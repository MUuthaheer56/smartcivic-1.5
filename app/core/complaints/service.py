import os
import uuid
import datetime
import math
from bson import ObjectId
from werkzeug.utils import secure_filename
from app.extensions import db_wrapper, socketio
from app.models.complaint import Complaint
from app.models.worker import Worker
from app.models.user import User
from app.utils.validators import (
    validate_category,
    validate_location,
    validate_description,
    validate_image
)

def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371.0  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def create_new_complaint(citizen_id, category, subcategory, description, lat, lng, address, image_file, upload_folder, saved_image_path=None, ai_result=None):
    # Validations
    ok, err = validate_category(category)
    if not ok:
        return None, err
        
    ok, err = validate_location(lat, lng)
    if not ok:
        return None, err
        
    ok, err = validate_description(description)
    if not ok:
        return None, err
        
    # Check image file only if we haven't already saved it (meaning it's from the route handler)
    if not saved_image_path:
        ok, err = validate_image(image_file)
        if not ok:
            return None, err
        
    # Get user details for ward
    citizen_doc = db_wrapper.db.users.find_one({"_id": ObjectId(citizen_id)})
    if not citizen_doc:
        return None, "Citizen not found"
    ward = citizen_doc.get("ward", "General")
    
    # Save uploaded image with UUID filename if not already saved by routes
    if not saved_image_path:
        ext = os.path.splitext(secure_filename(image_file.filename))[1]
        if not ext:
            ext = ".png"
        image_filename = f"{uuid.uuid4().hex}{ext}"
        image_path_rel = os.path.join("static", "uploads", image_filename)
        full_path = os.path.join(upload_folder, image_filename)
        image_file.save(full_path)
        saved_image_path = "/" + image_path_rel.replace("\\", "/")
    
    # Create document
    complaint_doc = Complaint.create(
        citizen_id=citizen_id,
        ward=ward,
        category=category,
        subcategory=subcategory,
        description=description,
        lat=lat,
        lng=lng,
        address=address,
        image_path=saved_image_path
    )
    
    # Merge AI results into complaint before DB insert
    if ai_result:
        complaint_doc.update({
            "status": "AI_ANALYSIS",
            "ai_confidence": ai_result.get("ai_confidence"),
            "civic_confidence": ai_result.get("civic_confidence"),
            "routing_status": ai_result.get("routing_status"),
            "ai_detected_class": ai_result.get("ai_detected_class"),
            "bounding_box": ai_result.get("bounding_box"),
            "severity_score": ai_result.get("severity_score", 0.0),
            "is_duplicate": ai_result.get("is_duplicate", False),
            "duplicate_of": ai_result.get("duplicate_of"),
            "image_embedding": ai_result.get("image_embedding"),
            "image_quality_score": ai_result["steps"]["quality"]["score"] if "quality" in ai_result.get("steps", {}) else 0,
            
            # Layer 3 Specialised AI Results
            "streetlight": ai_result.get("streetlight"),
            "footpath": ai_result.get("footpath"),
            "dump_age": ai_result.get("dump_age"),
            "construction": ai_result.get("construction"),
            "lake": ai_result.get("lake"),
            "animals": ai_result.get("animals")
        })
        
        # Override priority for lake buffer violations
        if ai_result.get("lake", {}).get("violation"):
            complaint_doc["priority"] = "CRITICAL"
            
        # Auto-advance status based on routing
        if ai_result.get("routing_status") == "AUTO":
            complaint_doc["status"] = "VERIFIED"
            
    db_wrapper.db.complaints.insert_one(complaint_doc)
    serialized = Complaint.serialize(complaint_doc)
    
    # Broadcast to admin room via Socket.IO
    socketio.emit("complaint_created", serialized, to="admin")
    
    # Handle streetlight outage secondary report triggers
    if ai_result and ai_result.get("streetlight", {}).get("outage_detected") and category != "Streetlight":
        try:
            r_deg = 100 / 111000
            existing_st = db_wrapper.db.complaints.find_one({
                "_id": {"$ne": complaint_doc["_id"]},
                "category": "Streetlight",
                "status": {"$nin": ["RESOLVED", "REJECTED"]},
                "location.lat": {"$gte": float(lat) - r_deg, "$lte": float(lat) + r_deg},
                "location.lng": {"$gte": float(lng) - r_deg, "$lte": float(lng) + r_deg}
            })
            if not existing_st:
                create_new_complaint(
                    citizen_id=citizen_id,
                    category="Streetlight",
                    subcategory="Outage",
                    description="Automatically generated secondary streetlight outage report.",
                    lat=lat,
                    lng=lng,
                    address=address,
                    image_file=None,
                    upload_folder=upload_folder,
                    saved_image_path=saved_image_path, # Share the same photo
                    ai_result={
                        "status": "PROCESSED",
                        "ai_confidence": 1.0,
                        "civic_confidence": 0.8,
                        "routing_status": "AUTO",
                        "ai_detected_class": "streetlight_outage",
                        "severity_score": 5.0,
                        "is_duplicate": False,
                        "duplicate_of": None,
                        "image_embedding": None,
                        "steps": {"quality": {"score": 100}}
                    }
                )
        except Exception as e:
            print(f"Error creating secondary streetlight complaint: {e}")
            
    return serialized, None

