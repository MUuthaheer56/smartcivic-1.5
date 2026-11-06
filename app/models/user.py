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
            
            # 1.6 OTP & Security Verification fields
            "is_verified": False,
            "otp_code": None,
            "otp_expires_at": None,
            "failed_logins": 0,
            "lockout_until": None,
            
            "created_at": now,
            "last_active": now
        }

    @staticmethod
    def serialize(user_doc):
        if not user_doc:
            return None
        doc = dict(user_doc)
        doc["_id"] = str(doc["_id"])
        # Do not leak password hash or OTP secrets
        if "password_hash" in doc:
            del doc["password_hash"]
        if "otp_code" in doc:
            del doc["otp_code"]
        # Serialize datetimes
        for field in ["created_at", "last_active", "otp_expires_at", "lockout_until"]:
            if isinstance(doc.get(field), datetime.datetime):
                doc[field] = doc[field].isoformat()
        return doc
