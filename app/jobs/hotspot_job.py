from datetime import datetime, timedelta
from collections import defaultdict

GRID = 100 / 111000

def run_hotspot_job(db):
    cutoff = datetime.utcnow() - timedelta(days=30)
    animals = list(db.complaints.find({
        "category": "Stray Animal",
        "status": {"$ne": "RESOLVED"},
        "created_at": {"$gte": cutoff}
    }))
    
    grid = defaultdict(list)
    for c in animals:
        loc = c.get("location") or {}
        lat = loc.get("lat", 0)
        lng = loc.get("lng", 0)
        if lat and lng:
            cell = (round(lat / GRID) * GRID, round(lng / GRID) * GRID)
            grid[cell].append(c)
            
    records = []
    now = datetime.utcnow()
    for (clat, clng), items in grid.items():
        count = len(items)
        # Calculate hotspot score based on count and animal details
        score = min(count * 20.0, 100.0)
        records.append({
            "lat": clat,
            "lng": clng,
            "animal_count": count,
            "hotspot_score": round(score, 2),
            "computed_at": now
        })
        
    db.animal_hotspots.delete_many({})
    if records:
        db.animal_hotspots.insert_many(records)
