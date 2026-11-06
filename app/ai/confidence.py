from config import Config

def score_pipeline_confidence(ai_result: dict) -> dict:
    """
    Computes a unified 0-100 composite confidence score and breakdown
    for the master AI pipeline execution.
    """
    # 1. Image Quality (default 100)
    quality_score = 100
    if "quality" in ai_result.get("steps", {}):
        quality_score = int(ai_result["steps"]["quality"].get("score", 100))
    elif "image_quality_score" in ai_result:
        quality_score = int(ai_result["image_quality_score"])

    # 2. Road Detection Confidence
    det_conf = ai_result.get("ai_confidence", 0.0)
    road_detection_score = int(det_conf * 100)

    # 3. NLP Classification Confidence
    nlp_conf = ai_result.get("nlp_confidence", 0.8)
    classification_score = int(nlp_conf * 100)

    # 4. Specialized AI Confidence
    specialized_score = 85
    # If specialized checks are active, we can fine-tune
    for key in ["streetlight", "footpath", "dump_age", "construction", "lake", "animals"]:
        val = ai_result.get(key)
        if val and isinstance(val, dict) and "confidence" in val:
            specialized_score = int(val["confidence"] * 100)
            break

    # 5. Duplicate Score (higher duplicate similarity reduces confidence in authenticity)
    sim = ai_result.get("image_similarity", 0.0)
    duplicate_score = int(max(0, 100 - (sim * 100)))

    # Compute composite average
    composite = int(
        (quality_score * 0.2) +
        (road_detection_score * 0.3) +
        (classification_score * 0.15) +
        (specialized_score * 0.15) +
        (duplicate_score * 0.2)
    )

    return {
        "confidence": composite,
        "breakdown": {
            "image_quality": quality_score,
            "road_detection": road_detection_score,
            "classification": classification_score,
            "specialized": specialized_score,
            "duplicate": duplicate_score
        }
    }
