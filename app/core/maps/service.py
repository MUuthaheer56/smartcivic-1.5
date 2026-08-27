import requests

OSRM_BASE = "http://router.project-osrm.org"

def get_route(origin_lat, origin_lng, dest_lat, dest_lng):
    """
    Query project-osrm.org router service to get driving route and distance metrics.
    """
    url = f"{OSRM_BASE}/route/v1/driving/{origin_lng},{origin_lat};{dest_lng},{dest_lat}"
    params = {"overview": "full", "geometries": "geojson", "steps": "true"}
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        if not data or "routes" not in data or len(data["routes"]) == 0:
            return None
            
        route = data["routes"][0]
        return {
            "distance_km": round(route["distance"] / 1000, 2),
            "duration_min": round(route["duration"] / 60, 1),
            "geometry": route["geometry"]   # GeoJSON for Leaflet
        }
    except Exception:
        return None
