import datetime
from bson import ObjectId
from argon2 import PasswordHasher

ph = PasswordHasher()

def hash_password(password: str) -> str:
    return ph.hash(password)

def verify_password(password_hash: str, password: str) -> bool:
    try:
        return ph.verify(password_hash, password)
    except Exception:
        return False

class User:
    @staticmethod
    def create(name, email, phone, password, ward, role="citizen"):
        now = datetime.datetime.now(datetime.timezone.utc)
        return {
            "name": name,
            "email": email.strip().lower(),
            "phone": phone.strip(),
            "password_hash": hash_password(password),
            "role": role,
            "ward": ward.strip(),
            "civic_score": 0.0,
            "tier": "Reporter",
            "is_anonymous_allowed": False,
            "contribution_history": [],
            "created_at": now,
            "last_active": now
        }

    @staticmethod
    def serialize(user_doc):
        if not user_doc:
            return None
        doc = dict(user_doc)
        doc["_id"] = str(doc["_id"])
        # Do not leak password hash
        if "password_hash" in doc:
            del doc["password_hash"]
        # Serialize datetimes
        if isinstance(doc.get("created_at"), datetime.datetime):
            doc["created_at"] = doc["created_at"].isoformat()
        if isinstance(doc.get("last_active"), datetime.datetime):
            doc["last_active"] = doc["last_active"].isoformat()
        return doc
