import datetime
import time
from typing import Dict, Any, Optional

MODEL_REGISTRY = {
    "road_damage_detector": {
        "model_name": "yolov8n-road-damage",
        "model_version": "1.0.0",
        "dataset_name": "RDD2020-MultiCountry",
        "dataset_version": "v1.2",
        "input_resolution": "640x640",
        "preprocessing_version": "v1.0-rgb-norm",
        "runtime": "ONNXRuntime-CPU",
        "classes": ["pothole", "longitudinal_crack", "transverse_crack", "alligator_crack", "rutting", "bleeding"]
    },
    "nlp_complaint_classifier": {
        "model_name": "distilbart-mnli-civic",
        "model_version": "1.2.0",
        "dataset_name": "Municipal-311-Corpus",
        "dataset_version": "v2.1",
        "runtime": "HuggingFace-Transformers",
        "fallback_engine": "Regex-Lexicon-Heuristic"
    },
    "multimodal_fusion": {
        "model_name": "smartcivic-multimodal-fusion",
        "model_version": "2.0.0",
        "weights": {
            "image_detection": 0.40,
            "nlp_classification": 0.30,
            "specialized_spatial": 0.15,
            "image_quality": 0.15
        }
    },
    "repair_verification": {
        "model_name": "siamese-ssim-defect-attenuator",
        "model_version": "1.1.0",
        "metrics": ["cosine_similarity", "ssim", "defect_attenuation_ratio"]
    }
}

def create_model_provenance_record(
    model_key: str,
    prediction: Any,
    confidence: float,
    latency_ms: float,
    fallback_used: bool = False,
    fallback_reason: Optional[str] = None,
    input_metadata: Optional[Dict[str, Any]] = None,
    human_review_status: str = "PENDING"
) -> Dict[str, Any]:
    """
    Constructs an auditable, reproducible AI provenance record for research rigor.
    Meets IEEE requirements for empirical transparency and reproducibility.
    """
    model_spec = MODEL_REGISTRY.get(model_key, {
        "model_name": model_key,
        "model_version": "unknown",
        "dataset_name": "unknown",
        "dataset_version": "unknown"
    })

    return {
        "model_key": model_key,
        "model_name": model_spec.get("model_name"),
        "model_version": model_spec.get("model_version"),
        "dataset_name": model_spec.get("dataset_name"),
        "dataset_version": model_spec.get("dataset_version"),
        "inference_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "input_metadata": input_metadata or {},
        "prediction": prediction,
        "confidence": round(float(confidence), 4),
        "latency_ms": round(float(latency_ms), 2),
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "human_review": human_review_status
    }

def log_inference_audit(db, provenance_record: Dict[str, Any], complaint_id: Optional[str] = None):
    """
    Persists provenance record into the immutable ai_inference_audit collection.
    """
    if db is None:
        return
    try:
        from bson import ObjectId
        record = dict(provenance_record)
        if complaint_id:
            record["complaint_id"] = ObjectId(complaint_id) if ObjectId.is_valid(complaint_id) else complaint_id
        db.ai_inference_audit.insert_one(record)
    except Exception as e:
        # Logging should never crash pipeline execution
        print(f"[REGISTRY AUDIT WARNING] Could not persist inference audit: {e}")

