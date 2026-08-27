from datetime import datetime
from bson import ObjectId

MIN_VOTES = 3
PASS_RATIO = 0.67

def cast_vote(complaint_id: str, voter_id: str, vote: bool, db) -> dict:
    complaint = db.complaints.find_one({"_id": ObjectId(complaint_id)})
    if not complaint:
        return {"error": "Not found"}

    # check tier
    voter = db.users.find_one({"_id": ObjectId(voter_id)})
    if not voter or voter.get("tier", "Reporter") == "Reporter":
        return {"error": "Insufficient tier — Verifier required"}

    # prevent double vote
    if any(v["voter_id"] == voter_id for v in complaint.get("verification_votes", [])):
        return {"error": "Already voted"}

    db.complaints.update_one(
        {"_id": ObjectId(complaint_id)},
        {"$push": {"verification_votes": {
            "voter_id": voter_id, "vote": vote, "at": datetime.utcnow()
        }}}
    )

    all_votes = complaint.get("verification_votes", []) + [{"voter_id": voter_id, "vote": vote, "at": datetime.utcnow()}]
    if len(all_votes) >= MIN_VOTES:
        yes = sum(1 for v in all_votes if v["vote"])
        ratio = yes / len(all_votes)
        result = "VERIFIED" if ratio >= PASS_RATIO else "REJECTED"
        db.complaints.update_one(
            {"_id": ObjectId(complaint_id)},
            {"$set": {
                "verification_result": result,
                "status": "VERIFIED" if result == "VERIFIED" else "REJECTED"
            }}
        )
        
        # Award civic scores to voters based on whether their vote was accurate
        from app.civic.civicscore import record_event
        for v in all_votes:
            correct = (v["vote"] == (result == "VERIFIED"))
            record_event(db, v["voter_id"],
                "verification_accurate" if correct else "verification_wrong")
                
        return {"complete": True, "result": result, "yes_ratio": round(ratio, 2)}

    return {"complete": False, "votes": len(all_votes), "needed": MIN_VOTES}
