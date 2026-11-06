from app.ai.tasks import process_complaint_ai
from app.extensions import socketio

def run_ai_queue_audit_job(db, upload_folder):
    """
    Background job to process any stuck AI_QUEUED complaints.
    """
    stuck_complaints = list(db.complaints.find({"status": "AI_QUEUED"}))
    for c in stuck_complaints:
        complaint_id = str(c["_id"])
        print(f"[AI QUEUE AUDIT] Processing stuck complaint {complaint_id}")
        process_complaint_ai(complaint_id, db, socketio, upload_folder)
