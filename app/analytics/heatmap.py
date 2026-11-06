from app.utils.cache import cache

def get_heatmap_data(db, category=None, severity=None, ward=None, status=None) -> list:
    # 1. Compile cache key
    cache_key = f"heatmap:{category}:{severity}:{ward}:{status}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    # 2. Query MongoDB on cache miss
    query = {}
    if category: query["category"] = category
    if ward:     query["ward"] = ward
    if status:   query["status"] = status
    if severity:
        bounds = {"LOW": (0.0, 4.0), "MEDIUM": (4.0, 7.0), "HIGH": (7.0, 10.0)}
        lo, hi = bounds.get(severity, (0.0, 10.0))
        query["severity_score"] = {"$gte": lo, "$lte": hi}

    complaints = list(db.complaints.find(query,
        {"location":1, "severity_score":1, "category":1, "status":1}))

    result = [{"lat": c["location"]["lat"], "lng": c["location"]["lng"],
             "severity": c.get("severity_score",0),
             "category": c.get("category",""),
             "status": c.get("status","")} for c in complaints
            if c.get("location",{}).get("lat")]
            
    # 3. Store in cache for 300s (5 minutes)
    cache.set(cache_key, result, ttl=300)
    
    return result
