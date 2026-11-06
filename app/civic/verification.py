import datetime
from bson import ObjectId
from app.civic.civicscore import record_event
from app.civic.collusion import detect_vote_collusion
from app.models.event import ComplaintEvent

MIN_VOTES  = 3
PASS_RATIO = 0.67

def process_vote(complaint_id: str, voter_id: str, vote: bool, db) -> dict:
    """
    Records a verification vote. Calculates verifier tier validations,
    consensus thresholds, collusion audits, and awards civic scores.
    """
    complaint = db.complaints.find_one({"_id": ObjectId(complaint_id)})
    if not complaint:
        return {"error": "Complaint not found"}

    # 1. Verify voter tier
    voter = db.users.find_one({"_id": ObjectId(voter_id)})
    if not voter:
        return {"error": "Voter not found"}
        
    v_tier = voter.get("tier", "Reporter")
    if v_tier == "Reporter":
        return {"error": "Verifier tier required to vote"}

    # 2. Prevent double voting
    votes = complaint.get("verification_votes", [])
    already_voted = any(
        str(v.get("voter_id")) == voter_id
        for v in votes
    )
    if already_voted:
        return {"error": "Already voted on this complaint"}

    # 3. Record vote
    new_vote = {
        "voter_id": voter_id,
        "user_id": ObjectId(voter_id), # support both schemas
        "vote": vote,
        "voted_at": datetime.datetime.now(datetime.timezone.utc),
        "at": datetime.datetime.now(datetime.timezone.utc) # support both schemas
    }
    
    db.complaints.update_one(
        {"_id": ObjectId(complaint_id)},
        {"$push": {
            "verification_votes": new_vote,
            "timeline_events": ComplaintEvent.create(
                complaint_id=complaint_id,
                event_type="VOTE_CAST",
                actor_id=voter_id,
                actor_role="citizen",
                detail={"vote": vote}
            )
        }}
    )

    # 4. Refetch updated votes
    updated = db.complaints.find_one({"_id": ObjectId(complaint_id)})
    all_votes = updated.get("verification_votes", [])

    # Run collusion detection
    collusion_res = detect_vote_collusion(complaint_id, db)
    if collusion_res.get("collusion_risk", 0.0) >= 0.5:
        # Flag for admin review
        db.complaints.update_one(
            {"_id": ObjectId(complaint_id)},
            {"$set": {"collusion_flagged": True, "collusion_details": collusion_res}}
        )

    if len(all_votes) < MIN_VOTES:
        return {
            "complete": False,
            "votes_so_far": len(all_votes),
            "votes": len(all_votes), # support both schemas
            "needed": MIN_VOTES
        }

    # 5. Consensus check
    yes_count = sum(1 for v in all_votes if v["vote"])
    ratio = yes_count / len(all_votes)
    result = "VERIFIED" if ratio >= PASS_RATIO else "REJECTED"
    new_status = "VERIFIED" if result == "VERIFIED" else "REJECTED"

    db.complaints.update_one(
        {"_id": ObjectId(complaint_id)},
        {"$set": {
            "verification_result": result,
            "status": new_status,
            "updated_at": datetime.datetime.now(datetime.timezone.utc)
        }}
    )

    # 6. Award CivicScore to voters
    for v in all_votes:
        correct_vote = (v["vote"] == (result == "VERIFIED"))
        event_type = "verification_accurate" if correct_vote else "verification_inaccurate"
        record_event(db, str(v.get("voter_id") or v.get("user_id")), event_type)

    # 7. Award CivicScore to author if verified
    author_id = complaint.get("citizen_id")
    if result == "VERIFIED" and author_id:
        record_event(db, str(author_id), "complaint_verified")

    return {
        "complete": True,
        "result": result,
        "yes_ratio": round(ratio, 2),
        "total_votes": len(all_votes)
    }

def cast_vote(complaint_id: str, voter_id: str, vote: bool, db) -> dict:
    """
    Alias to process_vote for 1.5 tests compatibility.
    """
    return process_vote(complaint_id, voter_id, vote, db)
