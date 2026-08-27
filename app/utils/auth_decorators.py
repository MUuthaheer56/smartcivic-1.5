from functools import wraps
from flask import request, redirect, url_for
from flask_jwt_extended import verify_jwt_in_request, get_jwt
from app.utils.response import api_response

def auth_role_required(allowed_roles, allowed_tiers=None):
    """
    Decorator helper to enforce user roles and tiers.
    Automatically detects API vs Page requests and returns JSON or redirects.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            is_api = request.path.startswith("/api/")
            try:
                # Verify JWT token (Flask-JWT-Extended automatically validates cookies and CSRF tokens)
                verify_jwt_in_request()
                claims = get_jwt()
                role = claims.get("role")
                tier = claims.get("tier", "Reporter")
                
                # Role and tier checks
                if role not in allowed_roles:
                    if is_api:
                        return api_response(False, error="Forbidden: Access denied for this role", status_code=403)
                    return redirect("/")
                    
                if allowed_tiers and tier not in allowed_tiers:
                    if is_api:
                        return api_response(False, error="Forbidden: Higher tier required", status_code=403)
                    return redirect("/")
            except Exception as e:
                if is_api:
                    return api_response(False, error=f"Unauthorized: {str(e)}", status_code=401)
                return redirect("/login")
                
            return fn(*args, **kwargs)
        return wrapper
    return decorator

# Specific role decorators
def citizen_required(fn):
    return auth_role_required(["citizen"])(fn)

def worker_required(fn):
    return auth_role_required(["worker"])(fn)

def admin_required(fn):
    return auth_role_required(["admin"])(fn)

def verifier_required(fn):
    return auth_role_required(["citizen"], ["Verifier", "Ward Guardian"])(fn)
