import json
import pathlib
from shapely.geometry import Point, shape
from shapely.ops import transform
import pyproj

BUFFER_M = 30
_wgs84 = pyproj.CRS("EPSG:4326")
_utm43  = pyproj.CRS("EPSG:32643")
_to_utm = pyproj.Transformer.from_crs(_wgs84, _utm43, always_xy=True).transform
_to_wgs = pyproj.Transformer.from_crs(_utm43, _wgs84, always_xy=True).transform

_geojson = pathlib.Path(__file__).parent.parent.parent / "static/data/bengaluru_lakes.geojson"
_features = json.loads(_geojson.read_text()).get("features", []) if _geojson.exists() else []

def check_lake_buffer(lat: float, lng: float) -> dict:
    try:
        lat = float(lat)
        lng = float(lng)
    except (ValueError, TypeError):
        return {"violation": False}

    pt = Point(lng, lat)
    for f in _features:
        try:
            geom = shape(f["geometry"])
            name = f.get("properties", {}).get("name", "Unknown water body")
            geom_utm = transform(_to_utm, geom)
            buf_utm  = geom_utm.buffer(BUFFER_M)
            buf_wgs  = transform(_to_wgs, buf_utm)
            if buf_wgs.contains(pt) or geom.contains(pt):
                # Calculate distance in meters
                # Find the exterior distance
                if geom.geom_type == "Polygon":
                    dist = geom.exterior.distance(pt) * 111000
                else:
                    dist = geom.distance(pt) * 111000
                    
                return {
                    "violation": True,
                    "water_body": name,
                    "distance_m": round(dist, 1),
                    "inside_lake": geom.contains(pt),
                    "buffer_m": BUFFER_M,
                    "legal_reference": "KTCP Act — 30m buffer zone",
                    "priority_override": "CRITICAL",
                    "escalation": "Revenue Department"
                }
        except Exception as e:
            print(f"Error checking lake geometry: {e}")
            continue
            
    return {"violation": False}
