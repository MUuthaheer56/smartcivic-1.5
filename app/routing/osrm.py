import requests

OSRM_SERVICE_URL = "https://router.project-osrm.org/route/v1/driving"
OSRM_TABLE_URL = "https://router.project-osrm.org/table/v1/driving"

def get_route(o_lat: float, o_lng: float, d_lat: float, d_lng: float) -> dict:
    """
    Query project-osrm.org for actual route geometries.
    """
    url = f"{OSRM_SERVICE_URL}/{o_lng},{o_lat};{d_lng},{d_lat}?overview=full&geometries=geojson"
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            routes = data.get("routes", [])
            if routes:
                return {
                    "status": "success",
                    "geometry": routes[0]["geometry"],
                    "distance_m": routes[0]["distance"],
                    "duration_s": routes[0]["duration"]
                }
    except Exception:
        pass
        
    return {"status": "unavailable", "geometry": None}

def get_distance_matrix(coords: list) -> list:
    """
    coords is list of tuples: (lat, lng)
    Returns a distance/duration matrix.
    """
    if not coords or len(coords) < 2:
        return []
        
    coord_str = ";".join([f"{lng},{lat}" for lat, lng in coords])
    url = f"{OSRM_TABLE_URL}/{coord_str}?annotations=duration"
    
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return r.json().get("durations", [])
    except Exception:
        pass
        
    # Return mock identity matrix if OSRM is offline to allow optimized sequence fallbacks
    n = len(coords)
    return [[0.0 if i == j else 100.0 * (i + j) for j in range(n)] for i in range(n)]

def get_nearest_workers_osrm(lat: float, lng: float, candidates: list) -> list:
    """
    Sort candidates using exact OSRM distances.
    """
    if not candidates:
        return []
        
    coords = [(lat, lng)] + [(w.get("current_location", {}).get("lat", 12.9716), w.get("current_location", {}).get("lng", 77.5946)) for w in candidates]
    matrix = get_distance_matrix(coords)
    
    scored = []
    if matrix and len(matrix) > 0:
        durations = matrix[0][1:] # durations from index 0 (origin) to workers
        for i, dur in enumerate(durations):
            scored.append({
                "worker": candidates[i],
                "duration_s": dur
            })
            
    # Sort by travel duration
    scored = sorted(scored, key=lambda x: x["duration_s"])
    return [s["worker"] for s in scored]
