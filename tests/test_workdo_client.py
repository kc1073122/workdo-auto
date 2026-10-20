"""Unit tests for workdo_client module."""

import unittest
from datetime import date
from unittest.mock import patch, MagicMock

from config import Config
from workdo_client import WorkDoClient, WorkDoError

class TestWorkDoClient(unittest.TestCase):
    def setUp(self):
        self.client = WorkDoClient(email="user@example.com", password="password123")

    def test_login_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "bddUserData": {
                "lastDid": "test_tenant_123",
                "didList": ["test_tenant_123"]
            },
            "skyWebInfo": {
                "name": "Kurt",
                "dispUserNickname": "Kurt"
            }
        }

        with patch.object(self.client.session, "get") as mock_get, \
             patch.object(self.client.session, "post", return_value=mock_resp) as mock_post:
            self.client.session.cookies.set("dummy_cookie", "123")
            data = self.client.login()
            self.assertTrue(self.client.is_logged_in)
            self.assertEqual(self.client.tenant_id, "test_tenant_123")
            self.assertEqual(data["skyWebInfo"]["name"], "Kurt")

    def test_login_failure_verbatim_error(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {
            "message": "帳號或密碼錯誤，請重新確認。"
        }

        with patch.object(self.client.session, "get"), \
             patch.object(self.client.session, "post", return_value=mock_resp):
            with self.assertRaises(WorkDoError) as ctx:
                self.client.login()
            self.assertIn("帳號或密碼錯誤", str(ctx.exception))

    def test_query_punch_status(self):
        self.client.is_logged_in = True
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "list": [
                {"type": "ClockIn", "punchTime": "2026-10-14 09:02:11+0800"},
                {"type": "ClockOut", "punchTime": None}
            ]
        }

        with patch.object(self.client.session, "post", return_value=mock_resp):
            status = self.client.query_punch_status()
            self.assertEqual(status["ClockIn"], "2026-10-14 09:02:11+0800")
            self.assertIsNone(status["ClockOut"])

    def test_punch_already_done_skipped(self):
        """If punch already exists and force=False, returns without calling punch API."""
        self.client.is_logged_in = True
        with patch.object(self.client, "query_punch_status", return_value={"ClockIn": "2026-10-14 09:00:00+0800", "ClockOut": None}), \
             patch.object(self.client.session, "post") as mock_post:

            res = self.client.punch_with_validation("ClockIn", force=False)
            self.assertFalse(res["was_punched"])
            self.assertEqual(res["punch_time"], "2026-10-14 09:00:00+0800")
            mock_post.assert_not_called()

    def test_punch_verbatim_server_error(self):
        """API error must be captured verbatim without translation."""
        self.client.is_logged_in = True
        mock_err_resp = MagicMock()
        mock_err_resp.status_code = 500
        mock_err_resp.json.return_value = {
            "code": 14129,
            "message": "Unable to clock out because you haven't clock in yet."
        }

        with patch.object(self.client, "query_punch_status", return_value={"ClockIn": None, "ClockOut": None}), \
             patch.object(self.client.session, "post", return_value=mock_err_resp):

            with self.assertRaises(WorkDoError) as ctx:
                self.client.punch_with_validation("ClockOut")
            self.assertIn("Unable to clock out because you haven't clock in yet.", str(ctx.exception))

    def test_is_workday(self):
        # Monday (iso weekday 1), not in holidays
        with patch.object(Config, "WORKDAYS", [1, 2, 3, 4, 5]), \
             patch.object(Config, "ENABLE_HOLIDAY_CHECK", True), \
             patch.object(self.client, "fetch_holidays", return_value={"2026-10-10"}):

            # 2026-10-12 is Monday
            self.assertTrue(self.client.is_workday(date(2026, 10, 12)))

            # 2026-10-10 is in holidays
            self.assertFalse(self.client.is_workday(date(2026, 10, 10)))

            # 2026-10-11 is Sunday (iso weekday 7)
            self.assertFalse(self.client.is_workday(date(2026, 10, 11)))

    def test_fetch_holidays_ignores_company_events_and_trainings(self):
        mock_ical = """
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//WorkDo//Calendar//EN
BEGIN:VEVENT
SUMMARY:職場霸凌的法律選擇、申訴流程與自保指南 Legal Options
UID:Event-DD1B75BA3A2FFC83C40C45A0964B38FC39D4E9020019673AD010AE0F2C1E6F88
DESCRIPTION:[Zealogics Taiwan][Event]\n為提升同仁對職場霸凌相關議題的認識
DTSTART:20261020T023000Z
DTEND:20261020T040000Z
END:VEVENT
BEGIN:VEVENT
SUMMARY:2026 Team building #2
UID:Event-AA69A77E1CEE022552DFDF6A9B67AF20B1537845966FEBADC9601F6EA3E4DDE6
DESCRIPTION:[120-C# Team-Hsinchu][Event]\n11:30 - 15:00 饗 A Joy
DTSTART:20261123T033000Z
DTEND:20261123T070000Z
END:VEVENT
BEGIN:VEVENT
SUMMARY:國慶
UID:HumanResource-jU4SxGuAq0A
DESCRIPTION:[Zealogics Taiwan][Human Resource]
DTSTART;VALUE=DATE:20261010
END:VEVENT
BEGIN:VEVENT
SUMMARY:補假
UID:HumanResource-cwbNNa8W56g
DESCRIPTION:[Zealogics Taiwan][Human Resource]\n補 10-10
DTSTART;VALUE=DATE:20261009
END:VEVENT
END:VCALENDAR
"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = mock_ical
        with patch.object(self.client.session, "get", return_value=mock_resp), \
             patch.object(Config, "HOLIDAY_CALENDAR_URL", "https://example.com/cal.ics"):
            self.client._holidays_cache = None
            holidays = self.client.fetch_holidays()

            # Real holidays must be present
            self.assertIn("2026-10-10", holidays)
            self.assertIn("2026-10-09", holidays)

            # Meeting and training events must NOT be marked as holidays!
            self.assertNotIn("2026-10-20", holidays)
            self.assertNotIn("2026-11-23", holidays)

            # 2026-10-20 must be recognized as a workday
            self.assertTrue(self.client.is_workday(date(2026, 10, 20)))

if __name__ == "__main__":
    unittest.main()
