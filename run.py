import os
from dotenv import load_dotenv

# Load env before importing app
load_dotenv()

from app import create_app
from app.extensions import socketio

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # Using eventlet or standard gevent or development wsgi
    # Flask-SocketIO will automatically select the best worker
    socketio.run(app, host="0.0.0.0", port=port, debug=app.config.get("DEBUG", True))
