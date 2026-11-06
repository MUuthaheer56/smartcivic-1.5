import requests
from config import Config

def forecast_weather_risk(lat: float, lng: float, db) -> dict:
    """
    Evaluates weather risk for a location by querying the weather forecast API
    and combining it with historical drainage/waste complaints.
    """
    rain_probability = 0.0
    
    # 1. Fetch weather forecast precipitation probability
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
            rain_probability = 0.5 # Neutral fallback if API fails
    else:
        rain_probability = 0.5

    # 2. Count active unresolved drainage or waste management issues nearby (within 200m)
    r_deg = 200 / 111000
    active_issues = db.complaints.count_documents({
        "category": {"$in": ["Waste Management", "Drainage"]},
        "status": {"$nin": ["RESOLVED", "REJECTED"]},
        "location.lat": {"$gte": lat - r_deg, "$lte": lat + r_deg},
        "location.lng": {"$gte": lng - r_deg, "$lte": lng + r_deg}
    })

    # 3. Calculate risk score
    # Score goes from 0 to 100
    risk_score = min((active_issues * 15) + (rain_probability * 50), 100.0)

    return {
        "risk_score": round(risk_score, 1),
        "rain_probability": round(rain_probability, 2),
        "nearby_issues_count": active_issues,
        "risk_level": "HIGH" if risk_score >= 70 else "MEDIUM" if risk_score >= 40 else "LOW"
    }
