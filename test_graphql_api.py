import os
import unittest
from bson import ObjectId
from app import create_app
from app.extensions import db_wrapper

class SmartCivicGraphQLTestCase(unittest.TestCase):
    def setUp(self):
        os.environ["RATELIMIT_ENABLED"] = "False"
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["JWT_COOKIE_SECURE"] = False
        self.app.config["JWT_COOKIE_CSRF_PROTECT"] = False

        from app.extensions import limiter
        limiter.enabled = False

        self.client = self.app.test_client()

        with self.app.app_context():
            db_wrapper.db.users.delete_many({})
            db_wrapper.db.workers.delete_many({})
            db_wrapper.db.complaints.delete_many({})

    def register_and_login(self, name, email, role, ward="Indiranagar", department="Roads & Infrastructure"):
        # Register
        payload = {
            "name": name,
            "email": email,
            "phone": "9876543210",
            "password": "securepassword123",
            "ward": ward,
            "role": role
        }
        if role == "worker":
            payload["department"] = department

        res = self.client.post("/api/auth/register", json=payload)
        self.assertEqual(res.status_code, 201)
        user_id = res.json["data"]["user"]["_id"]

        # Ensure user/worker is marked verified
        db_wrapper.db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"is_verified": True}})
        db_wrapper.db.workers.update_one({"_id": ObjectId(user_id)}, {"$set": {"is_verified": True}})

        # Login
        login_res = self.client.post("/api/auth/login", json={
            "email": email,
            "password": "securepassword123"
        })
        self.assertEqual(login_res.status_code, 200)
        token = login_res.json["data"]["access_token"]
        return user_id, token

    def test_graphql_end_to_end(self):
        print("\n=== STARTING GRAPHQL INTEGRATION TESTS ===")

        # 1. Setup accounts
        citizen_id, citizen_token = self.register_and_login("Alice Citizen", "alice_gql@example.com", "citizen", ward="Indiranagar")
        admin_id, admin_token = self.register_and_login("Officer Bob", "bob_admin@smartcivic.gov", "admin", ward="Central")
        worker_id, worker_token = self.register_and_login("Charlie Worker", "charlie_worker@smartcivic.gov", "worker", ward="Indiranagar")

        citizen_headers = {"Authorization": f"Bearer {citizen_token}"}
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        worker_headers = {"Authorization": f"Bearer {worker_token}"}

        # 2. Test createComplaint Mutation
        print("[GQL TEST 1] Executing createComplaint mutation...")
        create_mutation = """
        mutation CreateIssue($input: CreateComplaintInput!) {
            createComplaint(input: $input) {
                id
                title
                category
                status
                priority
                ward
                location {
                    lat
                    lng
                    address
                }
                sla {
                    slaHours
                    isBreached
                }
            }
        }
        """
        variables = {
            "input": {
                "category": "Road Damage",
                "subcategory": "Pothole",
                "description": "Deep hazardous pothole near 100 Feet Road.",
                "lat": 12.9716,
                "lng": 77.5946,
                "address": "100 Feet Road, Indiranagar",
                "imageRef": "/static/uploads/mock_pothole.png"
            }
        }
        res = self.client.post("/graphql", json={"query": create_mutation, "variables": variables}, headers=citizen_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json.get("data")
        self.assertIsNotNone(data)
        complaint = data["createComplaint"]
        complaint_id = complaint["id"]
        self.assertEqual(complaint["category"], "Road Damage")
        self.assertIn(complaint["status"], ["REPORTED", "AI_ANALYSIS", "AI_PROCESSING"])
        self.assertEqual(complaint["location"]["address"], "100 Feet Road, Indiranagar")
        print(f"[SUCCESS] Complaint created via GraphQL: ID {complaint_id}")

        # 3. Test complaint(id) Query
        print("[GQL TEST 2] Executing complaint(id) query with specific field selection...")
        query_complaint = """
        query GetComplaint($id: ID!) {
            complaint(id: $id) {
                id
                title
                category
                status
                ward
                location {
                    lat
                    lng
                }
                sla {
                    slaHours
                    isBreached
                }
            }
        }
        """
        res = self.client.post("/graphql", json={"query": query_complaint, "variables": {"id": complaint_id}}, headers=citizen_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json.get("data")
        self.assertIsNotNone(data["complaint"])
        self.assertEqual(data["complaint"]["id"], complaint_id)
        print("[SUCCESS] Single complaint fetched with precision projection.")

        # 4. Test RBAC: Unauthenticated query must fail
        print("[GQL TEST 3] Verifying unauthenticated request rejection...")
        res = self.client.post("/graphql", json={"query": query_complaint, "variables": {"id": complaint_id}})
        self.assertEqual(res.status_code, 200)
        self.assertIn("errors", res.json)
        self.assertIn("Authentication required", res.json["errors"][0]["message"])
        print("[SUCCESS] Unauthenticated GraphQL request blocked.")

        # 5. Test myComplaints Query
        print("[GQL TEST 4] Executing myComplaints query...")
        query_my = """
        query {
            myComplaints {
                id
                title
                status
            }
        }
        """
        res = self.client.post("/graphql", json={"query": query_my}, headers=citizen_headers)
        self.assertEqual(res.status_code, 200)
        my_list = res.json["data"]["myComplaints"]
        self.assertEqual(len(my_list), 1)
        self.assertEqual(my_list[0]["id"], complaint_id)
        print(f"[SUCCESS] Resident complaints retrieved: {len(my_list)} records.")

        # 6. Test assignComplaint Mutation (Admin only)
        print("[GQL TEST 5] Executing assignComplaint mutation by Admin...")
        assign_mutation = """
        mutation Assign($cid: ID!, $wid: ID) {
            assignComplaint(complaintId: $cid, workerId: $wid) {
                id
                status
            }
        }
        """
        res = self.client.post("/graphql", json={"query": assign_mutation, "variables": {"cid": complaint_id, "wid": worker_id}}, headers=admin_headers)
        self.assertEqual(res.status_code, 200)
        assigned_comp = res.json["data"]["assignComplaint"]
        self.assertEqual(assigned_comp["status"], "ASSIGNED")
        print("[SUCCESS] Complaint assigned to worker.")

        # 7. Test submitRepairEvidence Mutation (Worker)
        print("[GQL TEST 6] Executing submitRepairEvidence mutation by Worker...")
        repair_mutation = """
        mutation SubmitRepair($input: SubmitRepairEvidenceInput!) {
            submitRepairEvidence(input: $input) {
                id
                status
                afterImagePath
            }
        }
        """
        res = self.client.post("/graphql", json={"query": repair_mutation, "variables": {"input": {
            "complaintId": complaint_id,
            "afterImageRef": "/static/uploads/after_clean.jpg",
            "notes": "Pothole filled with cold asphalt mix."
        }}}, headers=worker_headers)
        self.assertEqual(res.status_code, 200)
        repaired = res.json["data"]["submitRepairEvidence"]
        self.assertEqual(repaired["status"], "RESOLVED")
        self.assertEqual(repaired["afterImagePath"], "/static/uploads/after_clean.jpg")
        print("[SUCCESS] Repair evidence submitted and status updated to RESOLVED.")

        # 8. Test verifyRepair Mutation (Admin)
        print("[GQL TEST 7] Executing verifyRepair mutation by Admin...")
        verify_mutation = """
        mutation Verify($input: VerifyRepairInput!) {
            verifyRepair(input: $input) {
                id
                status
            }
        }
        """
        res = self.client.post("/graphql", json={"query": verify_mutation, "variables": {"input": {
            "complaintId": complaint_id,
            "approved": True
        }}}, headers=admin_headers)
        self.assertEqual(res.status_code, 200)
        verified_comp = res.json["data"]["verifyRepair"]
        self.assertEqual(verified_comp["status"], "CLOSED")
        print("[SUCCESS] Repair verified and closed.")

        # 9. Test departmentDashboard Query
        print("[GQL TEST 8] Executing departmentDashboard analytics query...")
        dept_query = """
        query {
            departmentDashboard(department: "Roads & Infrastructure") {
                department
                totalComplaints
                resolvedComplaints
                slaBreachRate
                avgConfidence
            }
        }
        """
        res = self.client.post("/graphql", json={"query": dept_query}, headers=admin_headers)
        self.assertEqual(res.status_code, 200)
        dept_data = res.json["data"]["departmentDashboard"]
        self.assertEqual(dept_data["totalComplaints"], 1)
        self.assertEqual(dept_data["resolvedComplaints"], 0) # closed now
        self.assertGreaterEqual(dept_data["avgConfidence"], 0.0)
        print(f"[SUCCESS] Department analytics query completed. Total: {dept_data['totalComplaints']}")

        print("\n=== ALL GRAPHQL TESTS PASSED SUCCESSFULLY ===")

if __name__ == "__main__":
    unittest.main()
