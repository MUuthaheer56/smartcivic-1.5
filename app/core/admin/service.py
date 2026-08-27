import datetime
from bson import ObjectId
from app.extensions import db_wrapper, socketio
from app.models.complaint import Complaint

def get_admin_queue():
    """
    Returns complaints needing review:
    Status is REPORTED or (VERIFIED and routing_status is ADMIN_REVIEW)
    """
    query = {
        "$or": [
            {"status": "REPORTED"},
            {
                "$and": [
                    {"status": "VERIFIED"},
                    {"routing_status": "ADMIN_REVIEW"}
                ]
            }
        ]
    }
    docs = db_wrapper.db.complaints.find(query).sort("created_at", -1)
    return [Complaint.serialize(d) for d in docs]

def force_update_complaint(complaint_id, updates):
    try:
        comp_oid = ObjectId(complaint_id)
        complaint = db_wrapper.db.complaints.find_one({"_id": comp_oid})
        if not complaint:
            return None, "Complaint not found"
            
        allowed_keys = ["priority", "status", "assigned_worker_id", "severity_score"]
        db_updates = {}
        
        # Track status changes to manage worker busy states
        new_status = updates.get("status")
        old_status = complaint.get("status")
        
        for key in allowed_keys:
            if key in updates:
                val = updates[key]
                if key == "assigned_worker_id" and val:
                    db_updates[key] = ObjectId(val)
                elif key == "severity_score":
                    db_updates[key] = float(val)
                else:
                    db_updates[key] = val
                    
        if db_updates:
            db_updates["updated_at"] = datetime.datetime.now(datetime.timezone.utc)
            db_wrapper.db.complaints.update_one({"_id": comp_oid}, {"$set": db_updates})
            
            # Retrieve updated document
            updated_doc = db_wrapper.db.complaints.find_one({"_id": comp_oid})
            serialized = Complaint.serialize(updated_doc)
            
            # Manage worker busy status if worker is forced/unforced
            if "assigned_worker_id" in db_updates:
                new_worker_id = db_updates["assigned_worker_id"]
                old_worker_id = complaint.get("assigned_worker_id")
                
                # If worker changed
                if str(new_worker_id) != str(old_worker_id):
                    # Unassign old worker
                    if old_worker_id:
                        db_wrapper.db.workers.update_one(
                            {"_id": old_worker_id},
                            {"$set": {"status": "AVAILABLE", "active_complaint_id": None}}
                        )
                    # Assign new worker
                    if new_worker_id:
                        db_wrapper.db.workers.update_one(
                            {"_id": new_worker_id},
                            {"$set": {"status": "BUSY", "active_complaint_id": comp_oid}}
                        )
                        
            # Manage worker availability based on forced status changes
            if new_status and new_status != old_status:
                worker_id = updated_doc.get("assigned_worker_id")
                if worker_id:
                    if new_status in ["RESOLVED", "REJECTED"]:
                        db_wrapper.db.workers.update_one(
                            {"_id": worker_id},
                            {"$set": {"status": "AVAILABLE", "active_complaint_id": None}}
                        )
                    else:
                        db_wrapper.db.workers.update_one(
                            {"_id": worker_id},
                            {"$set": {"status": "BUSY", "active_complaint_id": comp_oid}}
                        )
            
            # Emit updates to Socket.IO
            socketio.emit("complaint_updated", serialized, to=f"complaint_{complaint_id}")
            socketio.emit("complaint_updated", serialized, to="admin")
            
            return serialized, None
        return Complaint.serialize(complaint), None
    except Exception as e:
        return None, str(e)

def get_admin_stats():
    now = datetime.datetime.now(datetime.timezone.utc)
    
    # Proactively check and update SLA breach tags in MongoDB
    db_wrapper.db.complaints.update_many(
        {
            "status": {"$nin": ["RESOLVED", "REJECTED"]},
            "sla_deadline": {"$lt": now}
        },
        {"$set": {"sla_breached": True}}
    )
    
    # Counts by status
    status_counts = {}
    for stat in ["REPORTED", "VERIFIED", "ASSIGNED", "IN_PROGRESS", "RESOLVED", "REOPENED", "REJECTED"]:
        status_counts[stat] = db_wrapper.db.complaints.count_documents({"status": stat})
        
    # Total open: everything except RESOLVED and REJECTED
    total_open = db_wrapper.db.complaints.count_documents({"status": {"$nin": ["RESOLVED", "REJECTED"]}})
    
    # High or Critical priority
    high_priority = db_wrapper.db.complaints.count_documents({
        "status": {"$nin": ["RESOLVED", "REJECTED"]},
        "priority": {"$in": ["HIGH", "CRITICAL"]}
    })
    
    # SLA breached count
    sla_breached = db_wrapper.db.complaints.count_documents({"sla_breached": True, "status": {"$nin": ["RESOLVED", "REJECTED"]}})
    
    # Available workers count
    available_workers = db_wrapper.db.workers.count_documents({"status": "AVAILABLE"})
    total_workers = db_wrapper.db.workers.count_documents({})
    
    # Counts by category
    pipeline_cat = [{"$group": {"_id": "$category", "count": {"$sum": 1}}}]
    cat_res = list(db_wrapper.db.complaints.aggregate(pipeline_cat))
    category_counts = {item["_id"]: item["count"] for item in cat_res if item["_id"]}
    
    # Counts by ward
    pipeline_ward = [{"$group": {"_id": "$ward", "count": {"$sum": 1}}}]
    ward_res = list(db_wrapper.db.complaints.aggregate(pipeline_ward))
    ward_counts = {item["_id"]: item["count"] for item in ward_res if item["_id"]}
    
    return {
        "status_counts": status_counts,
        "total_open": total_open,
        "high_priority": high_priority,
        "sla_breached": sla_breached,
        "available_workers": available_workers,
        "total_workers": total_workers,
        "category_counts": category_counts,
        "ward_counts": ward_counts
    }
