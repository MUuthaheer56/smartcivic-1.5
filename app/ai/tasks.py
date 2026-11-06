import threading
import datetime
import os
from bson import ObjectId
from app.ai.pipeline import run_photo_pipeline
from app.models.complaint import Complaint
from app.models.event import ComplaintEvent
from app.civic.civicscore import record_event

def queue_complaint_ai(complaint_id: str, db, socketio, upload_folder: str):
    """
    Spawns a background thread to process the AI pipeline asynchronously.
    """
    thread = threading.Thread(
        target=process_complaint_ai,
        args=(complaint_id, db, socketio, upload_folder)
    )
    thread.daemon = True
    thread.start()

def process_complaint_ai(complaint_id: str, db, socketio, upload_folder: str):
    try:
        comp_oid = ObjectId(complaint_id)
        
        # 1. Update status to AI_PROCESSING
        db.complaints.update_one(
            {"_id": comp_oid},
            {
                "$set": {
                    "status": "AI_PROCESSING",
                    "updated_at": datetime.datetime.now(datetime.timezone.utc)
                },
                "$push": {
                    "timeline_events": ComplaintEvent.create(
                        complaint_id=complaint_id,
                        event_type="STATUS_CHANGED",
                        from_status="AI_QUEUED",
                        to_status="AI_PROCESSING",
                        detail={"message": "AI analysis started."}
                    )
                }
            }
        )
        
        complaint = db.complaints.find_one({"_id": comp_oid})
        if not complaint:
            return
            
        # Get absolute photo path
        img_path = complaint.get("image_path", "")
        # Resolve clean relative path from "/" static reference
        if img_path.startswith("/"):
            img_path = img_path[1:]
        
        # Run master photo pipeline
        ai_result = run_photo_pipeline(
            image_path=img_path,
            lat=complaint["location"]["lat"],
            lng=complaint["location"]["lng"],
            category=complaint["category"],
            description=complaint["description"],
            submission_time=complaint["created_at"],
            db=db
        )
        
        # Determine status and routing values
        routing_status = ai_result.get("routing_status", "ADMIN_REVIEW")
        is_duplicate = ai_result.get("is_duplicate", False)
        
        # Determine status transitions based on composite confidence
        if is_duplicate:
            new_status = "DUPLICATE"
        elif routing_status == "AUTO":
            new_status = "VERIFIED"
        else:
            new_status = "AI_ANALYSIS" # maps to legacy AI_ANALYSIS
            
        # Merge values
        update_data = {
            "status": new_status,
            "routing_status": routing_status,
            "ai_confidence": ai_result.get("ai_confidence"),
            "civic_confidence": ai_result.get("civic_confidence"),
            "composite_confidence": ai_result.get("composite_confidence"),
            "confidence_breakdown": ai_result.get("confidence_breakdown"),
            "ai_detected_class": ai_result.get("ai_detected_class"),
            "bounding_box": ai_result.get("bounding_box"),
            "severity_score": ai_result.get("severity_score", 0.0),
            "is_duplicate": is_duplicate,
            "duplicate_of": ai_result.get("duplicate_of"),
            "image_embedding": ai_result.get("image_embedding"),
            "image_quality_score": ai_result["steps"]["quality"]["score"] if "quality" in ai_result.get("steps", {}) else 100,
            
            # Specialised AI
            "streetlight": ai_result.get("streetlight"),
            "footpath": ai_result.get("footpath"),
            "dump_age": ai_result.get("dump_age"),
            "construction": ai_result.get("construction"),
            "lake": ai_result.get("lake"),
            "animals": ai_result.get("animals"),
            "road": ai_result.get("road"),
            "weather_risk": ai_result.get("weather_risk"),
            "explanation": ai_result.get("explanation"),
            "updated_at": datetime.datetime.now(datetime.timezone.utc)
        }

        # Override priorities
        if ai_result.get("lake", {}).get("violation"):
            update_data["priority"] = "CRITICAL"
            update_data["assigned_department"] = "Revenue Department"
            update_data["tags"] = list(set(complaint.get("tags", []) + ["protected_zone_violation"]))
            
        # Construction hazard priority
        construction = ai_result.get("construction") or {}
        if construction.get("hazard_detected"):
            permit = db.construction_permits.find_one({
                "status": "ACTIVE",
                "lat": {"$gte": complaint["location"]["lat"] - 30/111000, "$lte": complaint["location"]["lat"] + 30/111000},
                "lng": {"$gte": complaint["location"]["lng"] - 30/111000, "$lte": complaint["location"]["lng"] + 30/111000}
            })
            if not permit:
                update_data["priority"] = "CRITICAL"
                update_data["assigned_department"] = "BBMP Enforcement"
                update_data["tags"] = list(set(complaint.get("tags", []) + ["illegal_construction"]))
            else:
                update_data["priority"] = "HIGH"
                update_data["assigned_department"] = "BBMP Safety Wing"
                update_data["tags"] = list(set(complaint.get("tags", []) + ["safety_violation_licensed_site"]))

        # Footpath near sensitive POI priority override
        footpath = ai_result.get("footpath") or {}
        if footpath.get("near_sensitive_poi"):
            update_data["priority"] = "CRITICAL"

        # Check dump age repeat locations
        dump = ai_result.get("dump_age") or {}
        if dump.get("neglect_indicator"):
            # Check repeat locations
            cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=60)
            r_deg = 50 / 111000
            repeat = db.complaints.find_one({
                "category": {"$in": ["Waste Management", "Drainage"]},
                "status": "RESOLVED",
                "created_at": {"$gte": cutoff},
                "location.lat": {"$gte": complaint["location"]["lat"] - r_deg, "$lte": complaint["location"]["lat"] + r_deg},
                "location.lng": {"$gte": complaint["location"]["lng"] - r_deg, "$lte": complaint["location"]["lng"] + r_deg}
            }) is not None
            if repeat:
                update_data["tags"] = list(set(complaint.get("tags", []) + ["contractor_accountability"]))

        # Push timeline events
        db.complaints.update_one(
            {"_id": comp_oid},
            {
                "$set": update_data,
                "$push": {
                    "timeline_events": {
                        "$each": [
                            ComplaintEvent.create(
                                complaint_id=complaint_id,
                                event_type="STATUS_CHANGED",
                                from_status="AI_PROCESSING",
                                to_status=new_status,
                                detail={"message": f"AI process completed. Decision: {routing_status}."}
                            ),
                            ComplaintEvent.create(
                                complaint_id=complaint_id,
                                event_type="AI_COMPLETED",
                                detail={"explanation": ai_result.get("explanation")}
                            )
                        ]
                    }
                }
            }
        )
        
        # Award initial user scores
        citizen_id = str(complaint["citizen_id"])
        if routing_status == "AUTO":
            record_event(db, citizen_id, "complaint_ai_auto")
        if is_duplicate:
            record_event(db, citizen_id, "complaint_duplicate")
            
        # Refetch and serialize
        updated_complaint = db.complaints.find_one({"_id": comp_oid})
        serialized = Complaint.serialize(updated_complaint)
        
        # Emit WebSocket notifications
        socketio.emit("ai_completed", serialized, to="admin")
        socketio.emit("complaint_updated", serialized, to=f"complaint_{complaint_id}")
        socketio.emit("complaint_updated", serialized, to="admin")

        # Auto trigger streetlight outage secondary report
        if ai_result.get("streetlight", {}).get("outage_detected") and complaint["category"] != "Streetlight":
            from app.core.complaints.service import _auto_create_streetlight_complaint
            _auto_create_streetlight_complaint(db, complaint["location"], ai_result["streetlight"])
            
    except Exception as e:
        print(f"Error in process_complaint_ai background task: {e}")
