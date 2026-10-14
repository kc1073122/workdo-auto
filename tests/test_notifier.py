"""Unit tests for notifier module."""

import logging
import unittest
from unittest.mock import patch, MagicMock

from config import Config
from notifier import WebhookPushHandler, notify, logger

class TestNotifier(unittest.TestCase):
    def setUp(self):
        self.handler = WebhookPushHandler(level=logging.INFO)

    def test_debug_level_is_suppressed(self):
        """DEBUG level must not trigger any push."""
        record = logging.LogRecord(
            name="WorkDoAuto",
            level=logging.DEBUG,
            pathname=__file__,
            lineno=10,
            msg="debug message",
            args=(),
            exc_info=None
        )
        with patch.object(self.handler, "_send_pushes") as mock_push:
            self.handler.emit(record)
            mock_push.assert_not_called()

    def test_info_warning_error_trigger_pushes(self):
        """INFO and above must trigger pushes."""
        for level in (logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL):
            record = logging.LogRecord(
                name="WorkDoAuto",
                level=level,
                pathname=__file__,
                lineno=20,
                msg=f"message for {level}",
                args=(),
                exc_info=None
            )
            with patch.object(self.handler, "_send_pushes") as mock_push:
                self.handler.emit(record)
                mock_push.assert_called_once()
                content = mock_push.call_args[0][0]
                self.assertIn(f"message for {level}", content)

    def test_message_truncation(self):
        """Long messages must be truncated to prevent Discord 400 Bad Request."""
        record = logging.LogRecord(
            name="WorkDoAuto",
            level=logging.ERROR,
            pathname=__file__,
            lineno=30,
            msg="A" * 3000,
            args=(),
            exc_info=None
        )
        with patch.object(self.handler, "_send_pushes") as mock_push:
            self.handler.emit(record)
            mock_push.assert_called_once()
            content = mock_push.call_args[0][0]
            self.assertLessEqual(len(content), 1900)
            self.assertTrue(content.endswith("..."))

    def test_discord_webhook_send(self):
        with patch.object(Config, "DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test"), \
             patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 204
            self.handler._send_pushes("test content")
            mock_post.assert_called_once()
            self.assertEqual(mock_post.call_args[1]["json"], {"content": "test content"})

    def test_notify_helper(self):
        with patch.object(logger, "info") as mock_info, \
             patch.object(logger, "error") as mock_error:
            notify("Title", "Info Message", level=logging.INFO)
            mock_info.assert_called_once_with("Title: Info Message")

            notify("Title", "Error Message", level=logging.ERROR)
            mock_error.assert_called_once_with("Title: Error Message")

if __name__ == "__main__":
    unittest.main()
