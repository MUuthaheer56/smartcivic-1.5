from flask import Blueprint, request, render_template
from app.utils.response import api_response
from app.utils.auth_decorators import admin_required
from app.core.admin.service import (
    get_admin_queue,
    force_update_complaint,
    get_admin_stats
)
from app.core.complaints.service import get_complaints
from app.core.workers.service import get_workers

admin_bp = Blueprint("admin", __name__)

# --- Jinja2 Page Views ---

@admin_bp.route("/admin/dashboard", methods=["GET"])
@admin_required
def admin_dashboard():
    stats = get_admin_stats()
    # Fetch all complaints to display on map
    all_complaints = get_complaints()
    # Fetch workers to display on admin dashboard
    workers = get_workers()
    
    return render_template(
        "admin/dashboard.html",
        stats=stats,
        complaints=all_complaints,
        workers=workers
    )

@admin_bp.route("/admin/queue", methods=["GET"])
@admin_required
def admin_queue_view():
    queue = get_admin_queue()
    # Fetch all available workers so admin can assign manually
    workers = get_workers({"status": "AVAILABLE"})
    return render_template("admin/queue.html", queue=queue, workers=workers)

@admin_bp.route("/admin/workers", methods=["GET"])
@admin_required
def admin_workers_view():
    workers = get_workers()
    return render_template("admin/workers.html", workers=workers)


# --- REST API Endpoints ---

@admin_bp.route("/api/admin/queue", methods=["GET"])
@admin_required
def list_admin_queue_api():
    queue = get_admin_queue()
    return api_response(True, data=queue)

@admin_bp.route("/api/admin/complaints/<id>", methods=["PATCH"])
@admin_required
def force_update_complaint_api(id):
    data = request.get_json() or {}
    
    complaint, err = force_update_complaint(id, data)
    if err:
        return api_response(False, error=err, status_code=400)
        
    return api_response(True, data=complaint)

@admin_bp.route("/api/admin/stats", methods=["GET"])
@admin_required
def get_admin_stats_api():
    stats = get_admin_stats()
    return api_response(True, data=stats)
