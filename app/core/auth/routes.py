from flask import Blueprint, request, render_template, redirect, url_for
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    set_access_cookies,
    set_refresh_cookies,
    unset_jwt_cookies,
    jwt_required,
    get_jwt_identity,
    get_jwt,
    verify_jwt_in_request
)
from app.extensions import limiter, db_wrapper
from app.utils.response import api_response
from app.core.auth.service import register_user, authenticate_user
from app.models.user import User
from app.models.worker import Worker
from bson import ObjectId

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["GET"])
def login_view():
    # If already logged in, redirect to index (which routes to dashboards)
    try:
        verify_jwt_in_request(optional=True)
        if get_jwt_identity():
            return redirect("/")
    except Exception:
        pass
    return render_template("login.html")

@auth_bp.route("/register", methods=["GET"])
def register_view():
    try:
        verify_jwt_in_request(optional=True)
        if get_jwt_identity():
            return redirect("/")
    except Exception:
        pass
    return render_template("register.html")

@auth_bp.route("/logout", methods=["GET"])
def logout_view():
    resp = redirect(url_for("auth.login_view"))
    unset_jwt_cookies(resp)
    return resp

# Rate limit: 5 attempts per 15 minutes per IP
@auth_bp.route("/api/auth/register", methods=["POST"])
@limiter.limit("5 per 15 minutes")
def register():
    data = request.get_json() or {}
    name = data.get("name", "")
    email = data.get("email", "")
    phone = data.get("phone", "")
    password = data.get("password", "")
    ward = data.get("ward", "")
    role = data.get("role", "citizen")
    department = data.get("department", "General")
    
    user, err = register_user(name, email, phone, password, ward, role, department)
    if err:
        return api_response(False, error=err, status_code=400)
        
    # Generate tokens
    user_id = user["_id"]
    tier = user.get("tier", "Reporter")
    access_token = create_access_token(identity=user_id, additional_claims={"role": role, "tier": tier})
    refresh_token = create_refresh_token(identity=user_id, additional_claims={"role": role, "tier": tier})
    
    resp, code = api_response(True, data={"user": user, "role": role}, status_code=201)
    set_access_cookies(resp, access_token)
    set_refresh_cookies(resp, refresh_token)
    return resp, code

# Rate limit: 5 attempts per 15 minutes per IP
@auth_bp.route("/api/auth/login", methods=["POST"])
@limiter.limit("5 per 15 minutes")
def login():
    data = request.get_json() or {}
    email = data.get("email", "")
    password = data.get("password", "")
    
    user, err, role = authenticate_user(email, password)
    if err:
        return api_response(False, error=err, status_code=401)
        
    # Generate tokens
    user_id = user["_id"]
    tier = user.get("tier", "Reporter")
    access_token = create_access_token(identity=user_id, additional_claims={"role": role, "tier": tier})
    refresh_token = create_refresh_token(identity=user_id, additional_claims={"role": role, "tier": tier})
    
    resp, code = api_response(True, data={"user": user, "role": role}, status_code=200)
    set_access_cookies(resp, access_token)
    set_refresh_cookies(resp, refresh_token)
    return resp, code

@auth_bp.route("/api/auth/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh_token_endpoint():
    user_id = get_jwt_identity()
    claims = get_jwt()
    role = claims.get("role", "citizen")
    tier = claims.get("tier", "Reporter")
    
    # Generate new access token
    new_access_token = create_access_token(identity=user_id, additional_claims={"role": role, "tier": tier})
    resp, code = api_response(True, data={"message": "Token refreshed"}, status_code=200)
    set_access_cookies(resp, new_access_token)
    return resp, code

@auth_bp.route("/api/auth/logout", methods=["POST"])
def logout_api():
    resp, code = api_response(True, data={"message": "Logged out successfully"}, status_code=200)
    unset_jwt_cookies(resp)
    return resp, code

@auth_bp.route("/api/auth/me", methods=["GET"])
@jwt_required()
def me():
    user_id = get_jwt_identity()
    claims = get_jwt()
    role = claims.get("role")
    
    if role == "worker":
        user_doc = db_wrapper.db.workers.find_one({"_id": ObjectId(user_id)})
        serialized = Worker.serialize(user_doc)
    else:
        user_doc = db_wrapper.db.users.find_one({"_id": ObjectId(user_id)})
        serialized = User.serialize(user_doc)
        
    if not serialized:
        return api_response(False, error="User not found", status_code=404)
        
    return api_response(True, data={"user": serialized, "role": role})
