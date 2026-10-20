"""Unit tests for main CLI module."""

import argparse
import unittest
from unittest.mock import patch, MagicMock

from config import Config
from main import (
    build_parser,
    handle_punch_in,
    handle_punch_out,
    handle_status,
    handle_test_login,
)

class TestMain(unittest.TestCase):
    def test_parser_commands_and_aliases(self):
        parser = build_parser()

        # punch-in and alias 'in'
        args1 = parser.parse_args(["punch-in", "--force"])
        self.assertEqual(args1.command, "punch-in")
        self.assertTrue(args1.force)

        args2 = parser.parse_args(["in"])
        self.assertEqual(args2.command, "in")
        self.assertFalse(args2.force)

        # punch-out and alias 'out'
        args3 = parser.parse_args(["punch-out", "--flexible"])
        self.assertEqual(args3.command, "punch-out")
        self.assertTrue(args3.flexible)

        args4 = parser.parse_args(["out", "--force"])
        self.assertEqual(args4.command, "out")
        self.assertTrue(args4.force)

        # status & test-login
        args5 = parser.parse_args(["status"])
        self.assertEqual(args5.command, "status")

        args6 = parser.parse_args(["test-login"])
        self.assertEqual(args6.command, "test-login")

    def test_handle_punch_in_non_workday_skipped(self):
        args = argparse.Namespace(force=False)
        with patch.object(Config, "validate_credentials"), \
             patch("workdo_client.WorkDoClient.is_workday", return_value=False), \
             patch("workdo_client.WorkDoClient.login") as mock_login:

            code = handle_punch_in(args)
            self.assertEqual(code, 0)
            mock_login.assert_not_called()

    def test_handle_punch_in_success(self):
        args = argparse.Namespace(force=True)
        with patch.object(Config, "validate_credentials"), \
             patch("workdo_client.WorkDoClient.login"), \
             patch("workdo_client.WorkDoClient.supplement_missing_punches"), \
             patch("workdo_client.WorkDoClient.punch_with_validation", return_value={"was_punched": True, "message": "OK"}):

            code = handle_punch_in(args)
            self.assertEqual(code, 0)

    def test_handle_punch_out_success(self):
        args = argparse.Namespace(force=True, flexible=False)
        with patch.object(Config, "validate_credentials"), \
             patch.object(Config, "ENABLE_FLEXIBLE_CLOCK_OUT", False), \
             patch("workdo_client.WorkDoClient.login"), \
             patch("workdo_client.WorkDoClient.supplement_missing_punches"), \
             patch("workdo_client.WorkDoClient.query_punch_status", return_value={"ClockIn": "09:00", "ClockOut": None}), \
             patch("workdo_client.WorkDoClient.punch_with_validation", return_value={"was_punched": True, "message": "OK"}):

            code = handle_punch_out(args)
            self.assertEqual(code, 0)

    def test_handle_test_login(self):
        args = argparse.Namespace()
        with patch.object(Config, "validate_credentials"), \
             patch("workdo_client.WorkDoClient.login", return_value={"skyWebInfo": {"name": "Test User"}}):

            code = handle_test_login(args)
            self.assertEqual(code, 0)

if __name__ == "__main__":
    unittest.main()
