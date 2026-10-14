"""Unit tests for config module."""

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from config import Config, get_bool, get_list, parse_time_str

class TestConfig(unittest.TestCase):
    def test_get_bool(self):
        with patch.dict(os.environ, {"TEST_BOOL_TRUE": "true", "TEST_BOOL_FALSE": "0"}):
            self.assertTrue(get_bool("TEST_BOOL_TRUE", False))
            self.assertFalse(get_bool("TEST_BOOL_FALSE", True))
            self.assertTrue(get_bool("NON_EXISTENT", True))
            self.assertFalse(get_bool("NON_EXISTENT", False))

    def test_get_list(self):
        with patch.dict(os.environ, {"TEST_LIST": "1, 2, 3, 5"}):
            self.assertEqual(get_list("TEST_LIST"), [1, 2, 3, 5])
            self.assertEqual(get_list("NON_EXISTENT", [1, 2]), [1, 2])

    def test_parse_time_str(self):
        self.assertEqual(parse_time_str("09:00"), (9, 0))
        self.assertEqual(parse_time_str("18:30"), (18, 30))
        self.assertEqual(parse_time_str("9:5"), (9, 5))
        # Invalid inputs fallback to defaults
        self.assertEqual(parse_time_str("invalid", 8, 30), (8, 30))
        self.assertEqual(parse_time_str("25:00", 9, 0), (9, 0))
        self.assertEqual(parse_time_str("12:65", 9, 0), (9, 0))

    def test_config_get_time_tuples(self):
        with patch.object(Config, "CLOCK_IN_TIME", "08:45"):
            self.assertEqual(Config.get_clock_in_tuple(), (8, 45))
        with patch.object(Config, "CLOCK_OUT_TIME", "17:15"):
            self.assertEqual(Config.get_clock_out_tuple(), (17, 15))

    def test_is_configured(self):
        with patch.object(Config, "EMAIL", "test@example.com"), patch.object(Config, "PASSWORD", "secret"):
            self.assertTrue(Config.is_configured())
        with patch.object(Config, "EMAIL", ""), patch.object(Config, "PASSWORD", "secret"):
            self.assertFalse(Config.is_configured())

if __name__ == "__main__":
    unittest.main()
