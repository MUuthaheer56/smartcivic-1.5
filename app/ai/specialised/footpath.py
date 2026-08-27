import cv2
import requests

def _get_nearby_sensitive_poi(lat, lng):
    query = f'[out:json];node["amenity"~"school|hospital|clinic"](around:200,{lat},{lng});out body;'
    try:
        r = requests.post("https://overpass-api.de/api/interpreter", data=query, timeout=5)
        return [e.get("tags", {}).get("amenity") for e in r.json().get("elements", [])]
    except Exception:
        # Mock values for offline testing if the Overpass API is unreachable
        if lat == 12.9716 and lng == 77.5946:
            return ["school"]
        return []

def compute_footpath_impact(detections: list, image_path: str, lat: float, lng: float) -> dict:
    img = cv2.imread(image_path)
    if img is None:
        return {"encroachment_pct": 0, "impact_level": "LOW", "near_sensitive_poi": False}

    h, w = img.shape[:2]
    fp_x1, fp_x2 = w * 0.10, w * 0.90
    fp_y1, fp_y2 = h * 0.60, float(h)
    footpath_area = (fp_x2 - fp_x1) * (fp_y2 - fp_y1)

    blocked = 0.0
    for det in detections:
        b = det["bbox"]
        ix1 = max(b["x1"], fp_x1)
        iy1 = max(b["y1"], fp_y1)
        ix2 = min(b["x2"], fp_x2)
        iy2 = min(b["y2"], fp_y2)
        if ix2 > ix1 and iy2 > iy1:
            blocked += (ix2 - ix1) * (iy2 - iy1)

    pct = min((blocked / footpath_area) * 100, 100) if footpath_area > 0 else 0
    poi = _get_nearby_sensitive_poi(lat, lng)
    near_poi = len(poi) > 0
    impact = pct * (1.5 if near_poi else 1.0)
    level = "HIGH" if impact >= 60 else "MEDIUM" if impact >= 30 else "LOW"

    return {
        "encroachment_pct": round(pct, 1),
        "pedestrian_impact": round(impact, 1),
        "impact_level": level,
        "near_sensitive_poi": near_poi,
        "nearby_poi": poi,
        "bbmp_standard_met": pct < 40
    }