def get_complaints(filters=None):
    query = {}
    if filters:
        if filters.get("ward"):
            query["ward"] = filters["ward"]
        if filters.get("category"):
            query["category"] = filters["category"]
        if filters.get("status"):
            query["status"] = filters["status"]
        if filters.get("priority"):
            query["priority"] = filters["priority"]
        if filters.get("citizen_id"):
            query["citizen_id"] = ObjectId(filters["citizen_id"])
            
    docs = db_wrapper.db.complaints.find(query).sort("created_at", -1)
    return [Complaint.serialize(d) for d in docs]

def get_complaint_by_id(complaint_id):
    try:
        doc = db_wrapper.db.complaints.find_one({"_id": ObjectId(complaint_id)})
        return Complaint.serialize(doc)
    except Exception:
        return None

def update_complaint_status(complaint_id, user_id, role, new_status, after_image_file=None, repair_result=None, upload_folder=None):
    try:
        comp_oid = ObjectId(complaint_id)
        complaint = db_wrapper.db.complaints.find_one({"_id": comp_oid})
        if not complaint:
            return None, "Complaint not found"
            
        current_status = complaint.get("status")
        
        # State machine validations
        # Allowed statuses in Layer 1: REPORTED, VERIFIED, ASSIGNED, IN_PROGRESS, RESOLVED, REOPENED, REJECTED
        valid_transitions = {
            "REPORTED": ["VERIFIED", "REJECTED"],
            "VERIFIED": ["ASSIGNED", "REJECTED"],
            "ASSIGNED": ["IN_PROGRESS", "RESOLVED"], # Admin or worker can force resolve
            "IN_PROGRESS": ["RESOLVED"],
            "RESOLVED": ["REOPENED"],
            "REOPENED": ["ASSIGNED", "VERIFIED", "IN_PROGRESS"],
            "REJECTED": ["VERIFIED"] # Re-verify rejected if admin decides
        }
        
        # Admin can transition to any state. Non-admins must follow state machine.
        if role != "admin":
            # Ownership checks (Prioritized for IDOR)
            if role == "worker" and str(complaint.get("assigned_worker_id")) != str(user_id):
                return None, "You are not assigned to this complaint"
            if role == "citizen" and str(complaint.get("citizen_id")) != str(user_id):
                return None, "You do not own this complaint"

            if new_status not in valid_transitions.get(current_status, []):
                return None, f"Invalid transition from {current_status} to {new_status}"
                
            # Role check constraints
            if new_status == "IN_PROGRESS" and role != "worker":
                return None, "Only the assigned worker can start work"
            if new_status == "RESOLVED" and role != "worker" and role != "admin":
                return None, "Only workers or admin can mark a complaint resolved"
            if new_status == "REOPENED" and role != "citizen":
                return None, "Only citizens can reopen resolved complaints"
                
        # Handle resolving with attachments
        update_data = {
            "status": new_status,
            "updated_at": datetime.datetime.now(datetime.timezone.utc)
        }
        
        if new_status == "RESOLVED":
            update_data["resolved_at"] = datetime.datetime.now(datetime.timezone.utc)
            if repair_result:
                update_data["repair_result"] = repair_result
            if after_image_file and upload_folder:
                ok, err = validate_image(after_image_file)
                if not ok:
                    return None, f"After-photo validation error: {err}"
                ext = os.path.splitext(secure_filename(after_image_file.filename))[1]
                if not ext:
                    ext = ".png"
                img_name = f"after_{uuid.uuid4().hex}{ext}"
                img_path = os.path.join("static", "uploads", img_name)
                after_image_file.save(os.path.join(upload_folder, img_name))
                update_data["after_image_path"] = "/" + img_path.replace("\\", "/")
                
            # If resolved, set worker back to AVAILABLE and clear their active complaint
            worker_id = complaint.get("assigned_worker_id")
            if worker_id:
                db_wrapper.db.workers.update_one(
                    {"_id": worker_id},
                    {
                        "$set": {
                            "status": "AVAILABLE",
                            "active_complaint_id": None
                        },
                        "$inc": {
                            "performance.completed": 1
                        }
                    }
                )
                
        if new_status == "IN_PROGRESS" and not complaint.get("first_response_at"):
            update_data["first_response_at"] = datetime.datetime.now(datetime.timezone.utc)
            
        db_wrapper.db.complaints.update_one({"_id": comp_oid}, {"$set": update_data})
        
        # Retrieve updated doc
        updated_doc = db_wrapper.db.complaints.find_one({"_id": comp_oid})
        serialized = Complaint.serialize(updated_doc)
        
        # Socket.IO Broadcast
        socketio.emit("complaint_updated", serialized, to=f"complaint_{complaint_id}")
        socketio.emit("complaint_updated", serialized, to="admin")
        
        return serialized, None
    except Exception as e:
        return None, str(e)

