import datetime
from bson import ObjectId

def generate_ward_monthly_report(ward: str, db) -> dict:
    """
    Generates a monthly analytical report summarizing complaints,
    SLA compliance, worker resolution rates, and reopens.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    month_ago = now - datetime.timedelta(days=30)

    q = {"ward": ward, "created_at": {"$gte": month_ago}}

    total = db.complaints.count_documents(q)
    if total == 0:
        return {
            "ward": ward,
            "period": "Last 30 Days",
            "total_complaints": 0,
            "resolution_rate_pct": 100.0,
            "sla_compliance_pct": 100.0,
            "reopened_count": 0,
            "avg_resolution_days": 0.0,
            "category_distribution": {}
        }

    resolved = db.complaints.count_documents({**q, "status": "RESOLVED"})
    reopened = db.complaints.count_documents({**q, "status": "REOPENED"})
    sla_ok = db.complaints.count_documents({**q, "sla_breached": False, "status": "RESOLVED"})

    # Calculate average resolution days
    pipeline = [
        {"$match": {**q, "resolved_at": {"$exists": True}}},
        {"$project": {"diff": {"$subtract": ["$resolved_at", "$created_at"]}}},
        {"$group": {"_id": None, "avg_ms": {"$avg": "$diff"}}}
    ]
    agg = list(db.complaints.aggregate(pipeline))
    avg_days = 0.0
    if agg and agg[0]["avg_ms"]:
        avg_days = round(agg[0]["avg_ms"] / (1000 * 60 * 60 * 24), 1)

    # Category counts
    cat_pipeline = [
        {"$match": q},
        {"$group": {"_id": "$category", "count": {"$sum": 1}}}
    ]
    cat_agg = list(db.complaints.aggregate(cat_pipeline))
    category_distribution = {c["_id"]: c["count"] for c in cat_agg}

    # Rates
    res_rate = round((resolved / total) * 100.0, 1)
    sla_rate = round((sla_ok / resolved) * 100.0, 1) if resolved else 100.0

    return {
        "ward": ward,
        "period": "Last 30 Days",
        "total_complaints": total,
        "resolved_count": resolved,
        "reopened_count": reopened,
        "resolution_rate_pct": res_rate,
        "sla_compliance_pct": sla_rate,
        "avg_resolution_days": avg_days,
        "category_distribution": category_distribution,
        "generated_at": now
    }
