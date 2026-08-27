EVENTS = {
    "complaint_verified":     +10,
    "complaint_auto_pass":    +5,
    "verification_accurate":  +8,
    "verification_wrong":     -5,
    "complaint_rejected":     -8,
    "complaint_duplicate":    -3,
    "ai_correction_useful":   +6,
    "community_confirm":      +4,
    "repair_verified":        +3
}

def compute_civicscore(history: list) -> float:
    return max(0.0, round(sum(EVENTS.get(e["type"], 0) for e in history), 1))

def record_event(db, user_id, event_type: str):
    from bson import ObjectId
    from datetime import datetime
    db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$push": {"contribution_history": {"type": event_type, "at": datetime.utcnow()}}}
    )
    user = db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        return 0.0, "Reporter"
    new_score = compute_civicscore(user.get("contribution_history", []))
    new_tier = get_tier(new_score)
    db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"civic_score": new_score, "tier": new_tier}}
    )
    return new_score, new_tier

def get_tier(score: float) -> str:
    if score >= 150: return "Ward Guardian"
    if score >= 50:  return "Verifier"
    return "Reporter"
