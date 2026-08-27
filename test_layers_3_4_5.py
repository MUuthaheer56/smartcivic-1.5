import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from PIL import Image
from bson import ObjectId
from app import create_app
from app.extensions import db_wrapper
from app.jobs.drain_job import run_drain_job
from app.jobs.coordination_job import run_coordination_job
from app.jobs.trust_job import run_trust_job
from app.jobs.hotspot_job import run_hotspot_job
from app.analytics.risk import run_civicpulse_job

class SmartCivicLayers345TestCase(unittest.TestCase):
    def setUp(self):
        os.environ["RATELIMIT_ENABLED"] = "False"
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["JWT_COOKIE_SECURE"] = False
        self.app.config["JWT_COOKIE_CSRF_PROTECT"] = False
        # Disable rate limiting globally during test execution
        from app.extensions import limiter
        limiter.enabled = False
        
        self.client = self.app.test_client()
        
        # Clear collections
        with self.app.app_context():
            db_wrapper.db.users.delete_many({})
            db_wrapper.db.workers.delete_many({})
            db_wrapper.db.complaints.delete_many({})
            db_wrapper.db.drain_risk.delete_many({})
            db_wrapper.db.animal_hotspots.delete_many({})
            db_wrapper.db.coordination_failures.delete_many({})
            db_wrapper.db.ward_trust_scores.delete_many({})
            db_wrapper.db.civicpulse_risk.delete_many({})
            
        self.temp_files = []
        self.create_test_images()

    def tearDown(self):
        for f in self.temp_files:
            try:
                os.remove(f)
            except Exception:
                pass

    def create_test_images(self):
        # 1. Dark night-time image (low average brightness but sharp edges to pass blur check)
        dark_path = "dark_streetlight.jpg"
        img_dark = Image.new("RGB", (300, 300), color="black")
        pixels_dark = img_dark.load()
        for x in range(300):
            for y in range(300):
                if x % 6 == 0 and y % 6 == 0:
                    pixels_dark[x, y] = (255, 255, 255)
        img_dark.save(dark_path, format="JPEG")
        self.temp_files.append(dark_path)
        
        # 2. General sharp image
        sharp_path = "general_sharp.jpg"
        img = Image.new("RGB", (300, 300), color="white")
        pixels = img.load()
        for x in range(300):
            for y in range(300):
                if (x // 15) % 2 == 0:
                    pixels[x, y] = (0, 0, 0)
        img.save(sharp_path, format="JPEG")
        self.temp_files.append(sharp_path)

        # 3. Stray animal image
        animal_path = "dog_stray.jpg"
        img_an = Image.new("RGB", (300, 300), color="white")
        pixels_an = img_an.load()
        for x in range(300):
            for y in range(300):
                if (x // 15) % 2 == 0:
                    pixels_an[x, y] = (50, 50, 50)
        img_an.save(animal_path, format="JPEG")
        self.temp_files.append(animal_path)

    def test_complete_civic_intelligence_pipeline(self):
        print("\n[L3/4/5 STAGE 1] Registering users & workers...")
        # Citizen
        res = self.client.post("/api/auth/register", json={
            "name": "Citizen D", "email": "citizenD@gmail.com", "phone": "9876543230",
            "password": "securepassword123", "ward": "Indiranagar", "role": "citizen"
        })
        self.assertEqual(res.status_code, 201)
        citizen_id = res.json["data"]["user"]["_id"]
        
        # Worker
        res = self.client.post("/api/auth/register", json={
            "name": "Worker D", "email": "workerD@gmail.com", "phone": "9876543231",
            "password": "securepassword123", "ward": "Indiranagar", "role": "worker",
            "department": "Streetlight"
        })
        self.assertEqual(res.status_code, 201)
        worker_id = res.json["data"]["user"]["_id"]
        
        # Admin
        res = self.client.post("/api/auth/register", json={
            "name": "Admin D", "email": "adminD@smartcivic.gov", "phone": "9876543232",
            "password": "securepassword123", "ward": "Central", "role": "admin"
        })
        self.assertEqual(res.status_code, 201)

        # Authenticate Citizen D
        self.client.post("/api/auth/login", json={
            "email": "citizenD@gmail.com", "password": "securepassword123"
        })

        print("\n[L3/4/5 STAGE 2] Verifying Streetlight Nighttime Outage Trigger...")
        
        # Manually mock datetime class in routes to represent night (11:00 PM)
        import app.core.complaints.routes as routes
        from datetime import datetime as real_datetime
        
        class MockDatetime:
            @staticmethod
            def utcnow():
                return real_datetime(2026, 8, 26, 23, 0, 0)
            @staticmethod
            def fromtimestamp(ts):
                return real_datetime.fromtimestamp(ts)
                
        routes.datetime = MockDatetime
        
        # Submit complaint with a dark night-time photo under Road Damage
        try:
            with open("dark_streetlight.jpg", "rb") as f:
                res = self.client.post("/api/complaints", data={
                    "category": "Road Damage", "subcategory": "Pothole", "description": "Pothole spotted at night.",
                    "lat": 12.9716, "lng": 77.5946, "address": "100 Ft Rd", "image": (f, "dark.jpg")
                }, content_type="multipart/form-data")
        finally:
            routes.datetime = real_datetime
            
        if res.status_code != 201:
            print("Nighttime post failed with:", res.status_code, res.json)
        self.assertEqual(res.status_code, 201)
        print("Nighttime complaint Streetlight AI result:", res.json["data"].get("streetlight"))
        
        # Verify a secondary streetlight complaint was automatically created
        with self.app.app_context():
            st_complaints = list(db_wrapper.db.complaints.find({"category": "Streetlight"}))
            # Should have the auto-created secondary complaint
            self.assertEqual(len(st_complaints), 1)
            print(f"[SUCCESS] Streetlight outage triggered secondary complaint creation. Total: {len(st_complaints)}")

        print("\n[L3/4/5 STAGE 3] Verifying Footpath impact near a sensitive POI...")
        with open("general_sharp.jpg", "rb") as f:
            res = self.client.post("/api/complaints", data={
                "category": "Footpath", "subcategory": "Obstruction", "description": "Blocked path near school.",
                "lat": 12.9716, "lng": 77.5946, "address": "Indiranagar School Zone", "image": (f, "footpath.jpg")
            }, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 201)
        comp = res.json["data"]
        self.assertTrue(comp["footpath"]["near_sensitive_poi"])
        self.assertEqual(comp["footpath"]["impact_level"], "HIGH")
        print("[SUCCESS] Footpath obstruction flagged as HIGH impact near sensitive POI.")

        print("\n[L3/4/5 STAGE 4] Verifying Lake buffer CRITICAL priority override...")
        # Coordinate 12.9812, 77.6206 is inside Ulsoor Lake polygon boundary
        with open("general_sharp.jpg", "rb") as f:
            res = self.client.post("/api/complaints", data={
                "category": "Road Damage", "subcategory": "Pothole", "description": "Flooding near lake.",
                "lat": 12.9812, "lng": 77.6206, "address": "Ulsoor Lake Rd", "image": (f, "lake.jpg")
            }, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 201)
        comp = res.json["data"]
        self.assertTrue(comp["lake"]["violation"])
        self.assertEqual(comp["priority"], "CRITICAL")
        print("[SUCCESS] Lake buffer violation successfully overrode priority to CRITICAL.")

        print("\n[L3/4/5 STAGE 5] Verifying CPCB Noise Violation recording endpoint...")
        res = self.client.post("/api/complaints/noise-reading", json={
            "measured_db": 78, "zone": "residential", "lat": 12.9716, "lng": 77.5946, "address": "100 Ft Rd"
        })
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json["data"]["is_violation"])
        self.assertIsNotNone(res.json["data"].get("complaint_id"))
        print("[SUCCESS] Noise violation recorded and automated verified complaint generated.")

        print("\n[L3/4/5 STAGE 6] Verifying Animal detection and Hotspot clustering...")
        with open("dog_stray.jpg", "rb") as f:
            res = self.client.post("/api/complaints", data={
                "category": "Stray Animal", "subcategory": "Dog Menace", "description": "Pack of dogs roaming.",
                "lat": 12.9750, "lng": 77.6000, "address": "Halasuru", "image": (f, "dog.jpg")
            }, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 201)
        self.assertTrue(res.json["data"]["animals"]["detected"])
        
        # Run animal hotspot job
        with self.app.app_context():
            run_hotspot_job(db_wrapper.db)
            hotspots = list(db_wrapper.db.animal_hotspots.find({}))
            self.assertGreaterEqual(len(hotspots), 1)
            print(f"[SUCCESS] Stray animal detected and hotspot clustered. Score: {hotspots[0]['hotspot_score']}")

        print("\n[L3/4/5 STAGE 7] Verifying Coordination Excavation Failures gridding...")
        with self.app.app_context():
            # Seed conflicting works
            now = datetime.utcnow()
            # Complaint A: Road Damage, resolved
            c_a = {
                "category": "Road Damage", "status": "RESOLVED", "created_at": now - timedelta(days=20),
                "location": {"lat": 12.9780, "lng": 77.6100}, "assigned_department": "BESCOM"
            }
            # Complaint B: Drainage, verified
            c_b = {
                "category": "Drainage", "status": "VERIFIED", "created_at": now - timedelta(days=5),
                "location": {"lat": 12.9781, "lng": 77.6101}, "assigned_department": "BWSSB"
            }
            db_wrapper.db.complaints.insert_many([c_a, c_b])
            run_coordination_job(db_wrapper.db)
            cfis = list(db_wrapper.db.coordination_failures.find({}))
            self.assertGreaterEqual(len(cfis), 1)
            print(f"[SUCCESS] Coordination job successfully flagged excavation overlaps between depts: {cfis[0]['departments']}")

        print("\n[L3/4/5 STAGE 8] Verifying Drain Overflow risk forecasting...")
        with self.app.app_context():
            # Seed open waste/drain reports near Indiranagar drain (12.9716, 77.5946)
            c_w = {
                "category": "Waste Management", "status": "REPORTED", "created_at": datetime.utcnow(),
                "location": {"lat": 12.9716, "lng": 77.5946}
            }
            db_wrapper.db.complaints.insert_one(c_w)
            run_drain_job(db_wrapper.db)
            risks = list(db_wrapper.db.drain_risk.find({}))
            self.assertGreaterEqual(len(risks), 1)
            print(f"[SUCCESS] Drain risk computed. Near complaints: {risks[0]['nearby_complaints']}, Score: {risks[0]['risk_score']}")

        print("\n[L3/4/5 STAGE 9] Verifying Citizen Tiers scoring upgrades and Crowd voting...")
        # Create 3 Verifier citizens by registering them and elevating their tiers in DB
        voters = []
        for i in range(3):
            res = self.client.post("/api/auth/register", json={
                "name": f"Verifier {i}", "email": f"verifier{i}@gmail.com", "phone": f"987654324{i}",
                "password": "securepassword123", "ward": "Indiranagar", "role": "citizen"
            })
            self.assertEqual(res.status_code, 201)
            v_id = res.json["data"]["user"]["_id"]
            voters.append(v_id)
            
            with self.app.app_context():
                hist = [{"type": "complaint_verified", "at": datetime.utcnow()} for _ in range(5)]
                db_wrapper.db.users.update_one(
                    {"_id": ObjectId(v_id)},
                    {"$set": {
                        "contribution_history": hist,
                        "civic_score": 50.0,
                        "tier": "Verifier"
                    }}
                )

        with self.app.app_context():

            # Create an unverified complaint in Indiranagar ward
            c_vote = {
                "citizen_id": citizen_id, "ward": "Indiranagar", "category": "Road Damage", 
                "subcategory": "Pothole", "status": "REPORTED", "created_at": datetime.utcnow(),
                "verification_votes": []
            }
            c_vote_id = str(db_wrapper.db.complaints.insert_one(c_vote).inserted_id)

        # Login as voters and cast YES votes
        for v_id in voters:
            self.client = self.app.test_client()
            # Mock login by setting access cookies (we can login standardly)
            self.client.post("/api/auth/login", json={
                "email": f"verifier{voters.index(v_id)}@gmail.com", "password": "securepassword123"
            })
            res = self.client.post(f"/api/complaints/{c_vote_id}/vote", json={"vote": "UPVOTE"})
            self.assertEqual(res.status_code, 200)

        # Verify that complaint is now VERIFIED
        with self.app.app_context():
            comp_updated = db_wrapper.db.complaints.find_one({"_id": ObjectId(c_vote_id)})
            self.assertEqual(comp_updated["status"], "VERIFIED")
            self.assertEqual(comp_updated["verification_result"], "VERIFIED")
            
            # Check that voters' civic scores increased on accurate vote (+8 points -> total 58.0)
            voter_doc = db_wrapper.db.users.find_one({"_id": ObjectId(voters[0])})
            self.assertEqual(voter_doc["civic_score"], 58.0)
            print(f"[SUCCESS] Crowd voting consensus achieved. Status upgraded to VERIFIED. Voters scores: {voter_doc['civic_score']}")

        print("\n[L3/4/5 STAGE 10] Verifying Ward Trust score computing...")
        with self.app.app_context():
            run_trust_job(db_wrapper.db)
            trusts = list(db_wrapper.db.ward_trust_scores.find({}))
            self.assertGreaterEqual(len(trusts), 1)
            print(f"[SUCCESS] Ward trust levels computed. Ward: {trusts[0]['ward']}, Level: {trusts[0]['trust_level']}")

        print("\n[L3/4/5 STAGE 11] Authenticating Admin D and asserting Analytics Dashboards...")
        # Login Admin D
        self.client = self.app.test_client()
        self.client.post("/api/auth/login", json={
            "email": "adminD@smartcivic.gov", "password": "securepassword123"
        })
        
        # Test Heatmap API
        res = self.client.get("/analytics/heatmap")
        self.assertEqual(res.status_code, 200)
        self.assertGreaterEqual(len(res.json["data"]), 1)
        
        # Test worker performance calculation API
        res = self.client.get(f"/analytics/worker-performance/{worker_id}")
        self.assertEqual(res.status_code, 200)
        self.assertIsNotNone(res.json["data"].get("performance_score"))
        
        # Test the rest of L5 endpoints
        for endpoint in ["drain-risk", "coordination-failures", "ward-trust", "animal-hotspots"]:
            res = self.client.get(f"/analytics/{endpoint}")
            self.assertEqual(res.status_code, 200)
            
        print("\n=== ALL L3/4/5 TEST GATES PASSED SUCCESSFULLY ===")

if __name__ == "__main__":
    unittest.main()
