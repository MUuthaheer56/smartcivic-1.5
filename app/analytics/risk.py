import math
import requests
from datetime import datetime, timedelta
from collections import defaultdict
from config import Config

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

def forecast_complaint_surge(ward: str, db) -> dict:
    """
    Predicts if a ward will experience a surge in complaints
    based on weather forecast variables and historical trends.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    one_month_ago = now - datetime.timedelta(days=30)
    
    # 1. Historical rate of complaints in this ward
    historical_count = db.complaints.count_documents({
        "ward": ward,
        "created_at": {"$gte": one_month_ago}
    })
    
    # 2. Get coordinates of a centroid in this ward
    # Find one complaint location to use as a centroid proxy
    sample = db.complaints.find_one({"ward": ward, "location.lat": {"$exists": True}})
    lat, lng = 12.9716, 77.5946
    if sample:
        lat = sample["location"]["lat"]
        lng = sample["location"]["lng"]

    # 3. OpenWeather forecast checks
    rain_probability = 0.0
    key = getattr(Config, "OPENWEATHER_API_KEY", None) or getattr(Config, "WEATHER_API_KEY", None)
    if key:
        try:
            url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lng}&appid={key}&cnt=4"
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                pops = [f.get("pop", 0) for f in r.json().get("list", [])]
                if pops:
                    rain_probability = sum(pops) / len(pops)
        except Exception:
            rain_probability = 0.5
    else:
        rain_probability = 0.5

    # Calculate surge probability
    # Base load from historical frequency + rain multiplication factor
    base_factor = min(30, historical_count * 2)
    weather_multiplier = 1.0 + (rain_probability * 1.5)
    surge_score = min(100.0, base_factor * weather_multiplier)

    # Compile recommendation
    need_preemptive_assign = surge_score >= 60.0
    
    return {
        "ward": ward,
        "surge_score": round(surge_score, 1),
        "rain_probability": round(rain_probability, 2),
        "historical_monthly_count": historical_count,
        "recommendation": "PRE_EMPTIVE_ALLOCATION" if need_preemptive_assign else "STANDARD_DISPATCH",
        "details": f"Expected increase in waterlogging and drainage reports. Pre-emptive assignment recommended." if need_preemptive_assign else "Normal complaint frequencies anticipated."
    }
