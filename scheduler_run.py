import os
import time
from dotenv import load_dotenv
from pymongo import MongoClient
from app.jobs.scheduler import start_scheduler

load_dotenv()

class RawDbWrapper:
    def __init__(self):
        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/smartcivic")
        self.client = MongoClient(mongo_uri)
        db_name = mongo_uri.split("/")[-1].split("?")[0]
        if not db_name:
            db_name = "smartcivic"
        self.db = self.client[db_name]

if __name__ == "__main__":
    print("[SCHEDULER PROCESS] Initializing raw database wrapper...")
    db_wrapper = RawDbWrapper()
    print("[SCHEDULER PROCESS] Starting scheduler engine...")
    scheduler = start_scheduler(db_wrapper.db)
    print("[SCHEDULER PROCESS] Running. Press Ctrl+C to exit.")
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        print("[SCHEDULER PROCESS] Shutting down scheduler...")
        scheduler.shutdown()