def vote_on_complaint(complaint_id, user_id, vote_type):
    try:
        comp_oid = ObjectId(complaint_id)
        user_oid = ObjectId(user_id)
        
        # Verify user exists and is a Verifier+
        user = db_wrapper.db.users.find_one({"_id": user_oid})
        if not user or user.get("tier") not in ["Verifier", "Ward Guardian"]:
            return None, "Only Verifiers or Ward Guardians are allowed to vote"
            
        complaint = db_wrapper.db.complaints.find_one({"_id": comp_oid})
        if not complaint:
            return None, "Complaint not found"
            
        if complaint.get("status") != "REPORTED":
            return None, "Can only vote on complaints in REPORTED status"
            
        # Prevent duplicate voting
        votes = complaint.get("verification_votes", [])
        if any(str(v["user_id"]) == str(user_id) for v in votes):
            return None, "You have already voted on this complaint"
            
        # Register the vote
        new_vote = {
            "user_id": user_oid,
            "vote": vote_type,  # "UPVOTE" (Verify) or "DOWNVOTE" (Reject)
            "voted_at": datetime.datetime.now(datetime.timezone.utc)
        }
        
        db_wrapper.db.complaints.update_one(
            {"_id": comp_oid},
            {"$push": {"verification_votes": new_vote}}
        )
        
        # Check net score for auto verification
        updated_comp = db_wrapper.db.complaints.find_one({"_id": comp_oid})
        upvotes = sum(1 for v in updated_comp.get("verification_votes", []) if v["vote"] == "UPVOTE")
        downvotes = sum(1 for v in updated_comp.get("verification_votes", []) if v["vote"] == "DOWNVOTE")
        net_votes = upvotes - downvotes
        
        status_updated = False
        if net_votes >= 2:  # Threshold of 2 net positive votes
            db_wrapper.db.complaints.update_one(
                {"_id": comp_oid},
                {
                    "$set": {
                        "status": "VERIFIED",
                        "verification_result": "VERIFIED",
                        "updated_at": datetime.datetime.now(datetime.timezone.utc)
                    }
                }
            )
            status_updated = True
        elif net_votes <= -2:  # Threshold of 2 net negative votes
            db_wrapper.db.complaints.update_one(
                {"_id": comp_oid},
                {
                    "$set": {
                        "status": "REJECTED",
                        "verification_result": "REJECTED",
                        "updated_at": datetime.datetime.now(datetime.timezone.utc)
                    }
                }
            )
            status_updated = True
            
        final_doc = db_wrapper.db.complaints.find_one({"_id": comp_oid})
        serialized = Complaint.serialize(final_doc)
        
        if status_updated:
            socketio.emit("complaint_updated", serialized, to=f"complaint_{complaint_id}")
            socketio.emit("complaint_updated", serialized, to="admin")
            
        return serialized, None
        
    except Exception as e:
        return None, str(e)

