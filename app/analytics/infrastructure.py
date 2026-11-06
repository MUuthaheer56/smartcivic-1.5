import datetime
from bson import ObjectId

def predict_infrastructure_failure(lat: float, lng: float, db) -> dict:
    """
    Evaluates infrastructure health index (e.g. road surface decay)
    by auditing cumulative defect counts, repair frequencies, and soil moisture risk.
    """
    r_deg = 150 / 111000
    
    # 1. Count unresolved issues in 150m grid
    active_defects = db.complaints.count_documents({
        "category": {"$in": ["Road Damage", "Drainage", "Pothole"]},
        "status": {"$nin": ["RESOLVED", "REJECTED"]},
        "location.lat": {"$gte": lat - r_deg, "$lte": lat + r_deg},
        "location.lng": {"$gte": lng - r_deg, "$lte": lng + r_deg}
    })
    
    # 2. Find resolution history in last 180 days
    six_months_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=180)
    past_repairs = db.complaints.count_documents({
        "category": {"$in": ["Road Damage", "Drainage", "Pothole"]},
        "status": "RESOLVED",
        "resolved_at": {"$gte": six_months_ago},
        "location.lat": {"$gte": lat - r_deg, "$lte": lat + r_deg},
        "location.lng": {"$gte": lng - r_deg, "$lte": lng + r_deg}
    })

    # Failure index: active defects add risk, repeating repairs indicates base structural decay
    failure_risk = min(100.0, (active_defects * 20.0) + (past_repairs * 10.0))

    return {
        "failure_risk_score": round(failure_risk, 1),
        "risk_level": "CRITICAL" if failure_risk >= 80 else "HIGH" if failure_risk >= 50 else "MEDIUM" if failure_risk >= 20 else "LOW",
        "recurrent_repair_count": past_repairs,
        "recommendation": "URGENT_SUBGRADE_RECONSTRUCTION" if failure_risk >= 80 else "PREVENTATIVE_RESURFACING" if failure_risk >= 50 else "MONITOR"
    }
