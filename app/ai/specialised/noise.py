import json
import pathlib

_limits_path = pathlib.Path(__file__).parent.parent.parent / "static/data/cpcb_noise_limits.json"
CPCB_LIMITS = json.loads(_limits_path.read_text()) if _limits_path.exists() else {
    "residential": {"day": 55, "night": 45},
    "commercial":  {"day": 65, "night": 55},
    "industrial":  {"day": 75, "night": 70},
    "silence":     {"day": 50, "night": 40}
}

def validate_noise_reading(measured_db: float, zone: str, hour: int) -> dict:
    period = "day" if 6 <= hour < 22 else "night"
    limits = CPCB_LIMITS.get(zone, CPCB_LIMITS["residential"])
    legal_limit = limits[period]
    is_violation = measured_db > legal_limit
    return {
        "measured_db": measured_db,
        "legal_limit_db": legal_limit,
        "zone": zone,
        "period": period,
        "is_violation": is_violation,
        "excess_db": round(max(0.0, measured_db - legal_limit), 1),
        "cpcb_reference": "Noise Pollution (Regulation and Control) Rules, 2000"
    }
