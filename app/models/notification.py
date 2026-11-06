import datetime
from bson import ObjectId

class Notification:
    @staticmethod
    def create(user_id, event_type, message, complaint_id=None):
        now = datetime.datetime.now(datetime.timezone.utc)
        return {
            "user_id": ObjectId(user_id) if isinstance(user_id, str) else user_id,
            "complaint_id": ObjectId(complaint_id) if isinstance(complaint_id, str) else complaint_id,
            "event_type": event_type,
            "message": message,
            "status": "QUEUED",
            "retries": 0,
            "created_at": now,
            "updated_at": now
        }

    @staticmethod
    def serialize(doc):
        if not doc:
            return None
        serialized = dict(doc)
        serialized["_id"] = str(serialized["_id"])
        serialized["user_id"] = str(serialized["user_id"])
        if serialized.get("complaint_id"):
            serialized["complaint_id"] = str(serialized["complaint_id"])
        for field in ["created_at", "updated_at"]:
            if isinstance(serialized.get(field), datetime.datetime):
                serialized[field] = serialized[field].isoformat()
        return serialized
