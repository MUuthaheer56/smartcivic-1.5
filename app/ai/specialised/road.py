import cv2
import numpy as np

def estimate_pothole_volume(image_path: str, bbox: dict = None) -> dict:
    """
    Estimates the volume of a pothole (in cm³) using shadow analysis
    and bounding box proportions. Returns volume and cost tier.
    """
    img = cv2.imread(image_path)
    if img is None:
        return {"volume_cm3": 0.0, "cost_tier": "LOW", "confidence": 0.0, "note": "unreadable image"}

    h, w = img.shape[:2]
    
    # If no bbox provided, assume a default region in the center bottom
    if not bbox:
        x1, y1, x2, y2 = int(w * 0.3), int(h * 0.5), int(w * 0.7), int(h * 0.9)
    else:
        # Translate normalized or absolute coordinates
        x1 = int(bbox.get("x1", w * 0.3))
        y1 = int(bbox.get("y1", h * 0.5))
        x2 = int(bbox.get("x2", w * 0.7))
        y2 = int(bbox.get("y2", h * 0.9))

    # Keep coordinates within image boundaries
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)

    crop = img[y1:y2, x1:x2]
    if crop.size == 0:
        return {"volume_cm3": 0.0, "cost_tier": "LOW", "confidence": 0.0, "note": "empty crop"}

    # Convert to grayscale for shadow intensity check
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    
    # Shadow pixels are typically very dark (e.g. intensity < 50)
    shadow_mask = gray < 50
    shadow_ratio = float(np.sum(shadow_mask)) / gray.size

    # Bounding box area relative to image
    bbox_area_pct = (x2 - x1) * (y2 - y1) / (w * h)

    # Calculate estimated physical dimensions (mock mapping for single image perspective)
    # Assume 1 pixel area represents ~0.05 cm² under typical camera angle
    approx_area_cm2 = (x2 - x1) * (y2 - y1) * 0.05
    # Depth estimated by shadow ratio: higher shadow ratio = deeper cavity (up to 15cm max)
    approx_depth_cm = max(2.0, shadow_ratio * 15.0)
    
    volume_cm3 = round(approx_area_cm2 * approx_depth_cm, 1)

    # Map to cost tiers
    if volume_cm3 < 5000:
        cost_tier = "LOW"
    elif volume_cm3 < 20000:
        cost_tier = "MEDIUM"
    else:
        cost_tier = "HIGH"

    return {
        "volume_cm3": volume_cm3,
        "cost_tier": cost_tier,
        "confidence": round(0.7 + (shadow_ratio * 0.2), 2),
        "note": "Estimated using shadow density analysis. Not a physical ground truth measurement."
    }
