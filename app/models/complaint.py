import datetime
from bson import ObjectId
from config import SLA_HOURS

class Complaint:
    @staticmethod
    def create(citizen_id, ward, category, subcategory, description, lat, lng, address, image_path=None, severity_score=5.0, priority="MEDIUM"):
        now = datetime.datetime.now(datetime.timezone.utc)
        sla_h = SLA_HOURS.get(category, 72)
        deadline = now + datetime.timedelta(hours=sla_h)
        
        return {
            "citizen_id": ObjectId(citizen_id) if citizen_id else None,
            "ward": ward.strip(),
            "category": category,
            "subcategory": subcategory.strip(),
            "description": description.strip(),
            "location": {
                "lat": float(lat),
                "lng": float(lng),
                "address": address.strip()
            },
            "status": "REPORTED",
            "priority": priority,
            "severity_score": float(severity_score),
            "sla_hours": sla_h,
            "sla_deadline": deadline,
            "sla_breached": False,
            "assigned_worker_id": None,
            "assigned_department": None,
            "image_path": image_path,
            "tags": [],
            "ai_confidence": None,
            "civic_confidence": None,
            "routing_status": None,
            "verification_votes": [],
            "verification_result": None,
            "before_image_path": image_path, # same as original image path for now
            "after_image_path": None,
            "repair_result": None,
            "first_response_at": None,
            "resolved_at": None,
            "created_at": now,
            "updated_at": now
        }

    @staticmethod
    def serialize(doc):
        if not doc:
            return None
        serialized = dict(doc)
        serialized["_id"] = str(serialized["_id"])
        
        if serialized.get("citizen_id"):
            serialized["citizen_id"] = str(serialized["citizen_id"])
        if serialized.get("assigned_worker_id"):
            serialized["assigned_worker_id"] = str(serialized["assigned_worker_id"])
            
        # Serialize datetimes
        for field in ["sla_deadline", "first_response_at", "resolved_at", "created_at", "updated_at"]:
            if isinstance(serialized.get(field), datetime.datetime):
                serialized[field] = serialized[field].isoformat()
                
        # Serialize votes
        votes = []
        for v in serialized.get("verification_votes", []):
            vote_dict = dict(v)
            if "user_id" in vote_dict:
                vote_dict["user_id"] = str(vote_dict["user_id"])
            if isinstance(vote_dict.get("voted_at"), datetime.datetime):
                vote_dict["voted_at"] = vote_dict["voted_at"].isoformat()
            votes.append(vote_dict)
        serialized["verification_votes"] = votes
        
        return serialized
