from flask import Blueprint, request, render_template
from app.utils.response import api_response
from app.utils.auth_decorators import admin_required
from app.extensions import db_wrapper
from app.core.admin.service import (
    get_admin_queue,
    force_update_complaint,
    get_admin_stats
)
from app.core.complaints.service import get_complaints
from app.core.workers.service import get_workers
from bson import ObjectId

admin_bp = Blueprint("admin", __name__)

# --- Jinja2 Page Views ---

@admin_bp.route("/admin/dashboard", methods=["GET"])
@admin_required
def admin_dashboard():
    stats = get_admin_stats()
    all_complaints = get_complaints()
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


# --- 1.6 Analytics & Dashboards Routes ---

@admin_bp.route("/api/admin/analytics/heatmap", methods=["GET"])
@admin_required
def heatmap_api():
    from app.analytics.heatmap import get_heatmap_data
    category = request.args.get("category")
    severity = request.args.get("severity")
    ward = request.args.get("ward")
    status = request.args.get("status")
    
    data = get_heatmap_data(db_wrapper.db, category, severity, ward, status)
    return api_response(True, data=data)

@admin_bp.route("/api/admin/analytics/drain-risk", methods=["GET"])
@admin_required
def drain_risk_api():
    data = list(db_wrapper.db.drain_risk.find({}, {"_id": 0}).sort("risk_score", -1))
    return api_response(True, data=data)

@admin_bp.route("/api/admin/analytics/coordination-failures", methods=["GET"])
@admin_required
def coordination_failures_api():
    data = list(db_wrapper.db.coordination_failures.find({}, {"_id": 0}).sort("cfi_score", -1))
    return api_response(True, data=data)

@admin_bp.route("/api/admin/analytics/ward-trust", methods=["GET"])
@admin_required
def ward_trust_api():
    data = list(db_wrapper.db.ward_trust_scores.find({}, {"_id": 0}).sort("trust_score", -1))
    return api_response(True, data=data)

@admin_bp.route("/api/admin/analytics/civicpulse", methods=["GET"])
@admin_required
def civicpulse_api():
    data = list(db_wrapper.db.civicpulse_risk.find({}, {"_id": 0}).sort("risk_score", -1))
    return api_response(True, data=data)

@admin_bp.route("/api/admin/analytics/animal-hotspots", methods=["GET"])
@admin_required
def animal_hotspots_api():
    data = list(db_wrapper.db.animal_hotspots.find({}, {"_id": 0}).sort("hotspot_score", -1))
    return api_response(True, data=data)

@admin_bp.route("/api/admin/analytics/ward-health", methods=["GET"])
@admin_required
def ward_health_api():
    from app.analytics.ward_health import compute_all_ward_health
    data = compute_all_ward_health(db_wrapper.db)
    return api_response(True, data=data)

@admin_bp.route("/api/admin/analytics/worker-performance", methods=["GET"])
@admin_required
def worker_performance_api():
    from app.analytics.worker_perf import compute_all_worker_performance
    data = compute_all_worker_performance(db_wrapper.db)
    return api_response(True, data=data)

@admin_bp.route("/api/admin/analytics/worker-performance/<worker_id>", methods=["GET"])
@admin_required
def single_worker_performance_api(worker_id):
    from app.analytics.worker_perf import compute_worker_performance
    try:
        data = compute_worker_performance(worker_id, db_wrapper.db)
        return api_response(True, data=data)
    except Exception as e:
        return api_response(False, error=str(e), status_code=400)

@admin_bp.route("/api/admin/analytics/ward-report/<ward>", methods=["GET"])
@admin_required
def ward_monthly_report_api(ward):
    from app.analytics.ward_reports import generate_ward_monthly_report
    try:
        data = generate_ward_monthly_report(ward, db_wrapper.db)
        return api_response(True, data=data)
    except Exception as e:
        return api_response(False, error=str(e), status_code=400)

@admin_bp.route("/api/admin/analytics/surge-risk/<ward>", methods=["GET"])
@admin_required
def ward_surge_risk_api(ward):
    from app.analytics.risk import forecast_complaint_surge
    try:
        data = forecast_complaint_surge(ward, db_wrapper.db)
        return api_response(True, data=data)
    except Exception as e:
        return api_response(False, error=str(e), status_code=400)

@admin_bp.route("/api/admin/analytics/infra-failure", methods=["GET"])
@admin_required
def infra_failure_api():
    from app.analytics.infrastructure import predict_infrastructure_failure
    lat = request.args.get("lat", 12.9716, type=float)
    lng = request.args.get("lng", 77.5946, type=float)
    try:
        data = predict_infrastructure_failure(lat, lng, db_wrapper.db)
        return api_response(True, data=data)
    except Exception as e:
        return api_response(False, error=str(e), status_code=400)
