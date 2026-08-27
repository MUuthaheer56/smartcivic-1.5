from datetime import datetime, timedelta
from collections import defaultdict

GRID = 50 / 111000
CFI_MIN = 3.0
MONTHS = 12

def run_coordination_job(db):
    cutoff = datetime.utcnow() - timedelta(days=MONTHS*30)
    complaints = list(db.complaints.find({
        "category": {"$in": ["Road Damage", "Construction Hazard", "Pothole", "Drainage"]},
        "status": {"$in": ["RESOLVED", "VERIFIED"]},
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

    failures = []
    for (clat, clng), items in grid.items():
        if len(items) < 2: 
            continue
        depts = {c.get("assigned_department", "Unknown") for c in items if c.get("assigned_department")}
        if not depts:
            depts = {"Unknown"}
            
        dates = sorted([c["created_at"] for c in items])
        rapid = any((dates[i+1]-dates[i]).days < 90 for i in range(len(dates)-1))
        cfi = (len(items) * len(depts)) / MONTHS
        if cfi >= CFI_MIN or (len(items) >= 2 and rapid):
            failures.append({
                "lat": clat, "lng": clng,
                "cfi_score": round(cfi, 2),
                "repeat_count": len(items),
                "department_count": len(depts),
                "departments": list(depts),
                "computed_at": datetime.utcnow()
            })

    db.coordination_failures.delete_many({})
    if failures:
        db.coordination_failures.insert_many(failures)
