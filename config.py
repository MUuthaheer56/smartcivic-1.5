import os
from datetime import timedelta

# SLA Rules (in hours)
SLA_HOURS = {
    "Road Damage":          48,
    "Waste Management":     24,
    "Stray Animal":         12,
    "Noise":                24,
    "Footpath":             72,
    "Construction Hazard":  6,
    "Streetlight":          48,
    "Drainage":             24,
    "Lake Encroachment":    12,
    "Other":                72
}

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-smartcivic")
    
    # MongoDB Config
    MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/smartcivic")
    
    # JWT Config
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "jwt-secret-key-smartcivic")
    JWT_TOKEN_LOCATION = ["cookies"]
    JWT_COOKIE_SECURE = False  # Disabled for local HTTP development. Set to True in production.
    JWT_COOKIE_SAMESITE = "Strict"
    
    # JWT Expire times
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)
    
    # JWT Cookie settings
    JWT_ACCESS_COOKIE_NAME = "access_token"
    JWT_REFRESH_COOKIE_NAME = "refresh_token"
    
    # JWT CSRF settings
    JWT_COOKIE_CSRF_PROTECT = True
    JWT_CSRF_IN_COOKIES = True
    JWT_ACCESS_CSRF_HEADER_NAME = "X-CSRF-Token"
    JWT_REFRESH_CSRF_HEADER_NAME = "X-CSRF-Token"
    JWT_ACCESS_CSRF_COOKIE_NAME = "csrf_access_token"
    JWT_REFRESH_CSRF_COOKIE_NAME = "csrf_refresh_token"
    
    # File upload settings
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "static", "uploads")
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB
    
    # OSRM config
    OSRM_BASE = "http://router.project-osrm.org"
