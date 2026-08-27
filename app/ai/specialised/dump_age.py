import cv2
import numpy as np
from datetime import datetime, timedelta

def estimate_dump_age(image_path: str) -> dict:
    img = cv2.imread(image_path)
    if img is None:
        return {"age_range": "unknown", "neglect_indicator": False}

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    saturation   = float(np.mean(hsv[:, :, 1]))
    brightness   = float(np.mean(gray))
    sharpness    = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    green_ratio  = float(np.mean(img[:, :, 1])) / (float(np.mean(img)) + 1)

    score = 0
    if saturation < 60:   score += 2
    if brightness < 80:   score += 2
    if sharpness < 200:   score += 1
    if green_ratio > 1.1: score += 2

    ranges = {
        (0, 1): ("0–3 days",   0,  3,  False),
        (2, 3): ("3–7 days",   3,  7,  False),
        (4, 5): ("7–14 days",  7, 14,  True),
        (6, 7): ("14+ days",  14, 30,  True),
    }
    for (lo, hi), (label, mn, mx, neglect) in ranges.items():
        if lo <= score <= hi:
            return {
                "age_range": label, "age_days_min": mn,
                "age_days_max": mx, "neglect_indicator": neglect,
                "confidence": "rule_based_v1"
            }
    return {"age_range": "14+ days", "age_days_min": 14, "age_days_max": 30, "neglect_indicator": True}

def check_repeat_dump_location(lat: float, lng: float, db) -> bool:
    cutoff = datetime.utcnow() - timedelta(days=60)
    return db.complaints.find_one({
        "category": {"$in": ["Waste Management", "Drainage"]},
        "status": "RESOLVED",
        "created_at": {"$gte": cutoff},
        "location.lat": {"$gte": lat - 0.0005, "$lte": lat + 0.0005},
        "location.lng": {"$gte": lng - 0.0005, "$lte": lng + 0.0005}
    }) is not None
