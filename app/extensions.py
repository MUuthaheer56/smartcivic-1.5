from pymongo import MongoClient
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_socketio import SocketIO

# Raw MongoDB PyMongo extension wrapper
class PyMongoExtension:
    def __init__(self):
        self.client = None
        self.db = None

    def init_app(self, app):
        mongo_uri = app.config.get("MONGO_URI", "mongodb://localhost:27017/smartcivic")
        # Initialize raw MongoClient
        self.client = MongoClient(mongo_uri)
        # Parse database name from URI path, default to 'smartcivic'
        db_name = mongo_uri.split("/")[-1].split("?")[0]
        if not db_name:
            db_name = "smartcivic"
        self.db = self.client[db_name]

# Instantiate extensions
db_wrapper = PyMongoExtension()
jwt = JWTManager()

# Initialize Flask-Limiter. It uses default in-memory storage.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri="memory://"
)

# Initialize SocketIO with support for cross-origin socket connections
socketio = SocketIO(cors_allowed_origins="*")
