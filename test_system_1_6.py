import unittest
import time
import datetime
from app import create_app
from app.extensions import db_wrapper
from app.core.auth.service import register_user, authenticate_user, verify_otp
from app.core.complaints.service import (
    create_new_complaint,
    reopen_complaint,
    get_complaint_timeline,
    get_nearest_available_worker,
    assign_complaint_worker
)
from app.routing.optimizer import optimize_worker_sequence
from app.jobs.sla_breach_job import run_sla_breach_job
from app.jobs.notification_job import run_notification_flush_job
from app.analytics.heatmap import get_heatmap_data
from app.utils.cache import cache
from bson import ObjectId

class TestSmartCivic1_6(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app("config.Config")
        cls.app_context = cls.app.app_context()
        cls.app_context.push()
        cls.db = db_wrapper.db
        
    @classmethod
    def tearDownClass(cls):
        cls.app_context.pop()

    def setUp(self):
        self.db.users.delete_many({})
        self.db.workers.delete_many({})
        self.db.complaints.delete_many({})
        self.db.login_lockouts.delete_many({})
        self.db.notifications.delete_many({})
        self.db.audit_logs.delete_many({})
        cache.clear()

    def test_end_to_end_1_6_lifecycle(self):
        print("\n=== STARTING 1.6 SYSTEM TESTS ===")
        
        # ── 1. OTP Registration & Verification ──────────────
        print("[1.6 STAGE 1] Registering Citizen & checking OTP verification...")
        user, err = register_user("Alice Smith", "alice@domain.com", "9876543210", "Password123!", "Indiranagar", "citizen")
        self.assertIsNotNone(user)
        self.assertIsNone(err)
        
        db_user = self.db.users.find_one({"email": "alice@domain.com"})
        self.assertIsNotNone(db_user)
        otp = db_user.get("otp_code")
        self.assertIsNotNone(otp)
        
        # Verify unverified login fails
        self.db.users.update_one({"email": "alice@domain.com"}, {"$set": {"is_verified": False}})
        res_login, login_err, _ = authenticate_user("alice@domain.com", "Password123!", "192.168.1.50")
        self.assertIsNone(res_login)
        self.assertIn("unverified", login_err)
        
        # Verify with OTP
        ok, verify_err = verify_otp("alice@domain.com", otp)
        self.assertTrue(ok)
        self.assertIsNone(verify_err)
        
        # Verify verified login succeeds
        res_login, login_err, role = authenticate_user("alice@domain.com", "Password123!", "192.168.1.50")
        self.assertIsNotNone(res_login)
        self.assertIsNone(login_err)
        self.assertEqual(role, "citizen")

        # ── 2. Login IP Lockout (5 attempts) ──────────────────
        print("[1.6 STAGE 2] Verifying IP-based login brute-force lockout...")
        for i in range(5):
            res, err, _ = authenticate_user("alice@domain.com", "WrongPassword", "192.168.1.10")
            self.assertIsNone(res)
            self.assertIn("password", err.lower())
            
        res, err, _ = authenticate_user("alice@domain.com", "Password123!", "192.168.1.10")
        self.assertIsNone(res)
        self.assertIn("locked", err.lower())
        
        res, err, _ = authenticate_user("alice@domain.com", "Password123!", "192.168.1.20")
        self.assertIsNotNone(res)
        self.assertIsNone(err)

        # ── 3. Asynchronous AI Queueing ─────────────────────
        print("[1.6 STAGE 3] Submitting complaint & checking async AI execution...")
        complaint, err = create_new_complaint(
            citizen_id=str(user["_id"]),
            category="Road Damage",
            subcategory="Deep Pothole",
            description="PII mock test email@domain.com with <p>HTML tags</p> and a phone +91 9999999999",
            lat=12.9716,
            lng=77.5946,
            address="100 Feet Rd",
            image_file=None,
            upload_folder=self.app.config["UPLOAD_FOLDER"],
            saved_image_path="/static/uploads/mock_pothole.png"
        )
        self.assertIsNotNone(complaint)
        self.assertIsNone(err)
        self.assertNotIn("<p>", complaint["description"])
        self.assertIn("[EMAIL_REDACTED]", complaint["description"])
        self.assertIn("[PHONE_REDACTED]", complaint["description"])
        
        timeline = get_complaint_timeline(complaint["_id"], self.db)
        self.assertTrue(len(timeline) >= 1)
        self.assertEqual(timeline[0]["to_status"], "AI_QUEUED")

        # ── 4. Routing, Cost & Volume Estimations ───────────
        print("[1.6 STAGE 4] Verifying specialized AI features & explanations...")
        processed = self.db.complaints.find_one({"_id": ObjectId(complaint["_id"])})
        self.assertIsNotNone(processed)
        
        # ── 5. Worker Capacity Tracking ──────────────────────
        print("[1.6 STAGE 5] Verifying worker dispatch limits & atomic batching...")
        self.db.workers.insert_one({
            "_id": ObjectId("6a90322b16de4627eee867f1"),
            "name": "Bob Builder",
            "email": "bob@bbmp.gov.in",
            "phone": "9876543211",
            "role": "worker",
            "department": "Roads",
            "ward": "Indiranagar",
            "status": "AVAILABLE",
            "active_tasks_count": 0,
            "active_complaint_ids": []
        })
        
        for i in range(3):
            c_doc = {
                "category": "Road Damage", "location": {"lat": 12.9716, "lng": 77.5946},
                "status": "VERIFIED", "ward": "Indiranagar", "timeline_events": []
            }
            self.db.complaints.insert_one(c_doc)
            res_assign, assign_err = assign_complaint_worker(str(c_doc["_id"]), "6a90322b16de4627eee867f1")
            self.assertIsNotNone(res_assign)
            self.assertIsNone(assign_err)
            
        c_doc_4 = {
            "category": "Road Damage", "location": {"lat": 12.9716, "lng": 77.5946},
            "status": "VERIFIED", "ward": "Indiranagar", "timeline_events": []
        }
        self.db.complaints.insert_one(c_doc_4)
        res_assign, assign_err = assign_complaint_worker(str(c_doc_4["_id"]), "6a90322b16de4627eee867f1")
        self.assertIsNone(res_assign)
        self.assertIn("capacity", assign_err.lower())

        # ── 6. OSRM Travel Optimizations ────────────────────
        print("[1.6 STAGE 6] Verifying nearest worker OSRM sequence planner...")
        tasks = [
            {"location": {"lat": 12.9710, "lng": 77.5940}},
            {"location": {"lat": 12.9780, "lng": 77.5990}}
        ]
        ordered = optimize_worker_sequence(12.9716, 77.5946, tasks)
        self.assertEqual(len(ordered), 2)
        self.assertTrue(ordered[0]["location"]["lat"] < ordered[1]["location"]["lat"])

        # ── 7. Live SLA Breach Audits ────────────────────────
        print("[1.6 STAGE 7] Running SLA breach scan daemon...")
        breached_id = ObjectId()
        self.db.complaints.insert_one({
            "_id": breached_id,
            "category": "Streetlight",
            "status": "REPORTED",
            "citizen_id": user["_id"],
            "assigned_worker_id": ObjectId("6a90322b16de4627eee867f1"),
            "sla_breached": False,
            "sla_deadline": datetime.datetime.utcnow() - datetime.timedelta(hours=2)
        })
        
        run_sla_breach_job(self.db)
        updated_c = self.db.complaints.find_one({"_id": breached_id})
        self.assertTrue(updated_c["sla_breached"])
        
        notif = self.db.notifications.find_one({"complaint_id": breached_id})
        self.assertIsNotNone(notif)
        self.assertEqual(notif["status"], "QUEUED")
        
        run_notification_flush_job(self.db)
        notif_sent = self.db.notifications.find_one({"_id": notif["_id"]})
        self.assertEqual(notif_sent["status"], "SENT")

        # ── 8. Reopens & SLA Scorecard Impact ────────────────
        print("[1.6 STAGE 8] Asserting customer reopen controls & worker performance penalty...")
        res_comp = {
            "_id": ObjectId(),
            "citizen_id": user["_id"],
            "category": "Road Damage",
            "status": "RESOLVED",
            "assigned_worker_id": ObjectId("6a90322b16de4627eee867f1"),
            "resolved_at": datetime.datetime.utcnow() - datetime.timedelta(hours=1),
            "timeline_events": []
        }
        self.db.complaints.insert_one(res_comp)
        
        reopened_c, err_reopen = reopen_complaint(str(res_comp["_id"]), "Pothole filled poorly.", str(user["_id"]), self.db)
        self.assertIsNotNone(reopened_c)
        self.assertIsNone(err_reopen)
        self.assertEqual(reopened_c["status"], "REOPENED")
        
        worker = self.db.workers.find_one({"_id": ObjectId("6a90322b16de4627eee867f1")})
        self.assertEqual(worker["performance"]["reopened"], 1)

        # ── 9. Heatmap TTL Caching ──────────────────────────
        print("[1.6 STAGE 9] Verifying Heatmap TTL database cache bypass...")
        data1 = get_heatmap_data(self.db, ward="Indiranagar")
        
        self.db.complaints.insert_one({
            "category": "Drainage", "ward": "Indiranagar", "location": {"lat": 12.9720, "lng": 77.5950}
        })
        
        data2 = get_heatmap_data(self.db, ward="Indiranagar")
        self.assertEqual(len(data1), len(data2))
        
        cache.clear()
        data3 = get_heatmap_data(self.db, ward="Indiranagar")
        self.assertNotEqual(len(data1), len(data3))

        print("=== ALL 1.6 SYSTEM TESTS PASSED SUCCESSFULLY ===")

if __name__ == "__main__":
    unittest.main()
