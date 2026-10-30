"""
Unit tests for database models, queries, deduplication, and referral accounting.
"""

import os
import tempfile
import unittest
from datetime import datetime

import database as db
from config import settings


class TestDatabaseLayer(unittest.TestCase):
    def setUp(self):
        # Create a unique temporary database file for each test
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        db.init_db(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_user_creation_and_retrieval(self):
        user, is_new = db.create_or_get_user(
            user_id=1001,
            username="dz_user",
            first_name="Ahmed",
            db_path=self.db_path
        )
        self.assertTrue(is_new)
        self.assertEqual(user["user_id"], 1001)
        self.assertEqual(user["username"], "dz_user")
        self.assertEqual(user["status"], "NEW")

        # Second retrieval should not be new
        fetched, is_new2 = db.create_or_get_user(
            user_id=1001,
            username="dz_user_updated",
            first_name="Ahmed",
            db_path=self.db_path
        )
        self.assertFalse(is_new2)
        self.assertEqual(fetched["username"], "dz_user_updated")

    def test_referral_tracking_and_gate(self):
        # Create Referrer User A
        referrer, _ = db.create_or_get_user(user_id=2001, username="referrer_a", db_path=self.db_path)
        
        # Create User B referred by User A
        user_b, _ = db.create_or_get_user(user_id=2002, username="user_b", referred_by=2001, db_path=self.db_path)
        self.assertEqual(user_b["referred_by"], 2001)
        self.assertEqual(user_b["referral_verified"], 0)

        # Before channel join verification, referrals_count is 0
        ref_user = db.get_user(2001, db_path=self.db_path)
        self.assertEqual(ref_user["referrals_count"], 0)

        # Trigger channel join verification
        result = db.verify_referral_join(2002, db_path=self.db_path)
        self.assertIsNotNone(result)
        ref_id, count = result
        self.assertEqual(ref_id, 2001)
        self.assertEqual(count, 1)

        # Check in DB
        ref_user_after = db.get_user(2001, db_path=self.db_path)
        self.assertEqual(ref_user_after["referrals_count"], 1)

        # Re-verifying the same user should do nothing (idempotent)
        second_result = db.verify_referral_join(2002, db_path=self.db_path)
        self.assertIsNone(second_result)
        self.assertEqual(db.get_user(2001, db_path=self.db_path)["referrals_count"], 1)

    def test_self_referral_prevention(self):
        user, _ = db.create_or_get_user(user_id=3001, username="self_ref", referred_by=3001, db_path=self.db_path)
        self.assertIsNone(user["referred_by"])

    def test_receipt_hash_and_tx_deduplication(self):
        tx_id = "TX20261024001"
        file_hash = "a1b2c3d4e5f67890abcdef1234567890abcdef1234567890abcdef1234567890"
        user_id = 4001

        # Create user
        db.create_or_get_user(user_id=user_id, username="receipt_tester", db_path=self.db_path)

        # Not yet recorded
        self.assertFalse(db.check_tx_id_exists(tx_id, db_path=self.db_path))
        self.assertFalse(db.check_receipt_hash_exists(file_hash, db_path=self.db_path))

        # Record receipt
        success = db.record_used_receipt(tx_id, file_hash, user_id, 500.0, db_path=self.db_path)
        self.assertTrue(success)

        # Should now exist
        self.assertTrue(db.check_tx_id_exists(tx_id, db_path=self.db_path))
        self.assertTrue(db.check_receipt_hash_exists(file_hash, db_path=self.db_path))

        # Duplicate insert must fail integrity
        dup_success = db.record_used_receipt(tx_id, "different_hash", user_id, 500.0, db_path=self.db_path)
        self.assertFalse(dup_success)

    def test_email_validation_and_seat_counting(self):
        user_id = 5001
        email = "creative.dz@gmail.com"
        db.create_or_get_user(user_id=user_id, username="canva_pro_fan", db_path=self.db_path)

        self.assertFalse(db.is_email_already_registered(email, db_path=self.db_path))

        # Set user email
        db.set_user_email(user_id, email, db_path=self.db_path)
        user = db.get_user(user_id, db_path=self.db_path)
        self.assertEqual(user["email"], email)
        self.assertEqual(user["status"], "PENDING_INVITE")

        # Now email is registered
        self.assertTrue(db.is_email_already_registered(email, db_path=self.db_path))

        # Check stats
        stats = db.get_system_stats(db_path=self.db_path)
        self.assertEqual(stats["pending_invites"], 1)
        self.assertEqual(stats["claimed_seats"], 1)
        self.assertEqual(stats["remaining_seats"], settings.MAX_SEATS - 1)

    def test_canva_csv_export(self):
        user_id = 6001
        email = "batch_invite@gmail.com"
        db.create_or_get_user(user_id=user_id, username="batch_user", first_name="Karim", db_path=self.db_path)
        db.update_user_status(user_id, "AWAITING_EMAIL", unlock_method="PAID", tx_id="TX888999", db_path=self.db_path)
        db.set_user_email(user_id, email, db_path=self.db_path)

        csv_text = db.export_canva_csv(db_path=self.db_path)
        self.assertIn("Email,Telegram Username,First Name,Unlock Method,Tx ID,Registered Date", csv_text)
        self.assertIn(email, csv_text)
        self.assertIn("batch_user", csv_text)
        self.assertIn("PAID", csv_text)

    def test_paid_referrals_and_freebie_rewards(self):
        # Referrer User (VIP paid user)
        referrer_id = 9001
        db.create_or_get_user(user_id=referrer_id, username="vip_affiliate", db_path=self.db_path)
        db.update_user_status(referrer_id, "INVITED", unlock_method="PAID", db_path=self.db_path)

        # 4 paying friends referred
        for i in range(1, 5):
            friend_id = 9100 + i
            db.create_or_get_user(user_id=friend_id, username=f"friend_{i}", referred_by=referrer_id, db_path=self.db_path)
            res = db.credit_paid_referral(friend_id, db_path=self.db_path)
            self.assertIsNotNone(res)
            ref_id, paid_count, reward_unlocked = res
            self.assertEqual(ref_id, referrer_id)
            self.assertEqual(paid_count, i)
            self.assertFalse(reward_unlocked)  # Not yet 5

        # 5th paying friend
        friend_5 = 9105
        db.create_or_get_user(user_id=friend_5, username="friend_5", referred_by=referrer_id, db_path=self.db_path)
        res5 = db.credit_paid_referral(friend_5, db_path=self.db_path)
        self.assertIsNotNone(res5)
        ref_id, paid_count, reward_unlocked = res5
        self.assertEqual(paid_count, 5)
        self.assertTrue(reward_unlocked)  # 5th paid friend unlocks reward!

        # Check pending rewards in database
        pending_rewards = db.get_pending_rewards(db_path=self.db_path)
        self.assertEqual(len(pending_rewards), 1)
        self.assertEqual(pending_rewards[0]["user_id"], referrer_id)
        reward_id = pending_rewards[0]["id"]

        # Admin delivers reward
        delivered = db.mark_reward_delivered(reward_id, note="Delivered Netflix 1-Month Gift Link", db_path=self.db_path)
        self.assertIsNotNone(delivered)
        self.assertEqual(delivered["status"], "DELIVERED")

        # Now pending rewards should be 0
        self.assertEqual(len(db.get_pending_rewards(db_path=self.db_path)), 0)

        # Referrer rewards_claimed should be 1
        ref_user = db.get_user(referrer_id, db_path=self.db_path)
        self.assertEqual(ref_user["rewards_claimed"], 1)

    def test_admin_crud_operations(self):
        # 1. Create User
        new_user = db.admin_create_user({
            "user_id": 5555,
            "username": "crud_master",
            "first_name": "CRUD",
            "email": "crud@example.com",
            "status": "PENDING_INVITE",
            "unlock_method": "PAID",
            "paid_referrals_count": 2,
            "language": "ar"
        }, db_path=self.db_path)
        self.assertEqual(new_user["user_id"], 5555)
        self.assertEqual(new_user["email"], "crud@example.com")
        self.assertEqual(new_user["status"], "PENDING_INVITE")
        self.assertEqual(new_user["language"], "ar")

        # Duplicate ID should fail
        with self.assertRaises(ValueError):
            db.admin_create_user({"user_id": 5555, "username": "duplicate_id"}, db_path=self.db_path)

        # Duplicate Email should fail
        with self.assertRaises(ValueError):
            db.admin_create_user({"user_id": 6666, "email": "crud@example.com"}, db_path=self.db_path)

        # 2. Update User
        updated = db.admin_update_user(5555, {
            "first_name": "UpdatedName",
            "status": "INVITED",
            "email": "crud_updated@example.com",
            "paid_referrals_count": 5
        }, db_path=self.db_path)
        self.assertIsNotNone(updated)
        self.assertEqual(updated["first_name"], "UpdatedName")
        self.assertEqual(updated["status"], "INVITED")
        self.assertEqual(updated["email"], "crud_updated@example.com")
        self.assertEqual(updated["paid_referrals_count"], 5)

        # 3. Delete User
        deleted = db.admin_delete_user(5555, db_path=self.db_path)
        self.assertTrue(deleted)
        self.assertIsNone(db.get_user(5555, db_path=self.db_path))

        # Deleting non-existent user returns False
        self.assertFalse(db.admin_delete_user(999999, db_path=self.db_path))


if __name__ == "__main__":
    unittest.main()
