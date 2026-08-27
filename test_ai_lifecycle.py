import io
import os
import unittest
from PIL import Image
from bson import ObjectId
from app import create_app
from app.extensions import db_wrapper

class SmartCivicAILifecycleTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["JWT_COOKIE_SECURE"] = False
        self.app.config["JWT_COOKIE_CSRF_PROTECT"] = False
        self.app.config["RATELIMIT_ENABLED"] = False
        
        self.client = self.app.test_client()
        
        # Clear collections
        with self.app.app_context():
            db_wrapper.db.users.delete_many({})
            db_wrapper.db.workers.delete_many({})
            db_wrapper.db.complaints.delete_many({})
            
        # Create test images
        self.temp_files = []
        self.create_test_images()

    def tearDown(self):
        for f in self.temp_files:
            try:
                os.remove(f)
            except Exception:
                pass

    def create_test_images(self):
        # 1. Clear high-contrast image (alternating stripes to pass blur check)
        clear_path = "clear_pothole.jpg"
        img = Image.new("RGB", (300, 300), color="white")
        pixels = img.load()
        for x in range(300):
            for y in range(300):
                if (x // 15) % 2 == 0:
                    pixels[x, y] = (0, 0, 0)
        img.save(clear_path, format="JPEG")
        self.temp_files.append(clear_path)
        
        # 2. Blurry image (solid gray has zero variance, fails blur check)
        blurry_path = "blurry_photo.jpg"
        img_blur = Image.new("RGB", (300, 300), color="gray")
        img_blur.save(blurry_path, format="JPEG")
        self.temp_files.append(blurry_path)

        # 3. Low confidence image
        low_conf_path = "low_conf_pothole.jpg"
        img_low = Image.new("RGB", (300, 300), color="white")
        pixels_low = img_low.load()
        for x in range(300):
            for y in range(300):
                if (x // 15) % 2 == 0:
                    pixels_low[x, y] = (50, 50, 50)
        img_low.save(low_conf_path, format="JPEG")
        self.temp_files.append(low_conf_path)

        # 4. Repair after clean image (no pothole)
        after_clean_path = "after_clean.jpg"
        img_after = Image.new("RGB", (300, 300), color="white")
        pixels_after = img_after.load()
        for x in range(300):
            for y in range(300):
                if (x // 20) % 2 == 0:
                    pixels_after[x, y] = (0, 100, 0)
        img_after.save(after_clean_path, format="JPEG")
        self.temp_files.append(after_clean_path)

        # 5. Repair after dirty image (still has pothole)
        after_dirty_path = "still_dirty_pothole.jpg"  # Does not contain "after" in filename, so mock returns pothole
        img_dirty = Image.new("RGB", (300, 300), color="white")
        pixels_dirty = img_dirty.load()
        for x in range(300):
            for y in range(300):
                if (x // 10) % 2 == 0:
                    pixels_dirty[x, y] = (0, 0, 0)
        img_dirty.save(after_dirty_path, format="JPEG")
        self.temp_files.append(after_dirty_path)

    def test_ai_intelligence_gates(self):
        print("\n[AI STAGE 1] Registering accounts...")
        # Citizen
        res = self.client.post("/api/auth/register", json={
            "name": "Citizen C", "email": "citizenC@gmail.com", "phone": "9876543220",
            "password": "securepassword123", "ward": "Indiranagar", "role": "citizen"
        })
        self.assertEqual(res.status_code, 201)
        
        # Worker
        res = self.client.post("/api/auth/register", json={
            "name": "Worker C", "email": "workerC@gmail.com", "phone": "9876543221",
            "password": "securepassword123", "ward": "Indiranagar", "role": "worker",
            "department": "Roads"
        })
        self.assertEqual(res.status_code, 201)
        worker_id = res.json["data"]["user"]["_id"]
        
        # Admin
        res = self.client.post("/api/auth/register", json={
            "name": "Admin C", "email": "adminC@smartcivic.gov", "phone": "9876543222",
            "password": "securepassword123", "ward": "Central", "role": "admin"
        })
        self.assertEqual(res.status_code, 201)

        print("\n[AI STAGE 2] Authenticating Citizen C & checking quality gate...")
        self.client = self.app.test_client()
        self.client.post("/api/auth/login", json={
            "email": "citizenC@gmail.com", "password": "securepassword123"
        })
        
        # Upload blurry photo -> should reject with 400 and quality reason
        with open("blurry_photo.jpg", "rb") as f:
            res = self.client.post("/api/complaints", data={
                "category": "Road Damage", "subcategory": "Pothole", "description": "Needs repair.",
                "lat": 12.9716, "lng": 77.5946, "address": "100 Ft Rd", "image": (f, "blurry.jpg")
            }, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 400)
        self.assertIn("appears blurry", res.json["error"])
        print("[SUCCESS] Quality gate successfully blocked blurry photo upload.")

        print("\n[AI STAGE 3] Uploading clear photo with 94% confidence (AUTO routing)...")
        with open("clear_pothole.jpg", "rb") as f:
            res = self.client.post("/api/complaints", data={
                "category": "Road Damage", "subcategory": "Pothole", "description": "Major road defect.",
                "lat": 12.9716, "lng": 77.5946, "address": "100 Ft Rd", "image": (f, "clear.jpg")
            }, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 201)
        comp_auto = res.json["data"]
        comp_auto_id = comp_auto["_id"]
        
        # Assert route status and auto verification
        self.assertEqual(comp_auto["routing_status"], "AUTO")
        self.assertEqual(comp_auto["status"], "VERIFIED")
        self.assertEqual(comp_auto["ai_detected_class"], "pothole")
        self.assertEqual(comp_auto["ai_confidence"], 0.94)
        self.assertIsNotNone(comp_auto["bounding_box"])
        self.assertIsNotNone(comp_auto["severity_score"])
        print(f"[SUCCESS] Complaint auto-verified. Current status: {comp_auto['status']}")

        print("\n[AI STAGE 4] Submitting adjacent complaint to test duplicate checks...")
        # Submit same category 30m away (diff coords by 0.0002)
        with open("clear_pothole.jpg", "rb") as f:
            res = self.client.post("/api/complaints", data={
                "category": "Road Damage", "subcategory": "Pothole", "description": "Pothole nearby.",
                "lat": 12.9718, "lng": 77.5948, "address": "100 Ft Rd", "image": (f, "clear2.jpg")
            }, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 201)
        comp_dup = res.json["data"]
        self.assertTrue(comp_dup["is_duplicate"])
        self.assertEqual(comp_dup["duplicate_of"], comp_auto_id)
        print(f"[SUCCESS] Second complaint flagged as duplicate of {comp_dup['duplicate_of']}")

        print("\n[AI STAGE 5] Uploading low confidence photo (45% -> ADMIN_REVIEW routing)...")
        # Submit low confidence image
        with open("low_conf_pothole.jpg", "rb") as f:
            res = self.client.post("/api/complaints", data={
                "category": "Road Damage", "subcategory": "Pothole", "description": "Doubtful defect description.",
                "lat": 12.9716, "lng": 77.5946, "address": "100 Ft Rd", "image": (f, "low_conf.jpg")
            }, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 201)
        comp_review = res.json["data"]
        comp_review_id = comp_review["_id"]
        
        self.assertEqual(comp_review["routing_status"], "ADMIN_REVIEW")
        self.assertEqual(comp_review["status"], "AI_ANALYSIS") # Stay in queue
        print(f"[SUCCESS] Low confidence complaint routed to ADMIN_REVIEW. Status: {comp_review['status']}")

        print("\n[AI STAGE 6] Admin assigns and worker repairs (verifying repair PASS)...")
        # Admin login and assign AUTO complaint
        self.client = self.app.test_client()
        self.client.post("/api/auth/login", json={
            "email": "adminC@smartcivic.gov", "password": "securepassword123"
        })
        res = self.client.post(f"/api/complaints/{comp_auto_id}/assign", json={"worker_id": worker_id})
        self.assertEqual(res.status_code, 200)

        # Worker login and start work
        self.client = self.app.test_client()
        self.client.post("/api/auth/login", json={
            "email": "workerC@gmail.com", "password": "securepassword123"
        })
        self.client.patch(f"/api/complaints/{comp_auto_id}/status", json={"status": "IN_PROGRESS"})
        
        # Upload clean after-photo (verifies PASS -> RESOLVED)
        with open("after_clean.jpg", "rb") as f:
            res = self.client.post(f"/api/complaints/{comp_auto_id}/after-photo", data={
                "after_image": (f, "after_clean.jpg")
            }, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json["data"]["result"], "PASS")
        
        # Verify DB status is RESOLVED
        res = self.client.get(f"/api/complaints/{comp_auto_id}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json["data"]["status"], "RESOLVED")
        print("[SUCCESS] Clean after-photo passed verification. Complaint status set to RESOLVED.")

        print("\n[AI STAGE 7] Worker repairs second complaint but uploads dirty photo (verifying repair FAIL)...")
        # Admin assigns comp_review
        self.client = self.app.test_client()
        self.client.post("/api/auth/login", json={
            "email": "adminC@smartcivic.gov", "password": "securepassword123"
        })
        # Force VERIFIED status on comp_review so it can be assigned
        self.client.patch(f"/api/admin/complaints/{comp_review_id}", json={"status": "VERIFIED"})
        res = self.client.post(f"/api/complaints/{comp_review_id}/assign", json={"worker_id": worker_id})
        self.assertEqual(res.status_code, 200)

        # Worker login and start work
        self.client = self.app.test_client()
        self.client.post("/api/auth/login", json={
            "email": "workerC@gmail.com", "password": "securepassword123"
        })
        self.client.patch(f"/api/complaints/{comp_review_id}/status", json={"status": "IN_PROGRESS"})

        # Upload dirty after-photo (verifies FAIL -> REOPENED)
        with open("still_dirty_pothole.jpg", "rb") as f:
            res = self.client.post(f"/api/complaints/{comp_review_id}/after-photo", data={
                "after_image": (f, "still_dirty.jpg")
            }, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json["data"]["result"], "FAIL")
        
        # Verify DB status is REOPENED
        res = self.client.get(f"/api/complaints/{comp_review_id}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json["data"]["status"], "REOPENED")
        print("[SUCCESS] Dirty after-photo failed verification. Complaint status reset to REOPENED.")
        print("\n=== ALL AI TEST GATES PASSED SUCCESSFULLY ===")

if __name__ == "__main__":
    unittest.main()
