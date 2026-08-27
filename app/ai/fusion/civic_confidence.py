WEIGHTS = {
    "ai_confidence":    0.35,
    "image_quality":    0.20,
    "location_score":   0.15,
    "community_result": 0.20,
    "historical":       0.10
}

def compute_civic_confidence(
    ai_confidence: float,
    image_quality: float,
    location_score: float,
    community_result: float,
    historical_score: float
) -> dict:
    score = (
        ai_confidence    * WEIGHTS["ai_confidence"] +
        image_quality    * WEIGHTS["image_quality"] +
        location_score   * WEIGHTS["location_score"] +
        community_result * WEIGHTS["community_result"] +
        historical_score * WEIGHTS["historical"]
    )
    score = round(max(0.0, min(1.0, score)), 3)
    level = "HIGH" if score >= 0.80 else "MEDIUM" if score >= 0.55 else "LOW"
    return {"civic_confidence": score, "level": level}
