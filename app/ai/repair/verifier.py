from app.ai.detector.road_damage import detect_road_damage

EFFECTIVE_DROP = 0.50     # confidence must fall by at least 50 percentage points
MAX_RESIDUAL   = 0.30     # after-confidence must be below 30%

def verify_repair(before_path: str, after_path: str) -> dict:
    before = detect_road_damage(before_path)
    after  = detect_road_damage(after_path)

    before_conf = before[0]["confidence"] if before else 0.0
    after_conf  = after[0]["confidence"]  if after  else 0.0
    drop = before_conf - after_conf

    passed = drop >= EFFECTIVE_DROP and after_conf <= MAX_RESIDUAL

    return {
        "before_confidence": round(before_conf, 3),
        "after_confidence":  round(after_conf, 3),
        "confidence_drop":   round(drop, 3),
        "result": "PASS" if passed else "FAIL",
        "recommendation": "Mark resolved" if passed else "Defect still detected — re-inspect"
    }
