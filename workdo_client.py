"""WorkDo API Client."""

import re
import json
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List, Set
import requests

from config import Config
from notifier import logger

class WorkDoError(Exception):
    """Base exception for WorkDo client."""
    pass

class WorkDoClient:
    """HTTP Client for interacting with WorkDo Cloud Attendance API."""

    URL_LOGIN = "https://www.workdo.co/bdddweb/api/dweb/BDD771M/userLogin"
    URL_PUNCH_STATUS = "https://www.workdo.co/ccndweb/api/dweb/CCN102M/execute102M2FromMenu"
    URL_PUNCH = "https://www.workdo.co/ccndweb/api/dweb/CCN102M/saveFromCreate102M3"
    URL_MISSING_PUNCH_QUERY = "https://www.workdo.co/ccnraweb/api/aweb/CCN002W/queryFromQuery002W1"
    URL_MISSING_PUNCH_SAVE = "https://www.workdo.co/ccndweb/api/dweb/CCN102M/saveFromCreate102M4"

    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    APP_VERSION = "wd_aweb_7.7.6"

    def __init__(self, email: Optional[str] = None, password: Optional[str] = None):
        self.email = email or Config.EMAIL
        self.password = password or Config.PASSWORD
        self.tenant_id = Config.TENANT_ID
        self.session = requests.Session()
        self.is_logged_in = False
        self._holidays_cache: Optional[Set[str]] = None

    def login(self) -> Dict[str, Any]:
        """
        Perform user login to WorkDo.
        Visits /Login first to initialize session cookies and anti-CSRF state.
        """
        if not self.email or not self.password:
            raise WorkDoError("WorkDo 帳號或密碼未提供，請檢查設定檔。")

        # 1. 初始化 Session Cookies
        try:
            self.session.get("https://www.workdo.co/Login", headers={"User-Agent": self.USER_AGENT}, timeout=15)
        except Exception as e:
            logger.debug(f"訪問登入首頁失敗 (可忽略): {e}")

        payload = {
            "clientType": "Web",
            "clientModel": "Chrome 120.0.0.0",
            "clientOs": "Windows 10",
            "appVersion": self.APP_VERSION,
            "timeZone": "GMT+0800",
            "loginEmail": self.email,
            "password": self.password,
            "loginId": self.email,
            "loginPhone": None,
        }
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "User-Agent": self.USER_AGENT,
            "brandName": "WorkDo",
            "app_version_code": self.APP_VERSION,
            "userLocale": "zh_TW",
            "Origin": "https://www.workdo.co",
            "Referer": "https://www.workdo.co/Login",
        }

        try:
            resp = self.session.post(self.URL_LOGIN, json=payload, headers=headers, timeout=20)
        except Exception as e:
            raise WorkDoError(f"連線至 WorkDo 登入 API 失敗: {e}")

        try:
            body = resp.json()
        except Exception:
            body = {}

        if resp.status_code != 200 or not self.session.cookies:
            # 如實回傳 WorkDo API 錯誤訊息，不另行轉譯
            msg = None
            if isinstance(body, dict):
                for k in ("localizedMessage", "message", "errorMessage", "errorMsg", "msg", "detail"):
                    if body.get(k):
                        msg = body[k]
                        break
            if not msg:
                msg = resp.text[:200] if resp.text else f"HTTP {resp.status_code}"
            raise WorkDoError(msg)

        # 2. 自動由登入回應解析租戶 ID (Tenant ID)
        try:
            bdd_user_data = body.get("bddUserData") or {}
            last_did = bdd_user_data.get("lastDid")
            did_list = bdd_user_data.get("didList") or []

            if last_did and last_did != "11111111":
                self.tenant_id = str(last_did)
                logger.debug(f"由 lastDid 取得 Tenant ID: {self.tenant_id}")
            else:
                valid_dids = [d for d in did_list if d and d != "11111111"]
                if valid_dids:
                    self.tenant_id = str(valid_dids[0])
                    logger.debug(f"由 didList 取得 Tenant ID: {self.tenant_id}")
                else:
                    sky_info = body.get("skyWebInfo") or {}
                    tenant_list = sky_info.get("tenantList") or []
                    if tenant_list:
                        self.tenant_id = str(tenant_list[0].get("tid") or tenant_list[0].get("tenantId") or self.tenant_id)
                        logger.debug(f"由 tenantList 取得 Tenant ID: {self.tenant_id}")
        except Exception as e:
            logger.debug(f"解析 Tenant ID 失敗，保留預設值: {e}")

        self.is_logged_in = True
        user_name = body.get("skyWebInfo", {}).get("dispUserNickname") or body.get("skyWebInfo", {}).get("name") or self.email
        logger.debug(f"使用者 {user_name} ({self.email}) 登入成功！(Tenant ID: {self.tenant_id})")
        return body

    def ensure_logged_in(self) -> None:
        """Ensure session is logged in."""
        if not self.is_logged_in:
            self.login()

    def _get_api_headers(self) -> Dict[str, str]:
        """Headers required for CCN API calls."""
        return {
            "Host": "www.workdo.co",
            "tenant_id": self.tenant_id,
            "timezone": "GMT+0800",
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": self.USER_AGENT,
            "Content-Type": "application/json;charset=UTF-8",
        }

    def query_punch_status(self) -> Dict[str, Optional[str]]:
        """
        Query today's punch status from WorkDo server.
        Returns:
            {"ClockIn": "YYYY-MM-DD HH:MM:SS+0800" or None, "ClockOut": ... or None}
        """
        self.ensure_logged_in()
        headers = self._get_api_headers()

        try:
            resp = self.session.post(self.URL_PUNCH_STATUS, headers=headers, json={}, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            raise WorkDoError(f"查詢今日打卡狀態失敗: {e}")

        result: Dict[str, Optional[str]] = {"ClockIn": None, "ClockOut": None}
        records = data.get("list") or []

        for item in records:
            p_type = item.get("type")
            p_time = item.get("punchTime")
            if p_type in result:
                result[p_type] = p_time if p_time else None

        return result

    def punch_with_validation(self, clock_type: str, force: bool = False) -> Dict[str, Any]:
        """
        Punch clock with pre-check and post-verification.
        Args:
            clock_type: "ClockIn" or "ClockOut"
            force: Force punch even if existing record is found
        Returns:
            {"clock_type": clock_type, "was_punched": bool, "punch_time": str, "message": str}
        """
        self.ensure_logged_in()

        # Step 1: Check existing punch status
        status = self.query_punch_status()
        existing_time = status.get(clock_type)

        if existing_time and not force:
            logger.debug(f"今日已於 {existing_time} 完成 {clock_type} 打卡，略過重複送出。")
            return {
                "clock_type": clock_type,
                "was_punched": False,
                "punch_time": existing_time,
                "message": f"今日已於 {existing_time} 完成打卡，略過重複打卡。"
            }

        # Step 2: Send punch request
        headers = self._get_api_headers()
        payload = {
            "type": clock_type,
            "place": "OtherCity",
            "gpsLocation": {
                "text": Config.GPS_LOCATION
            },
            "gpsPlace": Config.GPS_PLACE
        }

        logger.debug(
            f"正在發送 {clock_type} 打卡請求: 地點={Config.GPS_PLACE}, GPS={Config.GPS_LOCATION}"
        )

        try:
            resp = self.session.post(self.URL_PUNCH, headers=headers, json=payload, timeout=20)
            if resp.status_code != 200:
                # 如實捕捉伺服器錯誤訊息
                err_msg = None
                try:
                    err_json = resp.json()
                    err_msg = err_json.get("localizedMessage") or err_json.get("message")
                except Exception:
                    pass
                if not err_msg:
                    err_msg = resp.text.strip() if resp.text else f"HTTP {resp.status_code}"
                raise WorkDoError(err_msg)
        except WorkDoError:
            raise
        except Exception as e:
            raise WorkDoError(str(e))

        # Step 3: Verify punch status on server
        verified_status = self.query_punch_status()
        verified_time = verified_status.get(clock_type)
        if not verified_time:
            raise WorkDoError(f"{clock_type} 打卡已送出，但 WorkDo 紀錄未更新，請登入檢查。")

        logger.debug(f"{clock_type} 驗證成功，紀錄時間: {verified_time}")
        return {
            "clock_type": clock_type,
            "was_punched": True,
            "punch_time": verified_time,
            "message": f"{clock_type} 打卡成功！紀錄時間: {verified_time}"
        }

    def supplement_missing_punches(self) -> int:
        """
        Query and supplement any missing punch records (自動補送缺卡紀錄).
        Returns number of supplemented records.
        """
        self.ensure_logged_in()
        headers = self._get_api_headers()

        try:
            resp = self.session.post(
                self.URL_MISSING_PUNCH_QUERY,
                headers=headers,
                json={"displayName": "ClockPunchReq"},
                timeout=20
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning(f"查詢缺卡紀錄失敗: {e}")
            return 0

        records: List[Dict[str, Any]] = data.get("list") or []
        missing_records = [
            r for r in records if str(r.get("result", "")).lower() == "missing"
        ]

        if not missing_records:
            return 0

        logger.debug(f"偵測到 {len(missing_records)} 筆缺卡紀錄，正在自動補送...")
        supplemented = 0

        save_headers = dict(headers)
        save_headers.update({
            "brandName": "WorkDo",
            "app_version_code": self.APP_VERSION,
            "userLocale": "zh_TW",
            "Origin": "https://www.workdo.co",
            "Referer": f"https://www.workdo.co/ccnaweb/?ver={self.APP_VERSION}/",
        })

        for record in missing_records:
            punch_day = record.get("punchDay")
            r_type = record.get("type", "ClockIn")
            configured_time = Config.CLOCK_OUT_TIME if r_type.lower() == "clockout" else Config.CLOCK_IN_TIME

            req_time = None
            if punch_day and configured_time:
                req_time = f"{punch_day} {configured_time}:00+0800"
            else:
                req_time = record.get("reqPunchTime") or record.get("punchTime")

            req_gps_place = Config.GPS_PLACE or record.get("reqGpsPlace") or record.get("place")
            req_location = {"text": Config.GPS_LOCATION}

            payload = {
                "reqOid": record.get("reqOid"),
                "punchDay": punch_day,
                "reqPunchTime": req_time,
                "reqPlace": "OtherCity",
                "reqOidEnc": record.get("reqOidEnc"),
                "type": r_type,
                "fileInfoList": record.get("fileInfoList") or [],
                "reqWifiPoint": record.get("reqWifiPoint"),
                "reqWifiMac": record.get("reqWifiMac"),
                "reqGpsPlace": req_gps_place,
                "reqGpsLocation": req_location,
                "reqFaceDeviceName": record.get("reqFaceDeviceName"),
                "reqFaceDeviceOid": record.get("reqFaceDeviceOid")
            }

            try:
                sub_resp = self.session.post(self.URL_MISSING_PUNCH_SAVE, headers=save_headers, json=payload, timeout=20)
                sub_resp.raise_for_status()
                supplemented += 1
                logger.debug(f"成功補送缺卡: 日期={punch_day}, 類型={r_type}, 時間={req_time}")
            except Exception as e:
                logger.warning(f"補送缺卡紀錄失敗 (日期={punch_day}): {e}")

        if supplemented > 0:
            logger.info(f"缺卡自動補登完成：共成功補送 {supplemented} 筆缺卡紀錄。")

        return supplemented

    def fetch_holidays(self) -> Set[str]:
        """
        Fetch holiday dates from iCal calendar URL.
        Returns set of date strings in 'YYYY-MM-DD' format.
        """
        if self._holidays_cache is not None:
            return self._holidays_cache

        holidays: Set[str] = set()
        url = Config.HOLIDAY_CALENDAR_URL
        if not url:
            self._holidays_cache = holidays
            return holidays

        try:
            resp = self.session.get(url, headers={"User-Agent": self.USER_AGENT}, timeout=15)
            resp.raise_for_status()
            content = resp.text

            # 展開 iCal 換行折疊格式
            content = re.sub(r"\r?\n[ \t]", "", content)
            events = re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", content, re.DOTALL)

            for ev in events:
                if "Monthly Step-Up Challenge" in ev:
                    continue

                m_start = re.search(r"DTSTART(?:;[^:]*)?:(\d{8}(?:T\d{6}Z?)?)", ev)
                m_end = re.search(r"DTEND(?:;[^:]*)?:(\d{8}(?:T\d{6}Z?)?)", ev)
                if not m_start:
                    continue

                s_val = m_start.group(1)[:8]
                try:
                    s_date = datetime.strptime(s_val, "%Y%m%d").date()
                except ValueError:
                    continue

                if m_end:
                    e_val = m_end.group(1)[:8]
                    try:
                        e_date = datetime.strptime(e_val, "%Y%m%d").date()
                        is_date_only = "VALUE=DATE" in (re.search(r"DTEND([^:]*):", ev).group(1) if re.search(r"DTEND([^:]*):", ev) else "")
                        if is_date_only or e_date > s_date:
                            e_date = e_date - timedelta(days=1)
                        if e_date < s_date:
                            e_date = s_date
                    except ValueError:
                        e_date = s_date
                else:
                    e_date = s_date

                curr = s_date
                while curr <= e_date:
                    holidays.add(curr.strftime("%Y-%m-%d"))
                    curr += timedelta(days=1)

            logger.debug(f"成功自行事曆讀取 {len(holidays)} 個國定假日/休假日期。")
        except Exception as e:
            logger.warning(f"讀取國定假日行事曆失敗: {e}")

        self._holidays_cache = holidays
        return holidays

    def is_workday(self, target_date: Optional[date] = None) -> bool:
        """
        Check if given date (default Taipei current date) is a workday.
        Checks:
        1. Weekday in configured WORKDAYS (1=Monday ... 7=Sunday)
        2. Not in holiday list (if ENABLE_HOLIDAY_CHECK is True)
        """
        if target_date is None:
            # 確保使用台北時區之當前日期，避免非 UTC+8 伺服器誤判
            try:
                from scheduler import get_current_taipei_time
                target_date = get_current_taipei_time().date()
            except Exception:
                target_date = date.today()

        iso_weekday = target_date.isoweekday()
        if iso_weekday not in Config.WORKDAYS:
            logger.debug(f"日期 {target_date} (星期 {iso_weekday}) 不在設定之工作日 {Config.WORKDAYS} 內。")
            return False

        if Config.ENABLE_HOLIDAY_CHECK:
            holidays = self.fetch_holidays()
            date_str = target_date.strftime("%Y-%m-%d")
            if date_str in holidays:
                logger.debug(f"日期 {target_date} 為行事曆休假/國定假日。")
                return False

        return True
