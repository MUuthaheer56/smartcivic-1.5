from datetime import datetime, timedelta
from bson import ObjectId

def compute_worker_performance(worker_id: str, db) -> dict:
    m_ago = datetime.utcnow() - timedelta(days=30)
    q = {"assigned_worker_id": ObjectId(worker_id), "created_at": {"$gte": m_ago}}

    assigned  = db.complaints.count_documents(q)
    completed = db.complaints.count_documents({**q, "status": {"$in": ["RESOLVED","VERIFIED"]}})
    reopened  = db.complaints.count_documents({**q, "status": "REOPENED"})
    verified  = db.complaints.count_documents({**q, "repair_result": "PASS"})
    sla_ok    = db.complaints.count_documents({**q, "sla_breached": False,
                    "status": {"$in": ["RESOLVED","VERIFIED"]}})

    pipeline = [
        {"$match": {**q, "resolved_at": {"$exists": True}}},
        {"$project": {"diff": {"$subtract": ["$resolved_at","$created_at"]}}},
        {"$group":   {"_id": None, "avg": {"$avg": "$diff"}}}
    ]
    avg_res = list(db.complaints.aggregate(pipeline))
    avg_days = round(avg_res[0]["avg"] / 86400000, 1) if avg_res and avg_res[0]["avg"] else 0

    sla_rate   = sla_ok / completed if completed else 1.0
    score      = round(
        (completed / assigned if assigned else 0) * 40 +
        sla_rate * 30 +
        (verified / completed if completed else 0) * 20 +
        max(0.0, 1.0 - reopened / completed if completed else 1.0) * 10
    , 1)

    return {
        "worker_id": worker_id,
        "assigned": assigned, "completed": completed,
        "reopened": reopened, "ai_verified": verified,
        "avg_resolution_days": avg_days,
        "sla_compliance_pct": round(sla_rate*100, 1),
        "performance_score": round(score, 1)
    }
