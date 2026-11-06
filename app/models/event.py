import datetime
from bson import ObjectId

class ComplaintEvent:
    @staticmethod
    def create(complaint_id, event_type, actor_id=None, actor_role=None, from_status=None, to_status=None, detail=None):
        return {
            "complaint_id": ObjectId(complaint_id) if isinstance(complaint_id, str) else complaint_id,
            "timestamp": datetime.datetime.now(datetime.timezone.utc),
            "event_type": event_type,
            "actor_id": ObjectId(actor_id) if isinstance(actor_id, str) else actor_id,
            "actor_role": actor_role,
            "from_status": from_status,
            "to_status": to_status,
            "detail": detail or {}
        }

    @staticmethod
    def serialize(doc):
        if not doc:
            return None
        serialized = dict(doc)
        if "_id" in serialized:
            serialized["_id"] = str(serialized["_id"])
        if serialized.get("complaint_id"):
            serialized["complaint_id"] = str(serialized["complaint_id"])
        if serialized.get("actor_id"):
            serialized["actor_id"] = str(serialized["actor_id"])
        if isinstance(serialized.get("timestamp"), datetime.datetime):
            serialized["timestamp"] = serialized["timestamp"].isoformat()
        return serialized
