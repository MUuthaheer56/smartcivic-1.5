import os
from flask import Flask, redirect, url_for, make_response
from flask_jwt_extended import get_jwt, verify_jwt_in_request
from app.extensions import db_wrapper, jwt, limiter, socketio

def create_app(config_class="config.Config"):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize Extensions
    db_wrapper.init_app(app)
    jwt.init_app(app)
    limiter.init_app(app)
    socketio.init_app(app)
    
    # Create static upload folder if it doesn't exist
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    
    # Configure MongoDB indexes (unique emails)
    with app.app_context():
        try:
            db_wrapper.db.users.create_index("email", unique=True)
            db_wrapper.db.workers.create_index("email", unique=True)
        except Exception as e:
            app.logger.warning(f"Could not create database indexes: {e}")
            
    # Register Blueprints
    from app.core.auth.routes import auth_bp
    from app.core.complaints.routes import complaints_bp
    from app.core.workers.routes import workers_bp
    from app.core.admin.routes import admin_bp
    from app.core.maps.routes import maps_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(complaints_bp)
    app.register_blueprint(workers_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(maps_bp)
    
    # Default redirect route
    @app.route("/")
    def index():
        # Check if user is authenticated via cookies
        try:
            verify_jwt_in_request(optional=True)
            claims = get_jwt()
            if claims and "role" in claims:
                role = claims["role"]
                if role == "admin":
                    return redirect("/admin/dashboard")
                elif role == "worker":
                    return redirect("/worker/dashboard")
                elif role == "citizen":
                    return redirect("/citizen/dashboard")
        except Exception:
            pass
        return redirect("/login")
        
    @app.route("/login")
    def login_page():
        return app.send_static_file("login.html") or redirect(url_for("auth.login_view"))

    @app.route("/register")
    def register_page():
        return redirect(url_for("auth.register_view"))

    # Security Headers Middleware
    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response
        
    return app
