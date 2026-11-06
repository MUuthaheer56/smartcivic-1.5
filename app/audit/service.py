import datetime
import hashlib
import json
from bson import ObjectId

def log_audit(db, user_id: str, action: str, ip_address: str, payload: dict = None, metadata: dict = None):
    """
    Log sensitive operations to audit_logs collection.
    """
    payload_hash = None
    if payload:
        try:
            payload_str = json.dumps(payload, sort_keys=True, default=str)
            payload_hash = hashlib.sha256(payload_str.encode()).hexdigest()
        except Exception:
            pass

    audit_entry = {
        "user_id": ObjectId(user_id) if user_id else None,
        "action": action,
        "timestamp": datetime.datetime.now(datetime.timezone.utc),
        "ip_address": ip_address,
        "payload_hash": payload_hash,
        "metadata": metadata or {}
    }
    
    db.audit_logs.insert_one(audit_entry)
