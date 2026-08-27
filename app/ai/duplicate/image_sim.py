import numpy as np
from PIL import Image
from bson import ObjectId

_use_fallback = False
_model = None
_transform = None

try:
    import torch
    from torchvision import models, transforms
    
    _transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])
except Exception as e:
    print(f"Warning: PyTorch or Torchvision unavailable. Falling back to color histogram. Error: {e}")
    _use_fallback = True

def _get_model():
    global _model, _use_fallback
    if _use_fallback:
        return None
    if _model is None:
        try:
            m = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.DEFAULT)
            m.classifier = torch.nn.Identity()   # remove classification head
            m.eval()
            _model = m
        except Exception as e:
            print(f"Warning: Failed to load MobileNet weights. Falling back to color histogram. Error: {e}")
            _use_fallback = True
    return _model

def get_color_histogram_embedding(image_path: str) -> list:
    """
    Fast, reliable fallback that extracts a 512-dimensional normalized color histogram.
    """
    img = Image.open(image_path).convert("RGB")
    # Resize to make histogram computation faster
    img = img.resize((128, 128))
    img_data = np.array(img)
    
    # 8 bins per channel -> 8 * 8 * 8 = 512 dimensions
    hist, _ = np.histogramdd(
        img_data.reshape(-1, 3), 
        bins=(8, 8, 8), 
        range=((0, 256), (0, 256), (0, 256))
    )
    hist = hist.flatten()
    
    # Normalize to unit length
    norm = np.linalg.norm(hist)
    if norm > 0:
        hist = hist / norm
    return hist.tolist()

def get_embedding(image_path: str) -> list:
    model = _get_model()
    if _use_fallback or model is None:
        return get_color_histogram_embedding(image_path)
        
    try:
        img = Image.open(image_path).convert("RGB")
        t = _transform(img).unsqueeze(0)
        with torch.no_grad():
            emb = model(t).squeeze().numpy()
        return emb.tolist()
    except Exception as e:
        print(f"Warning: PyTorch embedding extraction failed: {e}. Using color histogram fallback.")
        return get_color_histogram_embedding(image_path)

def cosine_similarity(a: list, b: list) -> float:
    a, b = np.array(a), np.array(b)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom > 0 else 0.0

def check_image_similarity(image_path: str, candidate_ids: list, db) -> dict:
    embedding = get_embedding(image_path)
    if not candidate_ids:
        return {"embedding": embedding, "max_similarity": 0.0, "similar_to": None}

    candidates = list(db.complaints.find(
        {"_id": {"$in": [ObjectId(i) for i in candidate_ids]}, "image_embedding": {"$exists": True}},
        {"_id": 1, "image_embedding": 1}
    ))

    best_sim = 0.0
    best_id = None
    for c in candidates:
        sim = cosine_similarity(embedding, c["image_embedding"])
        if sim > best_sim:
            best_sim, best_id = sim, str(c["_id"])

    return {"embedding": embedding, "max_similarity": round(best_sim, 3), "similar_to": best_id}
