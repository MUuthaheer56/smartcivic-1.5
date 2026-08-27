import json, pathlib, requests
from datetime import datetime, timedelta

THRESHOLD = float(60)

def run_drain_job(db):
    drains_path = pathlib.Path(__file__).parent.parent / "static/data/drain_locations.json"
    if not drains_path.exists():
        print(f"Warning: drains path not found at {drains_path}")
        return
        
    drains = json.loads(drains_path.read_text())
    from os import environ
    key = environ.get("OPENWEATHER_API_KEY", "")

    for d in drains:
        lat, lng = d["lat"], d["lng"]
        r = 50 / 111000
        cutoff = datetime.utcnow() - timedelta(days=7)
        nearby = db.complaints.count_documents({
            "category": {"$in": ["Waste Management", "Drainage"]},
            "status": {"$ne": "RESOLVED"},
            "created_at": {"$gte": cutoff},
            "location.lat": {"$gte": lat-r, "$lte": lat+r},
            "location.lng": {"$gte": lng-r, "$lte": lng+r}
        })
        rain_prob = 0.5
        if key:
            try:
                url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lng}&appid={key}&cnt=4"
                pops = [f.get("pop", 0) for f in requests.get(url, timeout=5).json().get("list", [])]
                rain_prob = sum(pops)/len(pops) if pops else 0.5
            except Exception:
                pass

        risk = min(nearby * 5 * rain_prob * 10, 100.0)
        db.drain_risk.update_one(
            {"drain_id": d["id"]},
            {"$set": {
                **d, 
                "risk_score": round(risk, 2),
                "rain_probability": rain_prob,
                "nearby_complaints": nearby,
                "computed_at": datetime.utcnow()
            }},
            upsert=True
        )
