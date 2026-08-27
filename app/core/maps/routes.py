from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.extensions import db_wrapper
from app.utils.response import api_response
from app.core.maps.service import get_route
from app.core.complaints.service import get_complaints
from app.core.workers.service import get_workers
from bson import ObjectId

maps_bp = Blueprint("maps", __name__)

@maps_bp.route("/api/maps/complaints", methods=["GET"])
@jwt_required()
def maps_complaints_geojson():
    """
    Returns complaints as a GeoJSON FeatureCollection.
    Citizens/Workers are restricted to their registered ward's data.
    """
    identity = get_jwt_identity()
    claims = get_jwt()
    role = claims.get("role")
    
    filters = {}
    if role == "citizen":
        user_doc = db_wrapper.db.users.find_one({"_id": ObjectId(identity)})
        filters["ward"] = user_doc.get("ward", "General")
    elif role == "worker":
        worker_doc = db_wrapper.db.workers.find_one({"_id": ObjectId(identity)})
        filters["ward"] = worker_doc.get("ward", "General")
        
    # Admin can filter by ward optionally
    if role == "admin" and request.args.get("ward"):
        filters["ward"] = request.args.get("ward")
        
    complaints_list = get_complaints(filters)
    
    features = []
    for comp in complaints_list:
        loc = comp.get("location", {})
        lat = loc.get("lat")
        lng = loc.get("lng")
        if lat is not None and lng is not None:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(lng), float(lat)]  # GeoJSON is [lng, lat]
                },
                "properties": {
                    "id": comp["_id"],
                    "category": comp["category"],
                    "status": comp["status"],
                    "priority": comp["priority"],
                    "address": loc.get("address", ""),
                    "description": comp.get("description", "")
                }
            })
            
    return jsonify({
        "type": "FeatureCollection",
        "features": features
    })

@maps_bp.route("/api/maps/workers", methods=["GET"])
@jwt_required()
def maps_workers_api():
    """
    Returns workers with active locations.
    Admins see all active workers; workers see colleagues in the same ward.
    """
    identity = get_jwt_identity()
    claims = get_jwt()
    role = claims.get("role")
    
    filters = {}
    if role == "worker":
        worker_doc = db_wrapper.db.workers.find_one({"_id": ObjectId(identity)})
        filters["ward"] = worker_doc.get("ward", "General")
    elif role == "citizen":
        # Citizens can view workers in their ward if necessary, let's allow ward-level restriction
        user_doc = db_wrapper.db.users.find_one({"_id": ObjectId(identity)})
        filters["ward"] = user_doc.get("ward", "General")
        
    workers_list = get_workers(filters)
    active_workers = []
    
    for w in workers_list:
        loc = w.get("current_location")
        if loc and "lat" in loc and "lng" in loc:
            active_workers.append({
                "id": w["_id"],
                "name": w["name"],
                "status": w["status"],
                "department": w["department"],
                "ward": w["ward"],
                "location": loc
            })
            
    return api_response(True, data=active_workers)

@maps_bp.route("/api/maps/route", methods=["GET"])
@jwt_required()
def maps_route_api():
    """
    OSRM Routing endpoint wrapper.
    Accepts origin and destination parameters.
    """
    try:
        origin_lat = float(request.args.get("origin_lat"))
        origin_lng = float(request.args.get("origin_lng"))
        dest_lat = float(request.args.get("dest_lat"))
        dest_lng = float(request.args.get("dest_lng"))
    except (TypeError, ValueError):
        return api_response(False, error="Invalid coordinates provided", status_code=400)
        
    route_data = get_route(origin_lat, origin_lng, dest_lat, dest_lng)
    if not route_data:
        return api_response(False, error="Unable to calculate route from OSRM", status_code=400)
        
    return api_response(True, data=route_data)
