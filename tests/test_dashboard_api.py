"""
Integration tests for FastAPI dashboard endpoints and authentication.
"""

import os
import tempfile
import unittest
from fastapi.testclient import TestClient

from config import settings
import database as db
from dashboard import app


class TestDashboardAPI(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        settings.DATABASE_PATH = self.db_path
        db.init_db(self.db_path)
        self.client = TestClient(app)
        self.auth = (settings.ADMIN_USERNAME, settings.ADMIN_PASSWORD)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_health_check(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["seats_remaining"], settings.MAX_SEATS)

    def test_auth_protection(self):
        # Without credentials -> 401
        res = self.client.get("/api/stats")
        self.assertEqual(res.status_code, 401)

        # With credentials -> 200
        res_auth = self.client.get("/api/stats", auth=self.auth)
        self.assertEqual(res_auth.status_code, 200)

    def test_export_csv_endpoint(self):
        # Create a pending invite user
        db.create_or_get_user(user_id=777, username="csv_tester", db_path=self.db_path)
        db.set_user_email(user_id=777, email="csv_test@gmail.com", db_path=self.db_path)

        res = self.client.get("/admin/export-csv", auth=self.auth)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers["content-type"], "text/csv; charset=utf-8")
        self.assertIn("csv_test@gmail.com", res.text)

    def test_bulk_mark_invited_api(self):
        # Create 2 pending users
        db.create_or_get_user(user_id=881, username="u1", db_path=self.db_path)
        db.set_user_email(user_id=881, email="u1@gmail.com", db_path=self.db_path)

        db.create_or_get_user(user_id=882, username="u2", db_path=self.db_path)
        db.set_user_email(user_id=882, email="u2@gmail.com", db_path=self.db_path)

        res = self.client.post("/api/bulk-mark-invited", auth=self.auth)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["count"], 2)

        # Pending count should now be 0, invited count 2
        stats = db.get_system_stats(db_path=self.db_path)
        self.assertEqual(stats["pending_invites"], 0)
        self.assertEqual(stats["invited_users"], 2)

    def test_dashboard_html_rendering(self):
        res = self.client.get("/dashboard", auth=self.auth)
        self.assertEqual(res.status_code, 200)
        self.assertIn("Canva Algeria Hub", res.text)
        self.assertIn("Batch Seat Capacity", res.text)
        self.assertIn("addUserModal", res.text)
        self.assertIn("editUserModal", res.text)
        self.assertIn("userSearch", res.text)
        self.assertIn("statusFilter", res.text)

    def test_rewards_api(self):
        # Create user and paid referrals
        ref_id = 9901
        db.create_or_get_user(user_id=ref_id, username="reward_claim_user", db_path=self.db_path)
        for i in range(1, 6):
            db.create_or_get_user(user_id=9910 + i, username=f"payer_{i}", referred_by=ref_id, db_path=self.db_path)
            db.credit_paid_referral(9910 + i, db_path=self.db_path)

        # GET /api/rewards
        res = self.client.get("/api/rewards", auth=self.auth)
        self.assertEqual(res.status_code, 200)
        rewards = res.json()["rewards"]
        self.assertEqual(len(rewards), 1)
        reward_id = rewards[0]["id"]

        # POST /api/deliver-reward/{id}
        deliv_res = self.client.post(f"/api/deliver-reward/{reward_id}", auth=self.auth)
        self.assertEqual(deliv_res.status_code, 200)
        self.assertEqual(deliv_res.json()["status"], "success")

    def test_crud_user_endpoints(self):
        # 1. CREATE (POST /api/users)
        create_payload = {
            "user_id": 778899,
            "username": "crud_api_user",
            "first_name": "API",
            "email": "crud_api@example.com",
            "status": "AWAITING_EMAIL",
            "unlock_method": "PAID",
            "paid_referrals_count": 1,
            "language": "fr"
        }
        res = self.client.post("/api/users", json=create_payload, auth=self.auth)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["user"]["user_id"], 778899)
        self.assertEqual(data["user"]["email"], "crud_api@example.com")

        # Duplicate ID rejection (400)
        dup_res = self.client.post("/api/users", json=create_payload, auth=self.auth)
        self.assertEqual(dup_res.status_code, 400)

        # 2. READ (GET /api/users/{user_id})
        get_res = self.client.get("/api/users/778899", auth=self.auth)
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.json()["user"]["username"], "crud_api_user")

        # Non-existent user (404)
        nf_res = self.client.get("/api/users/9999999", auth=self.auth)
        self.assertEqual(nf_res.status_code, 404)

        # 3. UPDATE (PUT /api/users/{user_id})
        update_payload = {
            "email": "updated_crud@example.com",
            "status": "INVITED",
            "paid_referrals_count": 3
        }
        put_res = self.client.put("/api/users/778899", json=update_payload, auth=self.auth)
        self.assertEqual(put_res.status_code, 200)
        updated_data = put_res.json()["user"]
        self.assertEqual(updated_data["email"], "updated_crud@example.com")
        self.assertEqual(updated_data["status"], "INVITED")
        self.assertEqual(updated_data["paid_referrals_count"], 3)

        # 4. DELETE (DELETE /api/users/{user_id})
        del_res = self.client.delete("/api/users/778899", auth=self.auth)
        self.assertEqual(del_res.status_code, 200)
        self.assertEqual(del_res.json()["status"], "success")

        # Verify it no longer exists
        get_again = self.client.get("/api/users/778899", auth=self.auth)
        self.assertEqual(get_again.status_code, 404)

    @unittest.mock.patch("dashboard.broadcast_message")
    def test_broadcast_endpoint(self, mock_broadcast):
        mock_broadcast.return_value = {
            "total_targeted": 10,
            "sent_count": 9,
            "failed_count": 1,
            "blocked_count": 0
        }
        # Empty text -> 400
        res = self.client.post("/api/broadcast", json={"text": ""}, auth=self.auth)
        self.assertEqual(res.status_code, 400)

        # Valid text
        res = self.client.post(
            "/api/broadcast",
            json={"text": "Test broadcast announcement", "target_status": "ALL", "test_only": True},
            auth=self.auth
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "success")
        self.assertEqual(res.json()["result"]["sent_count"], 9)

    def test_receipts_api_and_revoke(self):
        # Insert a user and receipt
        db.create_or_get_user(user_id=123123, username="receipt_buyer", db_path=self.db_path)
        db.record_used_receipt(
            tx_id="TX_TEST_999",
            file_hash="hash999abcdef",
            user_id=123123,
            amount=500.0,
            db_path=self.db_path
        )

        # GET /api/receipts
        res = self.client.get("/api/receipts", auth=self.auth)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()["receipts"]), 1)
        self.assertEqual(res.json()["receipts"][0]["tx_id"], "TX_TEST_999")

        # DELETE /api/receipts/TX_TEST_999
        del_res = self.client.delete("/api/receipts/TX_TEST_999", auth=self.auth)
        self.assertEqual(del_res.status_code, 200)
        self.assertEqual(del_res.json()["status"], "success")

        # Verify deleted
        empty_res = self.client.get("/api/receipts", auth=self.auth)
        self.assertEqual(len(empty_res.json()["receipts"]), 0)

        # Delete non-existent -> 404
        nf_res = self.client.delete("/api/receipts/NON_EXISTENT", auth=self.auth)
        self.assertEqual(nf_res.status_code, 404)

    def test_pending_emails_and_bulk_import(self):
        db.create_or_get_user(user_id=5001, username="p1", db_path=self.db_path)
        db.set_user_email(user_id=5001, email="p1@example.com", db_path=self.db_path)

        db.create_or_get_user(user_id=5002, username="p2", db_path=self.db_path)
        db.set_user_email(user_id=5002, email="p2@example.com", db_path=self.db_path)

        # GET /api/pending-emails
        res = self.client.get("/api/pending-emails", auth=self.auth)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["count"], 2)
        self.assertIn("p1@example.com", data["comma_separated"])
        self.assertIn("p2@example.com", data["newline_separated"])

        # POST /api/bulk-import-invited
        raw_text = """
        Here are the invited Canva users:
        - p1@example.com [INVITED]
        - p2@example.com (confirmed)
        - extra_unrelated@example.com
        """
        import_res = self.client.post("/api/bulk-import-invited", json={"raw_text": raw_text}, auth=self.auth)
        self.assertEqual(import_res.status_code, 200)
        import_data = import_res.json()
        self.assertEqual(import_data["updated_count"], 2)
        self.assertEqual(import_data["total_parsed"], 3)

        # Verify status is now INVITED
        u1 = db.get_user(5001, db_path=self.db_path)
        u2 = db.get_user(5002, db_path=self.db_path)
        self.assertEqual(u1["status"], "INVITED")
        self.assertEqual(u2["status"], "INVITED")

        # Empty or invalid text -> 400
        inv_res = self.client.post("/api/bulk-import-invited", json={"raw_text": "no emails here"}, auth=self.auth)
        self.assertEqual(inv_res.status_code, 400)

    def test_config_api_endpoints(self):
        # GET /api/config
        get_res = self.client.get("/api/config", auth=self.auth)
        self.assertEqual(get_res.status_code, 200)
        cfg = get_res.json()["config"]
        self.assertEqual(float(cfg["payment_amount"]), settings.PAYMENT_AMOUNT)

        # POST /api/config
        update_payload = {
            "payment_amount": 600.0,
            "target_rip": "00799999009999999999",
            "max_seats": 600
        }
        post_res = self.client.post("/api/config", json=update_payload, auth=self.auth)
        self.assertEqual(post_res.status_code, 200)
        self.assertEqual(post_res.json()["status"], "success")

        # Verify updated values
        get_res2 = self.client.get("/api/config", auth=self.auth)
        cfg2 = get_res2.json()["config"]
        self.assertEqual(float(cfg2["payment_amount"]), 600.0)
        self.assertEqual(cfg2["target_rip"], "00799999009999999999")
        self.assertEqual(int(cfg2["max_seats"]), 600)

    def test_backup_and_json_exports(self):
        # GET /admin/backup-db
        backup_res = self.client.get("/admin/backup-db", auth=self.auth)
        self.assertEqual(backup_res.status_code, 200)
        self.assertIn("application/octet-stream", backup_res.headers["content-type"])
        self.assertGreater(len(backup_res.content), 0)

        # GET /admin/export-json
        json_res = self.client.get("/admin/export-json", auth=self.auth)
        self.assertEqual(json_res.status_code, 200)
        self.assertIn("application/json", json_res.headers["content-type"])
        parsed = json_res.json()
        self.assertIn("stats", parsed)
        self.assertIn("users", parsed)
        self.assertIn("receipts", parsed)


if __name__ == "__main__":
    unittest.main()
