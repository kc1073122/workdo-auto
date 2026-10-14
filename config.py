"""Configuration loader for WorkDoAuto."""

import os
import re
import sys
from pathlib import Path
from typing import List, Tuple, Optional

PROJECT_DIR = Path(__file__).resolve().parent
ENV_PATH = PROJECT_DIR / ".env"

def _load_env_file(filepath: Path) -> None:
    """Fallback .env parser if python-dotenv is not installed."""
    if not filepath.exists():
        return
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass

def load_environment() -> None:
    """Load environment variables from .env file."""
    try:
        from dotenv import load_dotenv
        if ENV_PATH.exists():
            load_dotenv(dotenv_path=ENV_PATH, override=False)
        else:
            load_dotenv(override=False)
    except ImportError:
        _load_env_file(ENV_PATH)

load_environment()

def get_bool(key: str, default: bool = False) -> bool:
    """Parse a boolean environment variable."""
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in ("true", "1", "yes", "y", "on")

def get_list(key: str, default: Optional[List[int]] = None) -> List[int]:
    """Parse comma-separated integer list (e.g. WORKDAYS=1,2,3,4,5)."""
    val = os.getenv(key)
    if not val:
        return default or [1, 2, 3, 4, 5]
    try:
        return [int(x.strip()) for x in val.split(",") if x.strip()]
    except ValueError:
        return default or [1, 2, 3, 4, 5]

def parse_time_str(time_str: str, default_h: int = 9, default_m: int = 0) -> Tuple[int, int]:
    """
    Safely parse 'HH:MM' time string into (hour, minute) tuple.
    Falls back to (default_h, default_m) on invalid input.
    """
    if not time_str:
        return default_h, default_m
    m = re.match(r"^(\d{1,2}):(\d{1,2})$", time_str.strip())
    if m:
        h, mn = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mn <= 59:
            return h, mn
    return default_h, default_m

class Config:
    """Global configuration settings for WorkDoAuto."""

    # Credentials
    EMAIL: str = os.getenv("WORKDO_EMAIL", "").strip()
    PASSWORD: str = os.getenv("WORKDO_PASSWORD", "").strip()

    # Times
    CLOCK_IN_TIME: str = os.getenv("CLOCK_IN_TIME", "09:00").strip()
    CLOCK_OUT_TIME: str = os.getenv("CLOCK_OUT_TIME", "18:00").strip()
    WORKDAYS: List[int] = get_list("WORKDAYS", [1, 2, 3, 4, 5])
    ENABLE_FLEXIBLE_CLOCK_OUT: bool = get_bool("ENABLE_FLEXIBLE_CLOCK_OUT", True)

    # GPS: Taipei City Hall (台北市政府)
    GPS_LOCATION: str = os.getenv("GPS_LOCATION", "POINT (121.564451 25.037517)").strip()
    GPS_PLACE: str = os.getenv("GPS_PLACE", "台北市信義區市府路1號").strip()

    # Tenant & Calendar
    TENANT_ID: str = os.getenv("TENANT_ID", "aa6pd97f").strip()
    HOLIDAY_CALENDAR_URL: str = os.getenv(
        "HOLIDAY_CALENDAR_URL",
        "https://www.workdo.co/ical/6f0baf113c1f4f7088920d3ad32d5d543"
    ).strip()
    ENABLE_HOLIDAY_CHECK: bool = get_bool("ENABLE_HOLIDAY_CHECK", True)
    ENABLE_MISSING_PUNCH_SUPPLEMENT: bool = get_bool("ENABLE_MISSING_PUNCH_SUPPLEMENT", True)

    # Notifications
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    DISCORD_WEBHOOK_URL: str = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    LINE_NOTIFY_TOKEN: str = os.getenv("LINE_NOTIFY_TOKEN", "").strip()

    # Paths
    LOG_DIR: Path = PROJECT_DIR / "logs"

    @classmethod
    def get_clock_in_tuple(cls) -> Tuple[int, int]:
        """Return (hour, minute) for scheduled clock-in."""
        return parse_time_str(cls.CLOCK_IN_TIME, 9, 0)

    @classmethod
    def get_clock_out_tuple(cls) -> Tuple[int, int]:
        """Return (hour, minute) for scheduled clock-out."""
        return parse_time_str(cls.CLOCK_OUT_TIME, 18, 0)

    @classmethod
    def is_configured(cls) -> bool:
        """Check if essential credentials are set."""
        return bool(cls.EMAIL and cls.PASSWORD)

    @classmethod
    def validate_credentials(cls) -> None:
        """Validate credentials; exit process if not set (for CLI commands)."""
        if not cls.is_configured():
            print("[ERROR] 請在 .env 檔案中設定 WORKDO_EMAIL 與 WORKDO_PASSWORD！", file=sys.stderr)
            print("可複製 .env.example 為 .env 並填入帳號密碼。", file=sys.stderr)
            sys.exit(1)

    @classmethod
    def reload(cls) -> None:
        """Reload configuration from environment variables."""
        load_environment()
        cls.EMAIL = os.getenv("WORKDO_EMAIL", "").strip()
        cls.PASSWORD = os.getenv("WORKDO_PASSWORD", "").strip()
        cls.CLOCK_IN_TIME = os.getenv("CLOCK_IN_TIME", "09:00").strip()
        cls.CLOCK_OUT_TIME = os.getenv("CLOCK_OUT_TIME", "18:00").strip()
        cls.WORKDAYS = get_list("WORKDAYS", [1, 2, 3, 4, 5])
        cls.ENABLE_FLEXIBLE_CLOCK_OUT = get_bool("ENABLE_FLEXIBLE_CLOCK_OUT", True)
        cls.GPS_LOCATION = os.getenv("GPS_LOCATION", "POINT (121.564451 25.037517)").strip()
        cls.GPS_PLACE = os.getenv("GPS_PLACE", "台北市信義區市府路1號").strip()
        cls.TENANT_ID = os.getenv("TENANT_ID", "aa6pd97f").strip()
        cls.HOLIDAY_CALENDAR_URL = os.getenv(
            "HOLIDAY_CALENDAR_URL",
            "https://www.workdo.co/ical/6f0baf113c1f4f7088920d3ad32d5d543"
        ).strip()
        cls.ENABLE_HOLIDAY_CHECK = get_bool("ENABLE_HOLIDAY_CHECK", True)
        cls.ENABLE_MISSING_PUNCH_SUPPLEMENT = get_bool("ENABLE_MISSING_PUNCH_SUPPLEMENT", True)
        cls.TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        cls.TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        cls.DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
        cls.LINE_NOTIFY_TOKEN = os.getenv("LINE_NOTIFY_TOKEN", "").strip()
