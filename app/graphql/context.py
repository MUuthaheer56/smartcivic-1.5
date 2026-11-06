from typing import Optional, Dict, Any
from flask_jwt_extended import decode_token
from app.extensions import db_wrapper

def get_graphql_context(request) -> Dict[str, Any]:
    """
    Extracts authentication context from incoming request headers or cookies.
    Provides user identity, role, and database connection to resolvers.
    """
    user = None
    token = None

    # 1. Bearer token in Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    
    # 2. JWT cookie fallback
    if not token:
        token = request.cookies.get("access_token_cookie")

    if token:
        try:
            decoded = decode_token(token)
            user_id = decoded.get("sub")
            role = decoded.get("role")
            tier = decoded.get("tier", "STANDARD")
            
            # Fetch user or worker profile details
            profile = None
            if role == "worker":
                profile = db_wrapper.db.workers.find_one({"_id": user_id})
                if not profile:
                    try:
                        from bson import ObjectId
                        profile = db_wrapper.db.workers.find_one({"_id": ObjectId(user_id)})
                    except Exception:
                        pass
            else:
                profile = db_wrapper.db.users.find_one({"_id": user_id})
                if not profile:
                    try:
                        from bson import ObjectId
                        profile = db_wrapper.db.users.find_one({"_id": ObjectId(user_id)})
                    except Exception:
                        pass

            ward = profile.get("ward") if profile else None
            user = {
                "id": str(user_id),
                "role": role,
                "tier": tier,
                "ward": ward,
                "profile": profile,
                "claims": decoded
            }
        except Exception:
            user = None

    return {
        "user": user,
        "db": db_wrapper.db,
        "request": request
    }

def require_auth(info) -> Dict[str, Any]:
    """Enforce authentication on resolvers."""
    user = info.context.get("user")
    if not user:
        raise PermissionError("Authentication required: Please provide a valid Bearer token or session cookie.")
    return user

def require_roles(info, allowed_roles: list) -> Dict[str, Any]:
    """Enforce role-based access control (RBAC)."""
    user = require_auth(info)
    if user.get("role") not in allowed_roles:
        raise PermissionError(f"Access denied: Role '{user.get('role')}' is not authorized for this operation.")
    return user

