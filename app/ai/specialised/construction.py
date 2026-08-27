import cv2
import numpy as np

def detect_construction_hazard(image_path: str) -> dict:
    img = cv2.imread(image_path)
    if img is None:
        return {"hazard_detected": False, "hazard_score": 0, "signals": []}

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    ground = gray[int(h*0.5):, :]

    dark_ratio  = float(np.sum(ground < 50)) / ground.size
    edges       = cv2.Canny(gray, 50, 150)
    edge_density = float(np.sum(edges > 0)) / edges.size

    score, signals = 0, []
    if dark_ratio > 0.15:    score += 40; signals.append("dark_ground_possible_trench")
    if edge_density < 0.05:  score += 20; signals.append("low_edge_density_no_barriers")

    return {
        "hazard_detected": score >= 40,
        "hazard_score": score,
        "signals": signals
    }

def check_construction_permit(lat: float, lng: float, db) -> dict:
    r = 30 / 111000
    p = db.construction_permits.find_one({
        "status": "ACTIVE",
        "lat": {"$gte": lat-r, "$lte": lat+r},
        "lng": {"$gte": lng-r, "$lte": lng+r}
    })
    if p:
        return {
            "permit_found": True,
            "permit_id": str(p.get("permit_id","")),
            "contractor": p.get("contractor_name",""),
            "escalation_type": "SAFETY_VIOLATION_LICENSED_SITE"
        }
    return {"permit_found": False, "escalation_type": "POSSIBLE_ILLEGAL_CONSTRUCTION"}
