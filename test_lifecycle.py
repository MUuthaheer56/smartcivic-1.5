import io
import os
import unittest
from PIL import Image
from bson import ObjectId
from app import create_app
from app.extensions import db_wrapper

class SmartCivicLifecycleTestCase(unittest.TestCase):
    def setUp(self):
        # Initialize app with testing configuration
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["JWT_COOKIE_SECURE"] = False
        self.app.config["JWT_COOKIE_CSRF_PROTECT"] = False  # Disable CSRF for backend test client requests
        self.app.config["RATELIMIT_ENABLED"] = True
        
        self.client = self.app.test_client()
        
        # Clear database
        with self.app.app_context():
            db_wrapper.db.users.delete_many({})
            db_wrapper.db.workers.delete_many({})
            db_wrapper.db.complaints.delete_many({})

    def create_dummy_image(self):
        # Create a tiny 1x1 image stream
        img = Image.new("RGB", (1, 1), color="blue")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes.seek(0)
        return img_bytes

    def test_complete_platform_lifecycle(self):
        print("\n[STAGE 1] Registering users...")
        
        # Register Citizen A
        res = self.client.post("/api/auth/register", json={
            "name": "Citizen A",
            "email": "citizenA@gmail.com",
            "phone": "9876543210",
            "password": "securepassword123",
            "ward": "Indiranagar",
            "role": "citizen"
        })
        self.assertEqual(res.status_code, 201)
        
        # Register Citizen B (for IDOR check)
        res = self.client.post("/api/auth/register", json={
            "name": "Citizen B",
            "email": "citizenB@gmail.com",
            "phone": "9876543211",
            "password": "securepassword123",
            "ward": "Koramangala",
            "role": "citizen"
        })
        self.assertEqual(res.status_code, 201)
        
        # Register Worker A
        res = self.client.post("/api/auth/register", json={
            "name": "Worker A",
            "email": "workerA@gmail.com",
            "phone": "9876543212",
            "password": "securepassword123",
            "ward": "Indiranagar",
            "role": "worker",
            "department": "Roads"
        })
        self.assertEqual(res.status_code, 201)
        
        # Register Admin
        res = self.client.post("/api/auth/register", json={
            "name": "Admin User",
            "email": "admin@smartcivic.gov",
            "phone": "9876543213",
            "password": "securepassword123",
            "ward": "Central",
            "role": "admin"
        })
        self.assertEqual(res.status_code, 201)
        print("[SUCCESS] Users registered.")

        print("\n[STAGE 2] Citizen A logs in and submits a complaint...")
        # Login Citizen A (Login attempt 1)
        self.client = self.app.test_client()
        res = self.client.post("/api/auth/login", json={
            "email": "citizenA@gmail.com",
            "password": "securepassword123"
        })
        self.assertEqual(res.status_code, 200)

        img_before = self.create_dummy_image()
        res = self.client.post("/api/complaints", data={
            "category": "Road Damage",
            "subcategory": "Deep Pothole",
            "description": "Massive pothole on 100 Feet road near Metro Station.",
            "lat": 12.9716,
            "lng": 77.5946,
            "address": "100 Feet Rd, Indiranagar",
            "image": (img_before, "before.jpg")
        }, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 201)
        
        complaint = res.json["data"]
        complaint_id = complaint["_id"]
        self.assertEqual(complaint["status"], "REPORTED")
        self.assertEqual(complaint["ward"], "Indiranagar")
        print(f"[SUCCESS] Complaint created: ID {complaint_id}")

        print("\n[STAGE 3] Verifying IDOR checks with Citizen B...")
        # Login Citizen B (Login attempt 2)
        self.client = self.app.test_client()
        res = self.client.post("/api/auth/login", json={
            "email": "citizenB@gmail.com",
            "password": "securepassword123"
        })
        self.assertEqual(res.status_code, 200)
        
        # Citizen B attempts to access Citizen A's complaint (restricted because it's a different ward and not owned)
        res = self.client.get(f"/api/complaints/{complaint_id}")
        self.assertEqual(res.status_code, 403)
        self.assertIn("IDOR check failed", res.json["error"])
        
        # Citizen B attempts to update the status of Citizen A's complaint
        res = self.client.patch(f"/api/complaints/{complaint_id}/status", json={
            "status": "REOPENED"
        })
        self.assertEqual(res.status_code, 403)
        print("[SUCCESS] Citizen A's complaint protected from Citizen B (IDOR verified).")

        print("\n[STAGE 4] Admin assigns complaint to Worker A...")
        # Login Admin (Login attempt 3)
        self.client = self.app.test_client()
        res = self.client.post("/api/auth/login", json={
            "email": "admin@smartcivic.gov",
            "password": "securepassword123"
        })
        self.assertEqual(res.status_code, 200)
        
        # Admin assigns complaint (tests auto-assignment)
        res = self.client.post(f"/api/complaints/{complaint_id}/assign", json={})
        self.assertEqual(res.status_code, 200)
        updated_complaint = res.json["data"]
        self.assertEqual(updated_complaint["status"], "ASSIGNED")
        self.assertIsNotNone(updated_complaint["assigned_worker_id"])
        
        assigned_worker_id = updated_complaint["assigned_worker_id"]
        print(f"[SUCCESS] Complaint assigned to Worker ID {assigned_worker_id}")

        print("\n[STAGE 5] Worker A starts work and resolves complaint...")
        # Login Worker A (Login attempt 4)
        self.client = self.app.test_client()
        res = self.client.post("/api/auth/login", json={
            "email": "workerA@gmail.com",
            "password": "securepassword123"
        })
        self.assertEqual(res.status_code, 200)
        
        # Worker updates status to IN_PROGRESS
        res = self.client.patch(f"/api/complaints/{complaint_id}/status", json={
            "status": "IN_PROGRESS"
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json["data"]["status"], "IN_PROGRESS")
        print("[SUCCESS] Worker started work.")

        # Worker resolves complaint with after image
        img_after = self.create_dummy_image()
        res = self.client.patch(f"/api/complaints/{complaint_id}/status", data={
            "status": "RESOLVED",
            "repair_result": "Pothole filled with asphalt.",
            "after_image": (img_after, "after.jpg")
        }, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json["data"]["status"], "RESOLVED")
        
        # Verify worker is available again
        res = self.client.get(f"/api/workers/{assigned_worker_id}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json["data"]["status"], "AVAILABLE")
        print("[SUCCESS] Complaint resolved and Worker availability restored.")

        print("\n[STAGE 6] Verifying login rate limiting (5 attempts allowed, 6th blocked)...")
        # We need a new test client to simulate separate IP request bounds,
        # but using the same client handles counting attempts cleanly.
        rate_client = self.app.test_client()
        
        # We've already completed 4 logins on the test context.
        # Let's perform more login requests.
        # 1st additional (5th total login attempt across all IPs on this client)
        res = rate_client.post("/api/auth/login", json={
            "email": "citizenA@gmail.com",
            "password": "securepassword123"
        })
        self.assertEqual(res.status_code, 200)

        # 2nd additional (6th total login attempt) -> Should be rate limited
        res = rate_client.post("/api/auth/login", json={
            "email": "citizenA@gmail.com",
            "password": "securepassword123"
        })
        self.assertEqual(res.status_code, 429)
        print("[SUCCESS] Rate limiter successfully blocked the 6th login attempt.")
        print("\n=== ALL TEST GATES PASSED SUCCESSFULLY ===")

if __name__ == "__main__":
    unittest.main()
