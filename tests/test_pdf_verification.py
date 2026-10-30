"""
End-to-end PDF receipt generation and verification test.
"""

import io
import os
import tempfile
import unittest
from datetime import date
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

import database as db
from config import settings
from receipt_verifier import verify_baridimob_receipt


class TestPDFReceiptVerification(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        db.init_db(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def create_sample_baridimob_pdf(self, tx_id="2026103012345678", amount_str="500,00 DZD", account_str=None, date_str=None):
        if not account_str:
            account_str = settings.TARGET_RIP
        if not date_str:
            date_str = date.today().strftime("%d/%m/%Y")
        
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        p.drawString(100, 750, "ALGERIE POSTE - BARIDIMOB")
        p.drawString(100, 730, "REÇU DE VIREMENT")
        p.drawString(100, 700, f"N° de transaction : {tx_id}")
        p.drawString(100, 680, f"Date de l'opération : {date_str} 15:30:00")
        p.drawString(100, 660, f"Compte à créditer : {account_str}")
        p.drawString(100, 640, "Titulaire : ADMIN CANVA ALGERIA")
        p.drawString(100, 620, f"Montant de la transaction : {amount_str}")
        p.drawString(100, 600, "Statut : Exécuté avec succès")
        p.showPage()
        p.save()
        buffer.seek(0)
        return buffer.getvalue()

    def test_pdf_receipt_verification_success(self):
        pdf_bytes = self.create_sample_baridimob_pdf()
        result = verify_baridimob_receipt(
            file_bytes=pdf_bytes,
            filename="recu_virement_500.pdf",
            is_pdf=True,
            db_path=self.db_path
        )
        self.assertTrue(result.is_valid, f"Verification failed with: {result.error_message}")
        self.assertEqual(result.tx_id, "2026103012345678")
        self.assertEqual(result.amount, 500.0)

        # Create user first to satisfy foreign key constraint
        db.create_or_get_user(user_id=999, username="receipt_payer", db_path=self.db_path)

        # Record and verify deduplication
        rec_ok = db.record_used_receipt(result.tx_id, result.file_hash, 999, result.amount, db_path=self.db_path)
        self.assertTrue(rec_ok)

        # Uploading the exact same PDF should now fail with DUPLICATE_HASH
        dup_result = verify_baridimob_receipt(
            file_bytes=pdf_bytes,
            filename="recu_virement_500.pdf",
            is_pdf=True,
            db_path=self.db_path
        )
        self.assertFalse(dup_result.is_valid)
        self.assertEqual(dup_result.status_code, "DUPLICATE_HASH")

    def test_pdf_receipt_wrong_amount(self):
        pdf_bytes = self.create_sample_baridimob_pdf(amount_str="200,00 DZD")
        result = verify_baridimob_receipt(
            file_bytes=pdf_bytes,
            filename="recu_virement_wrong_amt.pdf",
            is_pdf=True,
            db_path=self.db_path
        )
        self.assertFalse(result.is_valid)
        self.assertEqual(result.status_code, "INVALID_AMOUNT")

    def test_pdf_receipt_wrong_account(self):
        pdf_bytes = self.create_sample_baridimob_pdf(account_str="00799999888877776655")
        result = verify_baridimob_receipt(
            file_bytes=pdf_bytes,
            filename="recu_virement_wrong_acc.pdf",
            is_pdf=True,
            db_path=self.db_path
        )
        self.assertFalse(result.is_valid)
        self.assertEqual(result.status_code, "INVALID_ACCOUNT")

    def test_exact_baridimob_english_pdf_format(self):
        # Exact format from real BaridiMob system
        today_date = date.today()
        today_formatted = today_date.strftime("%d.%m.%Y")
        expected_tx_date = today_date.strftime("%d/%m/%Y")
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        p.drawString(100, 750, "Algeria Poste")
        p.drawString(100, 730, "Receipt for operation in the system «BaridiMob»")
        p.drawString(100, 700, "Amount 700.00")
        p.drawString(100, 680, f"Operation date: {today_formatted} 13:38:36")
        p.drawString(100, 660, f"Recipient: {settings.TARGET_RIP}")
        p.drawString(100, 640, "Operation type: TRANSFER")
        p.drawString(100, 620, "External id: 012582851483")
        p.drawString(100, 600, "Baridimob")
        p.drawString(100, 580, "Quartier des affaires, 16024, Bab Ezzouar, Algeria")
        p.showPage()
        p.save()
        pdf_bytes = buffer.getvalue()

        result = verify_baridimob_receipt(
            file_bytes=pdf_bytes,
            filename="Baridimob_012582851483.pdf",
            is_pdf=True,
            db_path=self.db_path
        )
        self.assertTrue(result.is_valid, f"Failed with: {result.error_message}")
        self.assertEqual(result.tx_id, "012582851483")
        self.assertEqual(result.amount, 700.0)
        self.assertEqual(result.operation_type, "TRANSFER")
        self.assertEqual(result.tx_date, expected_tx_date)


if __name__ == "__main__":
    unittest.main()
