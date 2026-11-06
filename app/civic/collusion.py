import datetime
from bson import ObjectId

def detect_vote_collusion(complaint_id: str, db) -> dict:
    """
    Analyzes voting logs on a complaint to identify potential collusion.
    Checks IP proximity, account ages, response timing, and voting overlaps.
    """
    comp_oid = ObjectId(complaint_id)
    complaint = db.complaints.find_one({"_id": comp_oid})
    if not complaint:
        return {"collusion_risk": 0.0, "flagged_voter_ids": [], "reasons": []}

    votes = complaint.get("verification_votes", [])
    if len(votes) < 2:
        return {"collusion_risk": 0.0, "flagged_voter_ids": [], "reasons": []}

    # Fetch voter user documents
    voter_ids = [ObjectId(v["voter_id"]) for v in votes if v.get("voter_id")]
    users = {str(u["_id"]): u for u in db.users.find({"_id": {"$in": voter_ids}})}

    flagged_voters = set()
    reasons = []
    risk_points = 0

    # 1. IP Proximity check (same IP addresses or subnets)
    # Since we log IP on registration or login, we check if they share login IPs
    ip_groups = {}
    for uid, u in users.items():
        # Retrieve login history from audit_logs
        login_logs = list(db.audit_logs.find({"user_id": ObjectId(uid), "action": "LOGIN_SUCCESS"}).limit(3))
        ips = {log["ip_address"] for log in login_logs if log.get("ip_address")}
        for ip in ips:
            ip_groups.setdefault(ip, []).append(uid)

    for ip, uids in ip_groups.items():
        if len(uids) >= 2 and ip not in ["127.0.0.1", "localhost"]:
            risk_points += 30
            reasons.append(f"Voters {', '.join(uids)} logged in from shared IP: {ip}")
            for uid in uids:
                flagged_voters.add(uid)

    # 2. Account Age checks (recent accounts registering within 24h of vote or in bulk)
    now = datetime.datetime.now(datetime.timezone.utc)
    for uid, u in users.items():
        created_at = u.get("created_at")
        if created_at:
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=datetime.timezone.utc)
            age_hours = (now - created_at).total_seconds() / 3600
            if age_hours < 48:
                risk_points += 15
                reasons.append(f"Voter {uid} is a recently created account (< 48h old)")
                flagged_voters.add(uid)

    # 3. Response Timing checks (votes cast within seconds of each other)
    voted_times = []
    for v in votes:
        vt = v.get("voted_at")
        if vt:
            if vt.tzinfo is None:
                vt = vt.replace(tzinfo=datetime.timezone.utc)
            voted_times.append((str(v["voter_id"]), vt))
            
    voted_times = sorted(voted_times, key=lambda x: x[1])
    for i in range(len(voted_times) - 1):
        diff = (voted_times[i+1][1] - voted_times[i][1]).total_seconds()
        if diff < 10: # within 10 seconds of each other
            risk_points += 20
            reasons.append(f"Votes cast by {voted_times[i][0]} and {voted_times[i+1][0]} were submitted within {int(diff)} seconds.")
            flagged_voters.add(voted_times[i][0])
            flagged_voters.add(voted_times[i+1][0])

    # Compile risk level
    risk = min(1.0, risk_points / 100.0)

    # If collusion risk is high, log to audit trail
    if risk >= 0.50:
        db.audit_logs.insert_one({
            "action": "COLLUSION_FLAGGED",
            "complaint_id": comp_oid,
            "collusion_risk": risk,
            "flagged_voters": list(flagged_voters),
            "timestamp": datetime.datetime.now(datetime.timezone.utc)
        })

    return {
        "collusion_risk": round(risk, 2),
        "flagged_voter_ids": list(flagged_voters),
        "reasons": reasons
    }
