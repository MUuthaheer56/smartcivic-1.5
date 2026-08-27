from datetime import datetime
from app.ai.quality.image_quality import assess_image_quality
from app.ai.detector.road_damage import detect_road_damage
from app.ai.severity.severity import estimate_severity
from app.ai.confidence.router import route_by_confidence
from app.ai.fusion.civic_confidence import compute_civic_confidence
from app.ai.duplicate.geo import check_geo_duplicate
from app.ai.duplicate.image_sim import check_image_similarity
from app.ai.nlp.classifier import classify_complaint_text
from app.ai.specialised.streetlight import check_streetlight_darkness
from app.ai.specialised.footpath import compute_footpath_impact
from app.ai.specialised.dump_age import estimate_dump_age
from app.ai.specialised.construction import detect_construction_hazard
from app.ai.specialised.lakes import check_lake_buffer
from app.ai.specialised.animals import detect_animals_in_photo

WASTE_CATEGORIES = ["Waste Management", "Drainage"]
ROAD_CATEGORIES  = ["Road Damage", "Footpath", "Construction Hazard"]

def run_photo_pipeline(
    image_path: str,
    lat: float,
    lng: float,
    category: str,
    description: str,
    submission_time: datetime,
    db,
    existing_complaint_id=None   # None for new, set for after-photo
) -> dict:

    result = {"status": "PROCESSING", "steps": {}}

    # ── Step 1: Quality gate ──────────────────────────────
    quality = assess_image_quality(image_path)
    result["steps"]["quality"] = quality
    if not quality["acceptable"]:
        return {
            "status": "REJECTED",
            "rejection_reason": quality["rejection_reason"],
            "quality": quality
        }

    # ── Step 2: Primary detection ─────────────────────────
    detections = detect_road_damage(image_path)
    result["steps"]["detections"] = detections
    result["ai_detected_class"] = detections[0]["class"] if detections else None
    result["ai_confidence"] = detections[0]["confidence"] if detections else 0.0
    result["bounding_box"] = detections[0]["bbox"] if detections else None

    # ── Step 3: Severity ──────────────────────────────────
    severity = estimate_severity(detections, image_path) if detections else {"score": 0.0, "level": "LOW"}
    result["severity_score"] = severity["score"]
    result["severity_level"] = severity["level"]

    # ── Step 4: Confidence routing ────────────────────────
    result["routing_status"] = route_by_confidence(result["ai_confidence"])

    # ── Specialised L3 Detectors ──────────────────────────
    result["streetlight"]  = check_streetlight_darkness(image_path, submission_time)
    result["footpath"]     = compute_footpath_impact(detections, image_path, lat, lng)
    result["dump_age"]     = estimate_dump_age(image_path) if category in WASTE_CATEGORIES else None
    result["construction"] = detect_construction_hazard(image_path) if category == "Construction Hazard" else None
    result["lake"]         = check_lake_buffer(lat, lng)
    result["animals"]      = detect_animals_in_photo(image_path) if category == "Stray Animal" else None

    # ── Step 5: Duplicate check ───────────────────────────
    dup_geo = check_geo_duplicate(lat, lng, category, db, exclude_id=existing_complaint_id)
    result["duplicate_geo"] = dup_geo
    result["is_duplicate"] = dup_geo["is_duplicate"]
    result["duplicate_of"] = dup_geo.get("matched_id")

    # ── Step 6: Image embedding + similarity ──────────────
    sim = check_image_similarity(image_path, dup_geo.get("nearby_ids", []), db)
    result["image_embedding"] = sim["embedding"]
    result["image_similarity"] = sim.get("max_similarity", 0.0)

    # ── Step 7: NLP category suggestion ───────────────────
    if description:
        nlp = classify_complaint_text(description)
        result["nlp_category"] = nlp["category"]
        result["nlp_subcategory"] = nlp["subcategory"]
        result["nlp_confidence"] = nlp["confidence"]

    # ── Step 8: Civic confidence fusion ───────────────────
    fusion = compute_civic_confidence(
        ai_confidence=result["ai_confidence"],
        image_quality=quality["score"] / 100,
        location_score=0.9,          # placeholder — geo consistency check
        community_result=0.5,        # neutral until votes arrive
        historical_score=0.5         # placeholder — query historical in Layer 3
    )
    result["civic_confidence"] = fusion["civic_confidence"]
    result["confidence_level"] = fusion["level"]

    result["status"] = "PROCESSED"
    return result
