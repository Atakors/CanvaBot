"""
Unit tests for mandatory channel membership verification logic.
"""

import unittest
from unittest.mock import MagicMock, patch
import types

from config import settings
from bot import check_channel_membership, get_channel_link


class TestChannelGate(unittest.TestCase):

    @patch("bot.bot.get_chat_member")
    def test_member_status_joined(self, mock_get_chat_member):
        # User is an active member
        mock_member = MagicMock()
        mock_member.status = "member"
        mock_get_chat_member.return_value = mock_member

        with patch.object(settings, "REQUIRED_CHANNEL", "@aitadz"):
            self.assertTrue(check_channel_membership(12345678))

    @patch("bot.bot.get_chat_member")
    def test_member_status_creator_or_admin(self, mock_get_chat_member):
        mock_member = MagicMock()
        mock_member.status = "creator"
        mock_get_chat_member.return_value = mock_member

        with patch.object(settings, "REQUIRED_CHANNEL", "@aitadz"):
            self.assertTrue(check_channel_membership(12345678))

    @patch("bot.bot.get_chat_member")
    def test_member_status_left(self, mock_get_chat_member):
        mock_member = MagicMock()
        mock_member.status = "left"
        mock_get_chat_member.return_value = mock_member

        with patch.object(settings, "REQUIRED_CHANNEL", "@aitadz"):
            self.assertFalse(check_channel_membership(12345678))

    @patch("bot.bot.get_chat_member")
    def test_user_not_found_exception(self, mock_get_chat_member):
        # Telegram API throws user not found when user has not joined
        mock_get_chat_member.side_effect = Exception("Bad Request: user not found")

        with patch.object(settings, "REQUIRED_CHANNEL", "@aitadz"):
            self.assertFalse(check_channel_membership(12345678))

    def test_no_required_channel_bypasses(self):
        with patch.object(settings, "REQUIRED_CHANNEL", ""):
            self.assertTrue(check_channel_membership(12345678))

    def test_channel_link_generation(self):
        with patch.object(settings, "CHANNEL_INVITE_LINK", "https://t.me/aitadz"):
            self.assertEqual(get_channel_link(), "https://t.me/aitadz")

        with patch.object(settings, "CHANNEL_INVITE_LINK", ""):
            with patch.object(settings, "REQUIRED_CHANNEL", "@aitadz"):
                self.assertEqual(get_channel_link(), "https://t.me/aitadz")


if __name__ == "__main__":
    unittest.main()
