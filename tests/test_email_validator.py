"""
Unit tests for email validation regex and edge cases.
"""

import unittest
from bot import EMAIL_REGEX


class TestEmailValidation(unittest.TestCase):
    def test_valid_emails(self):
        valid = [
            "designer@gmail.com",
            "canva.pro.user@yahoo.fr",
            "student_dz@univ-alger.dz",
            "contact+canva@company.co",
            "ahmed.benali99@outlook.com",
            "firstname.lastname@sub.domain.org"
        ]
        for email in valid:
            with self.subTest(email=email):
                self.assertIsNotNone(EMAIL_REGEX.match(email))

    def test_invalid_emails(self):
        invalid = [
            "not-an-email",
            "@gmail.com",
            "user@",
            "user@gmail",
            "user name@gmail.com",
            "user@.com",
            "user@com",
            "https://t.me/user"
        ]
        for email in invalid:
            with self.subTest(email=email):
                self.assertIsNone(EMAIL_REGEX.match(email))


if __name__ == "__main__":
    unittest.main()
