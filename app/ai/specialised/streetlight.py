import cv2
import numpy as np
from datetime import datetime

DARKNESS_THRESHOLD = 45.0    # mean road-area brightness — below = likely outage
NIGHT_START = 19
NIGHT_END   = 6

def is_night(t: datetime) -> bool:
    return t.hour >= NIGHT_START or t.hour < NIGHT_END

def check_streetlight_darkness(image_path: str, submission_time: datetime) -> dict:
    if not is_night(submission_time):
        return {"outage_detected": False, "reason": "daytime_photo"}

    img = cv2.imread(image_path)
    if img is None:
        return {"outage_detected": False, "reason": "unreadable"}

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h = gray.shape[0]
    road_region = gray[int(h * 0.4):, :]
    luminance = float(np.mean(road_region))

    outage = luminance < DARKNESS_THRESHOLD
    return {
        "outage_detected": outage,
        "luminance_score": round(luminance, 1),
        "confidence": round(max(0, (DARKNESS_THRESHOLD - luminance) / DARKNESS_THRESHOLD), 2)
    }
