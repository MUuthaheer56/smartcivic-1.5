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

@workers_bp.route("/api/workers/nearest", methods=["GET"])
@admin_required
def get_nearest_workers_api():
    lat = request.args.get("lat", type=float)
    lng = request.args.get("lng", type=float)
    category = request.args.get("category", "")
    
    if lat is None or lng is None:
        return api_response(False, error="lat and lng parameters are required", status_code=400)
        
    from app.core.complaints.service import get_nearest_available_worker
    data = get_nearest_available_worker(lat, lng, category, db_wrapper.db)
    return api_response(True, data=data)

@workers_bp.route("/api/workers/batch-assign", methods=["POST"])
@admin_required
def batch_assign_api():
    data = request.get_json() or {}
    worker_id = data.get("worker_id")
    complaint_ids = data.get("complaint_ids", [])
    
    if not worker_id or not complaint_ids:
        return api_response(False, error="worker_id and list of complaint_ids required", status_code=400)
        
    # Check max capacity of worker (max 3 active tasks)
    worker = db_wrapper.db.workers.find_one({"_id": ObjectId(worker_id)})
    if not worker:
        return api_response(False, error="Worker not found", status_code=404)
        
    active_count = worker.get("active_tasks_count", 0)
    if active_count + len(complaint_ids) > 3:
        return api_response(False, error="Worker capacity reached maximum limits (3 active tasks max)", status_code=400)

    assigned_count = 0
    from app.core.complaints.service import assign_complaint_worker
    for cid in complaint_ids:
        # Atomic check-and-assign
        res, err = assign_complaint_worker(cid, worker_id)
        if not err:
            assigned_count += 1
            
    return api_response(True, data={"assigned_count": assigned_count})

@workers_bp.route("/api/workers/<id>", methods=["GET"])
@jwt_required()
def get_worker_api(id):
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
    
    if role != "admin" and str(identity) != str(id):
        return api_response(False, error="Forbidden: IDOR check failed", status_code=403)
        
    route_info, err = get_worker_route(id)
    if err:
        return api_response(False, error=err, status_code=400)
        
    return api_response(True, data=route_info)

@workers_bp.route("/api/workers/<id>/schedule", methods=["GET"])
@jwt_required()
def get_worker_schedule_api(id):
    identity = get_jwt_identity()
    claims = get_jwt()
    role = claims.get("role")
    
    if role != "admin" and str(identity) != str(id):
        return api_response(False, error="Forbidden: IDOR check failed", status_code=403)
        
    worker = db_wrapper.db.workers.find_one({"_id": ObjectId(id)})
    if not worker:
        return api_response(False, error="Worker not found", status_code=404)
        
    # Find all active complaints assigned to this worker
    from app.models.complaint import Complaint
    tasks = list(db_wrapper.db.complaints.find({
        "assigned_worker_id": ObjectId(id),
        "status": {"$in": ["ASSIGNED", "IN_PROGRESS", "REOPENED"]}
    }))
    
    # Optimize sequence starting from current worker location
    curr_loc = worker.get("current_location") or {}
    start_lat = curr_loc.get("lat")
    start_lng = curr_loc.get("lng")
    if start_lat is None or start_lng is None:
        return api_response(False, error="Worker current_location (lat, lng) is not available to compute route", status_code=400)
    
    from app.routing.optimizer import optimize_worker_sequence
    ordered = optimize_worker_sequence(float(start_lat), float(start_lng), tasks)
    
    return api_response(True, data=[Complaint.serialize(t) for t in ordered])

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
    if not isinstance(data, dict):
        return
    worker_id = data.get("worker_id")
    lat = data.get("lat")
    lng = data.get("lng")
    if worker_id and lat is not None and lng is not None:
        update_worker_location(worker_id, lat, lng)

@socketio.on("join_complaint_room")
def handle_join_complaint_room(data):
    if not isinstance(data, dict):
        return
    complaint_id = data.get("complaint_id")
    if complaint_id:
        room = f"complaint_{complaint_id}"
        join_room(room)

@socketio.on("join_admin_room")
def handle_join_admin_room(data=None):
    join_room("admin")
