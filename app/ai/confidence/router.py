from config import Config

def route_by_confidence(confidence: float) -> str:
    # Safely load configuration thresholds with fallback defaults
    auto_thresh = getattr(Config, "CONFIDENCE_AUTO_THRESHOLD", 0.85)
    verify_thresh = getattr(Config, "CONFIDENCE_VERIFY_THRESHOLD", 0.50)
    
    if confidence >= auto_thresh:
        return "AUTO"
    elif confidence >= verify_thresh:
        return "COMMUNITY_VERIFY"
    return "ADMIN_REVIEW"
