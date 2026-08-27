# Zero-shot classifier using a small HuggingFace model
# Falls back to keyword rules if model unavailable

CATEGORIES = [
    "Road Damage", "Waste Management", "Stray Animal",
    "Noise", "Footpath", "Construction Hazard",
    "Streetlight", "Drainage", "Lake Encroachment", "Other"
]

KEYWORD_RULES = {
    "pothole": "Road Damage", "crack": "Road Damage", "road": "Road Damage",
    "garbage": "Waste Management", "dump": "Waste Management", "waste": "Waste Management",
    "dog": "Stray Animal", "cow": "Stray Animal", "cattle": "Stray Animal", "stray": "Stray Animal",
    "noise": "Noise", "sound": "Noise", "loud": "Noise",
    "footpath": "Footpath", "sidewalk": "Footpath", "pavement": "Footpath",
    "construction": "Construction Hazard", "trench": "Construction Hazard", "excavation": "Construction Hazard",
    "light": "Streetlight", "streetlight": "Streetlight", "dark": "Streetlight",
    "drain": "Drainage", "flood": "Drainage", "waterlog": "Drainage",
    "lake": "Lake Encroachment", "water body": "Lake Encroachment"
}

_classifier = None
def _get_classifier():
    global _classifier
    if _classifier is None:
        try:
            from transformers import pipeline
            # Set timeout/local_files_only flags if needed, or just default loading
            _classifier = pipeline("zero-shot-classification",
                                   model="typeform/distilbart-mnli-12-3",
                                   device=-1)   # CPU
        except Exception as e:
            print(f"Warning: Zero-shot classifier unavailable ({e}). Keyword fallback enabled.")
            _classifier = "keyword"
    return _classifier

def classify_complaint_text(text: str) -> dict:
    clf = _get_classifier()
    text_lower = text.lower()

    if clf == "keyword":
        for kw, cat in KEYWORD_RULES.items():
            if kw in text_lower:
                return {"category": cat, "subcategory": None, "confidence": 0.6, "method": "keyword"}
        return {"category": "Other", "subcategory": None, "confidence": 0.3, "method": "keyword"}

    try:
        result = clf(text, CATEGORIES, multi_label=False)
        return {
            "category": result["labels"][0],
            "subcategory": None,
            "confidence": round(result["scores"][0], 3),
            "method": "zero_shot"
        }
    except Exception as e:
        print(f"Warning: transformers zero-shot failed: {e}. Falling back to keywords.")
        for kw, cat in KEYWORD_RULES.items():
            if kw in text_lower:
                return {"category": cat, "subcategory": None, "confidence": 0.6, "method": "keyword"}
        return {"category": "Other", "subcategory": None, "confidence": 0.0, "method": "error"}
