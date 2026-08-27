from flask import Blueprint, request, render_template, redirect, url_for
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from flask_socketio import join_room
from app.extensions import socketio, db_wrapper
from app.utils.response import api_response
from app.utils.auth_decorators import worker_required, admin_required
from app.core.workers.service import (
    get_workers,
    get_worker_by_id,
    update_worker_location,
    get_worker_route,
    get_worker_performance
)
from bson import ObjectId

workers_bp = Blueprint("workers", __name__)

# --- Jinja2 Page Views ---

@workers_bp.route("/worker/dashboard", methods=["GET"])
@worker_required
def worker_dashboard():
    worker_id = get_jwt_identity()
    worker_doc = db_wrapper.db.workers.find_one({"_id": ObjectId(worker_id)})
    
    # Get active complaint details
    active_complaint = None
    active_complaint_id = worker_doc.get("active_complaint_id")
    if active_complaint_id:
        active_complaint = db_wrapper.db.complaints.find_one({"_id": ObjectId(active_complaint_id)})
        if active_complaint:
            # Serialize
            from app.models.complaint import Complaint
            active_complaint = Complaint.serialize(active_complaint)
            
    return render_template(
        "worker/dashboard.html",
        worker=worker_doc,
        active_complaint=active_complaint
    )

@workers_bp.route("/worker/repair/<id>", methods=["GET"])
@worker_required
def worker_repair(id):
    worker_id = get_jwt_identity()
    complaint = db_wrapper.db.complaints.find_one({"_id": ObjectId(id)})
    
    if not complaint:
        return redirect("/worker/dashboard")
        
    # IDOR check: Verify the worker is indeed assigned
    if str(complaint.get("assigned_worker_id")) != str(worker_id):
        return redirect("/worker/dashboard")
        
    from app.models.complaint import Complaint as ModelComplaint
    return render_template("worker/repair.html", complaint=ModelComplaint.serialize(complaint))


# --- REST API Endpoints ---

@workers_bp.route("/api/workers", methods=["GET"])
@admin_required
def list_workers_api():
    filters = {}
    if request.args.get("ward"):
        filters["ward"] = request.args.get("ward")
    if request.args.get("department"):
        filters["department"] = request.args.get("department")
    if request.args.get("status"):
        filters["status"] = request.args.get("status")
        
    workers = get_workers(filters)
    return api_response(True, data=workers)

@workers_bp.route("/api/workers/<id>", methods=["GET"])
@jwt_required()
def get_worker_api(id):
    # Admin can view anyone; worker can only view themselves
    identity = get_jwt_identity()
    claims = get_jwt()
    role = claims.get("role")
    
    if role != "admin" and str(identity) != str(id):
        return api_response(False, error="Forbidden: IDOR validation failed", status_code=403)
        
    worker = get_worker_by_id(id)
    if not worker:
        return api_response(False, error="Worker not found", status_code=404)
        
    return api_response(True, data=worker)

@workers_bp.route("/api/workers/<id>/location", methods=["PATCH"])
@worker_required
def update_location_api(id):
    identity = get_jwt_identity()
    if str(identity) != str(id):
         return api_response(False, error="Forbidden: Cannot update another worker's location", status_code=403)
         
    data = request.get_json() or {}
    lat = data.get("lat")
    lng = data.get("lng")
    
    if lat is None or lng is None:
        return api_response(False, error="Coordinates lat and lng are required", status_code=400)
        
    ok, err = update_worker_location(id, lat, lng)
    if not ok:
        return api_response(False, error=err, status_code=400)
        
    return api_response(True, data={"message": "Location updated successfully"})

@workers_bp.route("/api/workers/<id>/route", methods=["GET"])
@jwt_required()
def get_route_api(id):
    identity = get_jwt_identity()
    claims = get_jwt()
    role = claims.get("role")
    
    # IDOR Check: worker must query their own route, admins are allowed
    if role != "admin" and str(identity) != str(id):
        return api_response(False, error="Forbidden: IDOR check failed", status_code=403)
        
    route_info, err = get_worker_route(id)
    if err:
        return api_response(False, error=err, status_code=400)
        
    return api_response(True, data=route_info)

@workers_bp.route("/api/workers/<id>/performance", methods=["GET"])
@jwt_required()
def get_performance_api(id):
    identity = get_jwt_identity()
    claims = get_jwt()
    role = claims.get("role")
    
    if role != "admin" and str(identity) != str(id):
        return api_response(False, error="Forbidden: IDOR check failed", status_code=403)
        
    perf = get_worker_performance(id)
    if perf is None:
        return api_response(False, error="Worker not found", status_code=404)
        
    return api_response(True, data=perf)


# --- Socket.IO Event Handlers ---

@socketio.on("worker_location_update")
def handle_worker_location_update(data):
    """
    Called by workers to submit GPS coordinates every 30s.
    """
    if not isinstance(data, dict):
        return
    worker_id = data.get("worker_id")
    lat = data.get("lat")
    lng = data.get("lng")
    if worker_id and lat is not None and lng is not None:
        update_worker_location(worker_id, lat, lng)

@socketio.on("join_complaint_room")
def handle_join_complaint_room(data):
    """
    Called by users (citizen/worker) to monitor updates on a specific complaint.
    """
    if not isinstance(data, dict):
        return
    complaint_id = data.get("complaint_id")
    if complaint_id:
        room = f"complaint_{complaint_id}"
        join_room(room)

@socketio.on("join_admin_room")
def handle_join_admin_room(data=None):
    """
    Called by admins to register for dashboard broadcasts.
    """
    join_room("admin")
