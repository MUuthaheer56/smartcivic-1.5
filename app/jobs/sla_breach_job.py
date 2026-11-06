import datetime
from app.models.event import ComplaintEvent
from app.models.notification import Notification

def run_sla_breach_job(db):
    """
    Scans open complaints. Flags breaches, logs timeline events,
    and queues notifications.
    """
    now = datetime.datetime.utcnow()
    
    # Query unresolved complaints where deadline has passed and breach is not flagged
    open_complaints = list(db.complaints.find({
        "status": {"$in": ["REPORTED", "VERIFIED", "ASSIGNED", "IN_PROGRESS", "REOPENED", "AI_ANALYSIS"]},
        "sla_breached": False,
        "sla_deadline": {"$lt": now}
    }))
    
    for c in open_complaints:
        complaint_id = c["_id"]
        
        # 1. Update flag
        db.complaints.update_one(
            {"_id": complaint_id},
            {
                "$set": {"sla_breached": True, "updated_at": now},
                "$push": {
                    "timeline_events": ComplaintEvent.create(
                        complaint_id=str(complaint_id),
                        event_type="SLA_BREACHED",
                        detail={"message": "Resolution deadline has breached."}
                    )
                }
            }
        )

        # 2. Notify Citizen
        citizen_id = c.get("citizen_id")
        if citizen_id:
            db.notifications.insert_one(
                Notification.create(
                    user_id=str(citizen_id),
                    event_type="SLA_BREACHED",
                    message=f"SLA deadline breached for your report: {c.get('category')}.",
                    complaint_id=str(complaint_id)
                )
            )

        # 3. Notify Assigned Worker
        worker_id = c.get("assigned_worker_id")
        if worker_id:
            db.notifications.insert_one(
                Notification.create(
                    user_id=str(worker_id),
                    event_type="SLA_BREACHED",
                    message=f"SLA deadline breached! Please resolve immediately.",
                    complaint_id=str(complaint_id)
                )
            )
