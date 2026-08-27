import datetime
from bson import ObjectId
from app.models.user import hash_password

class Worker:
    @staticmethod
    def create(name, email, phone, password, department, ward):
        now = datetime.datetime.now(datetime.timezone.utc)
        return {
            "name": name,
            "email": email.strip().lower(),
            "phone": phone.strip(),
            "password_hash": hash_password(password),
            "department": department.strip(),
            "ward": ward.strip(),
            "current_location": None,
            "status": "AVAILABLE",
            "active_complaint_id": None,
            "performance": {
                "assigned": 0,
                "completed": 0,
                "avg_resolution_days": 0.0,
                "sla_compliance": 100.0,
                "reopened": 0,
                "score": 100.0
            },
            "created_at": now
        }

    @staticmethod
    def serialize(doc):
        if not doc:
            return None
        serialized = dict(doc)
        serialized["_id"] = str(serialized["_id"])
        
        # Strip password hash
        if "password_hash" in serialized:
            del serialized["password_hash"]
            
        if serialized.get("active_complaint_id"):
            serialized["active_complaint_id"] = str(serialized["active_complaint_id"])
            
        if isinstance(serialized.get("created_at"), datetime.datetime):
            serialized["created_at"] = serialized["created_at"].isoformat()
            
        return serialized