def assign_complaint_worker(complaint_id, worker_id=None):
    try:
        comp_oid = ObjectId(complaint_id)
        complaint = db_wrapper.db.complaints.find_one({"_id": comp_oid})
        if not complaint:
            return None, "Complaint not found"
            
        if complaint.get("status") not in ["REPORTED", "VERIFIED", "REOPENED"]:
            return None, f"Cannot assign worker to a complaint with status {complaint.get('status')}"
            
        # Determine department matching
        dept_map = {
            "Road Damage": "Roads",
            "Waste Management": "Sanitation",
            "Stray Animal": "Animal Control",
            "Noise": "General",
            "Footpath": "Roads",
            "Construction Hazard": "General",
            "Streetlight": "Electrical",
            "Drainage": "Sanitation",
            "Lake Encroachment": "Forestry",
            "Other": "General"
        }
        category = complaint.get("category")
        target_department = dept_map.get(category, "General")
        ward = complaint.get("ward")
        comp_lat = complaint["location"]["lat"]
        comp_lng = complaint["location"]["lng"]
        
        selected_worker = None
        
        if worker_id:
            # Explicit assignment
            selected_worker = db_wrapper.db.workers.find_one({
                "_id": ObjectId(worker_id),
                "status": "AVAILABLE"
            })
            if not selected_worker:
                return None, "Selected worker is not available or does not exist"
        else:
            # Automated nearest worker selection
            # 1. Find all AVAILABLE workers in the same ward + matching department
            candidates = list(db_wrapper.db.workers.find({
                "status": "AVAILABLE",
                "ward": ward,
                "department": target_department
            }))
            
            # Fallback 1: Broaden to same ward, any department
            if not candidates:
                candidates = list(db_wrapper.db.workers.find({
                    "status": "AVAILABLE",
                    "ward": ward
                }))
                
            # Fallback 2: Broaden to same department, any ward
            if not candidates:
                candidates = list(db_wrapper.db.workers.find({
                    "status": "AVAILABLE",
                    "department": target_department
                }))
                
            # Fallback 3: Any available worker
            if not candidates:
                candidates = list(db_wrapper.db.workers.find({
                    "status": "AVAILABLE"
                }))
                
            if not candidates:
                return None, "No available workers found for assignment"
                
            # 2. Factor in distance using Haversine & active workload (all available workers should have active_complaint_id is None, but let's check)
            best_dist = float("inf")
            for worker in candidates:
                curr_loc = worker.get("current_location")
                # Default coordinates in Bengaluru center if not set
                w_lat = curr_loc.get("lat") if (curr_loc and "lat" in curr_loc) else 12.9716
                w_lng = curr_loc.get("lng") if (curr_loc and "lng" in curr_loc) else 77.5946
                
                dist = haversine_distance(comp_lat, comp_lng, w_lat, w_lng)
                if dist < best_dist:
                    best_dist = dist
                    selected_worker = worker
                    
        if not selected_worker:
            return None, "Failed to match an available worker"
            
        selected_worker_oid = selected_worker["_id"]
        
        # 3. Update worker status to BUSY
        db_wrapper.db.workers.update_one(
            {"_id": selected_worker_oid},
            {
                "$set": {
                    "status": "BUSY",
                    "active_complaint_id": comp_oid
                },
                "$inc": {
                    "performance.assigned": 1
                }
            }
        )
        
        # 4. Update complaint status to ASSIGNED and assign worker
        db_wrapper.db.complaints.update_one(
            {"_id": comp_oid},
            {
                "$set": {
                    "status": "ASSIGNED",
                    "assigned_worker_id": selected_worker_oid,
                    "assigned_department": selected_worker.get("department", "General"),
                    "updated_at": datetime.datetime.now(datetime.timezone.utc)
                }
            }
        )
        
        final_comp = db_wrapper.db.complaints.find_one({"_id": comp_oid})
        serialized_comp = Complaint.serialize(final_comp)
        
        # Socket.IO Emits
        socketio.emit("assignment_received", serialized_comp, to=str(selected_worker_oid))
        socketio.emit("complaint_updated", serialized_comp, to=f"complaint_{complaint_id}")
        socketio.emit("complaint_updated", serialized_comp, to="admin")
        
        return serialized_comp, None
        
    except Exception as e:
        return None, str(e)
