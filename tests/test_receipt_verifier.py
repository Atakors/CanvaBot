"""
Unit tests for BaridiMob receipt parsing, regex extractors, and multi-rule verification.
"""

import unittest
from datetime import date, timedelta
from unittest.mock import patch

from config import settings
from receipt_verifier import (
    extract_transaction_id,
    extract_amount,
    extract_dates,
    is_date_valid,
    matches_target_account,
    normalize_digits
)


class TestBaridiMobReceiptVerifier(unittest.TestCase):
    def setUp(self):
        self.target_rip = "00799999000123456789"
        self.target_ccp = "0001234567"
        self.today = date.today()
        self.yesterday = self.today - timedelta(days=1)
        self.too_old = self.today - timedelta(days=10)

    def test_extract_transaction_id_variations(self):
        samples = [
            ("N° de transaction : 202610240987654321", "202610240987654321"),
            ("N° d'opération : TXN-884920194", "TXN-884920194"),
            ("Numéro de transaction : 998877665544", "998877665544"),
            ("Référence de transaction: REF2026BARIDI", "REF2026BARIDI"),
            ("رقم المعاملة : 445566778899", "445566778899"),
            ("N° d'opération\n10029384756", "10029384756"),
        ]
        for text, expected in samples:
            with self.subTest(text=text):
                extracted = extract_transaction_id(text)
                self.assertEqual(extracted, expected)

    def test_extract_amount_variations(self):
        valid_samples = [
            ("Montant de la transaction : 500,00 DZD", 500.0),
            ("Montant : 500.00 DZD", 500.0),
            ("Montant transféré : 500 DZD", 500.0),
            ("Montant : 500,00 DA", 500.0),
            ("Montant : 500 DA", 500.0),
            ("المبلغ : 500 دج", 500.0),
            ("Détails: Total 500,00 DZD débité avec succès", 500.0)
        ]
        for text, expected in valid_samples:
            with self.subTest(text=text):
                amount = extract_amount(text)
                self.assertIsNotNone(amount)
                self.assertAlmostEqual(amount, expected, places=2)

        # Non-500 amounts
        non_500 = "Montant : 200,00 DZD"
        self.assertAlmostEqual(extract_amount(non_500), 200.0, places=2)

    def test_date_extraction_and_grace_period(self):
        today_str = self.today.strftime("%d/%m/%Y")
        yesterday_str = self.yesterday.strftime("%d/%m/%Y")
        too_old_str = self.too_old.strftime("%d/%m/%Y")

        # Today's date
        dates_today = extract_dates(f"Date de l'opération : {today_str} à 14:32")
        valid, formatted = is_date_valid(dates_today, grace_days=2)
        self.assertTrue(valid)
        self.assertEqual(formatted, today_str)

        # Yesterday's date
        dates_yesterday = extract_dates(f"Date : {yesterday_str}")
        valid, formatted = is_date_valid(dates_yesterday, grace_days=2)
        self.assertTrue(valid)
        self.assertEqual(formatted, yesterday_str)

        # Two days ago date
        two_days_ago_str = (self.today - timedelta(days=2)).strftime("%d/%m/%Y")
        dates_two_days_ago = extract_dates(f"Date : {two_days_ago_str}")
        
        # When grace_days=1 (strictly today and yesterday), 2 days ago is rejected:
        valid_g1, _ = is_date_valid(dates_two_days_ago, grace_days=1)
        self.assertFalse(valid_g1)

        # When grace_days=2 (up to 2 days ago), 2 days ago is accepted:
        valid_g2, formatted_g2 = is_date_valid(dates_two_days_ago, grace_days=2)
        self.assertTrue(valid_g2)
        self.assertEqual(formatted_g2, two_days_ago_str)

        # Expired date (10 days old)
        dates_old = extract_dates(f"Date : {too_old_str}")
        valid, formatted = is_date_valid(dates_old, grace_days=2)
        self.assertFalse(valid)

    def test_target_account_matching(self):
        # 1. Matching exact 20-digit RIP formatted with spaces
        sample_rip_text = "Compte à créditer : 007 99999 0001234567 89 (Algérie Poste)"
        matched, account_info = matches_target_account(sample_rip_text, self.target_rip, self.target_ccp)
        self.assertTrue(matched)

        # 2. Matching core CCP extracted from RIP
        sample_ccp_text = "Bénéficiaire : Compte CCP 1234567 Clé 89"
        matched2, account_info2 = matches_target_account(sample_ccp_text, self.target_rip, self.target_ccp)
        self.assertTrue(matched2)

        # 3. Mismatched account
        wrong_account_text = "Compte à créditer : 007 99999 9999999999 11"
        matched3, _ = matches_target_account(wrong_account_text, self.target_rip, self.target_ccp)
        self.assertFalse(matched3)

    def test_simulated_full_baridimob_receipt(self):
        today_str = self.today.strftime("%d/%m/%Y")
        simulated_receipt = f"""
        RÉPUBLIQUE ALGÉRIENNE DÉMOCRATIQUE ET POPULAIRE
        ALGÉRIE POSTE - BARIDIMOB
        REÇU DE VIREMENT DE COMPTE À COMPTE
        
        N° de transaction : 2026103099887766
        Date de l'opération : {today_str} 14:15:22
        
        Émetteur:
        Compte à débiter : 00799999888877776655
        
        Bénéficiaire:
        Compte à créditer : 00799999000123456789
        Titulaire : ADMIN CANVA ALGERIA
        
        Détails du transfert:
        Montant de la transaction : 500,00 DZD
        Frais : 0,00 DZD
        Montant total débité : 500,00 DZD
        Statut : Opération effectuée avec succès
        """
        
        # Test individual components on the simulated receipt
        tx_id = extract_transaction_id(simulated_receipt)
        self.assertEqual(tx_id, "2026103099887766")

        amount = extract_amount(simulated_receipt)
        self.assertAlmostEqual(amount, 500.0, places=2)

        dates = extract_dates(simulated_receipt)
        date_ok, _ = is_date_valid(dates)
        self.assertTrue(date_ok)

        acc_ok, _ = matches_target_account(simulated_receipt, self.target_rip, self.target_ccp)
        self.assertTrue(acc_ok)


if __name__ == "__main__":
    unittest.main()
