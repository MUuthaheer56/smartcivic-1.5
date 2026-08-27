def estimate_severity(detections: list, image_path: str) -> dict:
    import cv2
    img = cv2.imread(image_path)
    if img is None:
        return {"score": 0.0, "level": "LOW"}
        
    h, w = img.shape[:2]
    image_area = h * w

    if not detections:
        return {"score": 0.0, "level": "LOW"}

    top = detections[0]
    conf = top["confidence"]
    bbox = top["bbox"]
    bbox_area = (bbox["x2"] - bbox["x1"]) * (bbox["y2"] - bbox["y1"])
    area_ratio = bbox_area / image_area

    # class severity weights
    CLASS_WEIGHT = {
        "pothole": 1.0, "alligator_crack": 0.9, "rutting": 0.8,
        "transverse_crack": 0.6, "longitudinal_crack": 0.5, "bleeding": 0.4
    }
    cw = CLASS_WEIGHT.get(top["class"], 0.5)
    count_factor = min(len(detections) / 3.0, 1.0)

    score = (
        conf         * 4.0 +
        area_ratio   * 3.0 +
        cw           * 2.0 +
        count_factor * 1.0
    )
    score = min(round(score, 2), 10.0)
    level = "HIGH" if score >= 7 else "MEDIUM" if score >= 4 else "LOW"

    return {"score": score, "level": level, "class_weight": cw, "area_ratio": round(area_ratio, 4)}
