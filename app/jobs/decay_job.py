from app.civic.civicscore import decay_civic_points

def run_decay_job(db):
    """
    Called monthly by background scheduler.
    """
    try:
        decay_civic_points(db)
        print("[DECAY JOB] Monthly points decay completed successfully.")
    except Exception as e:
        print(f"[DECAY JOB] Error processing points decay: {e}")
