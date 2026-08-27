import datetime
from app.extensions import db_wrapper
from app.models.user import User, verify_password
from app.models.worker import Worker
from app.utils.validators import validate_email, validate_phone, validate_password

def register_user(name, email, phone, password, ward, role, department="General"):
    # Perform field-level checks
    email = email.strip().lower()
    phone = phone.strip()
    
    ok, err = validate_email(email)
    if not ok:
        return None, err
    ok, err = validate_phone(phone)
    if not ok:
        return None, err
    ok, err = validate_password(password)
    if not ok:
        return None, err
        
    if not name or len(name.strip()) < 2:
        return None, "Name must be at least 2 characters long"
    if not ward or len(ward.strip()) < 2:
        return None, "Ward is required"
        
    if role not in ["citizen", "worker", "admin"]:
        return None, "Invalid role specified"
        
    # Ensure email uniqueness across both collections
    if db_wrapper.db.users.find_one({"email": email}) or db_wrapper.db.workers.find_one({"email": email}):
        return None, "Email address is already registered"
        
    # Create respective database document
    if role == "worker":
        user_doc = Worker.create(name, email, phone, password, department, ward)
        db_wrapper.db.workers.insert_one(user_doc)
        serialized = Worker.serialize(user_doc)
    else:
        user_doc = User.create(name, email, phone, password, ward, role)
        db_wrapper.db.users.insert_one(user_doc)
        serialized = User.serialize(user_doc)
        
    return serialized, None

def authenticate_user(email, password):
    email = email.strip().lower()
    
    # Try citizen/admin collection
    user_doc = db_wrapper.db.users.find_one({"email": email})
    role = None
    
    if user_doc:
        role = user_doc.get("role", "citizen")
        is_verified = verify_password(user_doc["password_hash"], password)
        if not is_verified:
            return None, "Invalid password", None
        
        # Update last active timestamp
        db_wrapper.db.users.update_one(
            {"_id": user_doc["_id"]},
            {"$set": {"last_active": datetime.datetime.now(datetime.timezone.utc)}}
        )
        serialized = User.serialize(user_doc)
        return serialized, None, role

    # Try worker collection
    worker_doc = db_wrapper.db.workers.find_one({"email": email})
    if worker_doc:
        role = "worker"
        is_verified = verify_password(worker_doc["password_hash"], password)
        if not is_verified:
            return None, "Invalid password", None
            
        # Update last active equivalent or worker info if needed
        serialized = Worker.serialize(worker_doc)
        return serialized, None, role
        
    return None, "User not found with this email", None
