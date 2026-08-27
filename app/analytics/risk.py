import math
from datetime import datetime, timedelta
from collections import defaultdict

GRID = 100 / 111000
DECAY_LAMBDA = 0.05

def decay(age_days): 
    return math.exp(-DECAY_LAMBDA * age_days)

def run_civicpulse_job(db):
    cutoff = datetime.utcnow() - timedelta(days=180)
    complaints = list(db.complaints.find({
        "category": {"$in": ["Road Damage", "Drainage", "Pothole"]},
        "created_at": {"$gte": cutoff}
    }))

    grid = defaultdict(list)
    for c in complaints:
        loc = c.get("location") or {}
        lat = loc.get("lat", 0)
        lng = loc.get("lng", 0)
        if lat and lng:
            cell = (round(lat/GRID)*GRID, round(lng/GRID)*GRID)
            grid[cell].append(c)

    now = datetime.utcnow()
    db.civicpulse_risk.delete_many({})
    records = []
    for (clat, clng), items in grid.items():
        weighted = sum(
            c.get("severity_score", 5) * decay((now - c["created_at"]).days)
            for c in items
        )
        score = min(round(weighted * 10, 2), 100.0) # Scaling factor to put it into a 0-100 range
        if score > 5:
            records.append({
                "lat": clat, "lng": clng,
                "risk_score": score,
                "complaint_count": len(items),
                "risk_level": "HIGH" if score>=70 else "MEDIUM" if score>=40 else "LOW",
                "computed_at": now
            })

    if records: 
        db.civicpulse_risk.insert_many(records)
