import datetime
import random

def run_notification_flush_job(db, simulate_failures=False):
    """
    Every 60s, processes queued notification tasks.
    Retries failed operations up to 3 times.
    """
    queued = list(db.notifications.find({
        "status": {"$in": ["QUEUED", "RETRY"]},
        "retries": {"$lt": 3}
    }))
    
    for n in queued:
        # Simulate notification delivery channel dispatch
        success = True
        
        # Introduce a minor mock failure rate (e.g. 5%) only when explicitly testing retry workflows
        if simulate_failures and random.random() < 0.05:
            success = False
            
        now = datetime.datetime.now(datetime.timezone.utc)
        if success:
            db.notifications.update_one(
                {"_id": n["_id"]},
                {"$set": {"status": "SENT", "updated_at": now}}
            )
            print(f"[NOTIFICATION SEND] Dispatched notification to User {n['user_id']}: {n['message']}")
        else:
            new_retries = n["retries"] + 1
            new_status = "FAILED" if new_retries >= 3 else "RETRY"
            db.notifications.update_one(
                {"_id": n["_id"]},
                {
                    "$set": {
                        "status": new_status,
                        "retries": new_retries,
                        "updated_at": now
                    }
                }
            )
            print(f"[NOTIFICATION RETRY] Delivery failed for {n['_id']}. Retries count: {new_retries}")
