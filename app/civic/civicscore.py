import datetime
from bson import ObjectId
from config import Config

EVENT_WEIGHTS = {
    # 1.5 weights
    "complaint_auto_pass":        +5,
    "verification_wrong":         -5,
    "community_confirm":          +4,
    
    # 1.6 weights
    "complaint_verified":        +10,
    "complaint_ai_auto":         +5,
    "verification_accurate":     +8,
    "verification_inaccurate":   -5,
    "complaint_rejected":        -8,
    "complaint_duplicate":       -3,
    "ai_correction_useful":      +6,
    "community_confirm_correct": +4,
    "repair_verified":           +3
}

def get_tier(score: float) -> str:
    # 1.6: use config values if available, fallback to defaults
    verifier_thresh = getattr(Config, "CIVICSCORE_VERIFIER_THRESHOLD", 50)
    guardian_thresh = getattr(Config, "CIVICSCORE_GUARDIAN_THRESHOLD", 150)
    
    if score >= guardian_thresh:
        return "Ward Guardian"
    if score >= verifier_thresh:
        return "Verifier"
    return "Reporter"

def compute_civicscore(history: list) -> float:
    score = 0.0
    for event in history:
        score += EVENT_WEIGHTS.get(event.get("type", ""), 0)
    return max(0.0, round(score, 1))

def record_event(db, user_id, event_type: str) -> tuple:
    now = datetime.datetime.now(datetime.timezone.utc)
    db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$push": {"contribution_history": {"type": event_type, "at": now}},
         "$set": {"last_active": now}}
    )
    user = db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        return 0.0, "Reporter"
        
    history = user.get("contribution_history", [])
    new_score = compute_civicscore(history)
    new_tier = get_tier(new_score)
    
    db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"civic_score": new_score, "tier": new_tier}}
    )
    return new_score, new_tier

def decay_civic_points(db):
    """
    Decays civic points by 5% for users who have been inactive for 30+ days.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    cutoff = now - datetime.timedelta(days=30)
    
    inactive_users = db.users.find({
        "last_active": {"$lt": cutoff},
        "civic_score": {"$gt": 0.0}
    })
    
    for u in inactive_users:
        old_score = u.get("civic_score", 0.0)
        # Apply 5% decay
        new_score = max(0.0, round(old_score * 0.95, 1))
        new_tier = get_tier(new_score)
        
        db.users.update_one(
            {"_id": u["_id"]},
            {
                "$set": {"civic_score": new_score, "tier": new_tier},
                "$push": {
                    "contribution_history": {
                        "type": "civic_score_decay",
                        "at": now,
                        "details": {"old_score": old_score, "new_score": new_score}
                    }
                }
            }
        )
