"""Unit tests for scheduler module."""

import unittest
from datetime import datetime, date, timedelta
from unittest.mock import patch

from config import Config
from scheduler import (
    parse_workdo_punch_time,
    compute_scheduled_clock_out,
    wait_until_target_time,
    get_current_taipei_time,
    TAIPEI_TZ,
)

class TestScheduler(unittest.TestCase):
    def test_parse_workdo_punch_time(self):
        # Empty
        self.assertIsNone(parse_workdo_punch_time(""))
        self.assertIsNone(parse_workdo_punch_time(None))

        # Standard ISO with offset
        dt1 = parse_workdo_punch_time("2026-10-14 09:05:22+0800")
        self.assertIsNotNone(dt1)
        self.assertEqual(dt1.hour, 9)
        self.assertEqual(dt1.minute, 5)
        self.assertEqual(dt1.second, 22)

        # Standard without offset (defaults to TAIPEI_TZ)
        dt2 = parse_workdo_punch_time("2026-10-14 18:30:00")
        self.assertIsNotNone(dt2)
        self.assertEqual(dt2.hour, 18)
        self.assertEqual(dt2.minute, 30)

        # Slash format
        dt3 = parse_workdo_punch_time("2026/10/14 09:12:00")
        self.assertIsNotNone(dt3)
        self.assertEqual(dt3.minute, 12)

    def test_compute_scheduled_clock_out_normal(self):
        """When clock-in is on-time or early, clock-out should remain at default 18:00."""
        with patch.object(Config, "CLOCK_IN_TIME", "09:00"), \
             patch.object(Config, "CLOCK_OUT_TIME", "18:00"), \
             patch.object(Config, "ENABLE_FLEXIBLE_CLOCK_OUT", True):

            # Case 1: Early clock in (08:55)
            today_str = get_current_taipei_time().strftime("%Y-%m-%d")
            target_dt, delay_min = compute_scheduled_clock_out(f"{today_str} 08:55:00+0800")
            self.assertEqual(delay_min, 0)
            self.assertEqual(target_dt.hour, 18)
            self.assertEqual(target_dt.minute, 0)

            # Case 2: Exactly on time (09:00)
            target_dt, delay_min = compute_scheduled_clock_out(f"{today_str} 09:00:00+0800")
            self.assertEqual(delay_min, 0)
            self.assertEqual(target_dt.hour, 18)
            self.assertEqual(target_dt.minute, 0)

    def test_compute_scheduled_clock_out_delayed(self):
        """When clock-in is delayed (e.g. 09:15), clock-out should extend to 18:15."""
        with patch.object(Config, "CLOCK_IN_TIME", "09:00"), \
             patch.object(Config, "CLOCK_OUT_TIME", "18:00"), \
             patch.object(Config, "ENABLE_FLEXIBLE_CLOCK_OUT", True):

            today_str = get_current_taipei_time().strftime("%Y-%m-%d")
            target_dt, delay_min = compute_scheduled_clock_out(f"{today_str} 09:15:30+0800")
            self.assertEqual(delay_min, 15)
            self.assertEqual(target_dt.hour, 18)
            self.assertEqual(target_dt.minute, 15)
            self.assertEqual(target_dt.second, 30)

    def test_compute_scheduled_clock_out_disabled(self):
        """When flexible clock out is disabled, always returns default 18:00."""
        with patch.object(Config, "CLOCK_IN_TIME", "09:00"), \
             patch.object(Config, "CLOCK_OUT_TIME", "18:00"), \
             patch.object(Config, "ENABLE_FLEXIBLE_CLOCK_OUT", False):

            today_str = get_current_taipei_time().strftime("%Y-%m-%d")
            target_dt, delay_min = compute_scheduled_clock_out(f"{today_str} 09:40:00+0800")
            self.assertEqual(delay_min, 0)
            self.assertEqual(target_dt.hour, 18)
            self.assertEqual(target_dt.minute, 0)

    def test_wait_until_target_time_already_passed(self):
        """Target time in the past should return immediately without sleep."""
        past_time = get_current_taipei_time() - timedelta(minutes=5)
        with patch("time.sleep") as mock_sleep:
            wait_until_target_time(past_time)
            mock_sleep.assert_not_called()

    def test_wait_until_target_time_future(self):
        """Target time in the future sleeps for the remaining seconds."""
        future_time = get_current_taipei_time() + timedelta(seconds=10)
        with patch("time.sleep") as mock_sleep:
            wait_until_target_time(future_time)
            mock_sleep.assert_called_once()
            slept_seconds = mock_sleep.call_args[0][0]
            self.assertAlmostEqual(slept_seconds, 10, delta=2)

if __name__ == "__main__":
    unittest.main()
