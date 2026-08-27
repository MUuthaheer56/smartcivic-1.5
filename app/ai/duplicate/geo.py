from datetime import datetime, timedelta
from bson import ObjectId

RADIUS_DEG = 100 / 111000   # 100 metres in degrees
LOOKBACK_DAYS = 30

def check_geo_duplicate(lat, lng, category, db, exclude_id=None) -> dict:
    try:
        lat = float(lat)
        lng = float(lng)
    except (ValueError, TypeError):
        return {"is_duplicate": False, "nearby_ids": []}
        
    cutoff = datetime.utcnow() - timedelta(days=LOOKBACK_DAYS)
    query = {
        "category": category,
        "status": {"$nin": ["RESOLVED", "REJECTED"]},
        "created_at": {"$gte": cutoff},
        "location.lat": {"$gte": lat - RADIUS_DEG, "$lte": lat + RADIUS_DEG},
        "location.lng": {"$gte": lng - RADIUS_DEG, "$lte": lng + RADIUS_DEG}
    }
    if exclude_id:
        query["_id"] = {"$ne": ObjectId(exclude_id)}

    matches = list(db.complaints.find(query, {"_id": 1, "location": 1, "status": 1}).limit(5))

    if not matches:
        return {"is_duplicate": False, "nearby_ids": []}

    return {
        "is_duplicate": True,
        "matched_id": str(matches[0]["_id"]),
        "match_count": len(matches),
        "nearby_ids": [str(m["_id"]) for m in matches]
    }
