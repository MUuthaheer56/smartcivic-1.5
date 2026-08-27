from bson import ObjectId
from app.extensions import db_wrapper, socketio
from app.models.worker import Worker
from app.models.complaint import Complaint
from app.core.maps.service import get_route

def get_workers(filters=None):
    query = {}
    if filters:
        if filters.get("ward"):
            query["ward"] = filters["ward"]
        if filters.get("department"):
            query["department"] = filters["department"]
        if filters.get("status"):
            query["status"] = filters["status"]
            
    docs = db_wrapper.db.workers.find(query)
    return [Worker.serialize(d) for d in docs]

def get_worker_by_id(worker_id):
    try:
        doc = db_wrapper.db.workers.find_one({"_id": ObjectId(worker_id)})
        return Worker.serialize(doc)
    except Exception:
        return None

def update_worker_location(worker_id, lat, lng):
    try:
        lat = float(lat)
        lng = float(lng)
        
        # Verify Bengaluru bounds
        if not (12.8 <= lat <= 13.2) or not (77.4 <= lng <= 77.8):
            return False, "Location outside Bengaluru bounds"
            
        worker_oid = ObjectId(worker_id)
        db_wrapper.db.workers.update_one(
            {"_id": worker_oid},
            {"$set": {"current_location": {"lat": lat, "lng": lng}}}
        )
        
        # Broadcast location update to admin room
        socketio.emit("worker_location", {
            "worker_id": str(worker_id),
            "lat": lat,
            "lng": lng
        }, to="admin")
        
        return True, None
    except Exception as e:
        return False, str(e)

def get_worker_route(worker_id):
    try:
        worker = db_wrapper.db.workers.find_one({"_id": ObjectId(worker_id)})
        if not worker:
            return None, "Worker not found"
            
        active_complaint_id = worker.get("active_complaint_id")
        if not active_complaint_id:
            return None, "No active complaint assigned to worker"
            
        complaint = db_wrapper.db.complaints.find_one({"_id": active_complaint_id})
        if not complaint:
            return None, "Active complaint not found"
            
        curr_loc = worker.get("current_location")
        if not curr_loc or "lat" not in curr_loc or "lng" not in curr_loc:
            # Fallback to general center if worker location is not recorded yet
            curr_loc = {"lat": 12.9716, "lng": 77.5946}
            
        dest_loc = complaint.get("location")
        if not dest_loc or "lat" not in dest_loc or "lng" not in dest_loc:
            return None, "Complaint coordinates are missing"
            
        route_data = get_route(
            origin_lat=curr_loc["lat"],
            origin_lng=curr_loc["lng"],
            dest_lat=dest_loc["lat"],
            dest_lng=dest_loc["lng"]
        )
        
        if not route_data:
            return None, "Unable to compute route from OSRM"
            
        return {
            "route": route_data,
            "complaint": Complaint.serialize(complaint)
        }, None
        
    except Exception as e:
        return None, str(e)

def get_worker_performance(worker_id):
    worker = get_worker_by_id(worker_id)
    if not worker:
         return None
    return worker.get("performance", {})
