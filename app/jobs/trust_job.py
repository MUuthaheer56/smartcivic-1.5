from datetime import datetime, timedelta

def run_trust_job(db):
    wards = db.complaints.distinct("ward")
    scores = []
    now = datetime.utcnow()
    m_ago = now - timedelta(days=30)
    q_ago = now - timedelta(days=90)

    for ward in wards:
        if not ward: 
            continue
        total = db.complaints.count_documents({"ward": ward, "created_at": {"$gte": m_ago}})
        if total == 0: 
            continue

        resolved = db.complaints.count_documents({"ward": ward, "created_at": {"$gte": m_ago},
            "status": {"$in": ["RESOLVED","VERIFIED"]}})
        ai_verified = db.complaints.count_documents({"ward": ward, "created_at": {"$gte": m_ago},
            "repair_result": "PASS"})
        reopened = db.complaints.count_documents({"ward": ward, "created_at": {"$gte": m_ago},
            "status": "REOPENED"})
        prev = db.complaints.count_documents({"ward": ward,
            "created_at": {"$gte": q_ago, "$lt": m_ago}})

        rq  = ai_verified / resolved if resolved else 0.5
        sla = db.complaints.count_documents({"ward": ward, "created_at": {"$gte": m_ago},
            "sla_breached": False, "status": {"$in": ["RESOLVED","VERIFIED"]}})
        sla_rate = sla / resolved if resolved else 0.5
        rec  = max(0.0, 1.0 - (reopened / total) * 3)
        trend = min(1.0, total / (prev / 2)) if prev > 0 else 0.5

        trust = round(0.3*rq + 0.2*sla_rate + 0.2*rq + 0.1*rec + 0.1*trend, 1) * 100
        level = "HIGH" if trust >= 75 else "MEDIUM" if trust >= 50 else "LOW" if trust >= 30 else "CRITICAL"

        scores.append({"ward": ward, "trust_score": round(trust,1), "trust_level": level,
                        "total_complaints": total, "computed_at": now})

    db.ward_trust_scores.delete_many({})
    if scores: 
        db.ward_trust_scores.insert_many(scores)
