"""Scheduling and flexible clock-out utilities."""

import time
from datetime import datetime, date, timedelta
from typing import Optional, Tuple

try:
    from zoneinfo import ZoneInfo
    TAIPEI_TZ = ZoneInfo("Asia/Taipei")
except ImportError:
    import pytz
    TAIPEI_TZ = pytz.timezone("Asia/Taipei")

from config import Config
from notifier import logger

def get_current_taipei_time() -> datetime:
    """Get current datetime in Asia/Taipei timezone."""
    return datetime.now(TAIPEI_TZ)

def parse_workdo_punch_time(punch_time_str: str) -> Optional[datetime]:
    """
    Parse WorkDo punch time string.
    Example: '2026-10-14 09:05:22+0800' or '2026-10-14 09:05:22'
    """
    if not punch_time_str:
        return None

    cleaned = punch_time_str.strip()
    formats = [
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S%z",
        "%Y/%m/%d %H:%M:%S",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(cleaned, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=TAIPEI_TZ)
            else:
                dt = dt.astimezone(TAIPEI_TZ)
            return dt
        except ValueError:
            continue
    return None

def compute_scheduled_clock_out(actual_clock_in_str: Optional[str]) -> Tuple[datetime, int]:
    """
    Compute target clock-out datetime for today based on flexible clock-out rules.
    If actual clock-in was later than scheduled CLOCK_IN_TIME, clock-out is delayed by the same duration.
    If actual clock-in was earlier or on-time, default CLOCK_OUT_TIME is used (no early leave).

    Returns:
        (target_clock_out_datetime, delay_minutes)
    """
    now = get_current_taipei_time()
    today = now.date()

    out_h, out_m = Config.get_clock_out_tuple()
    base_clock_out = datetime(today.year, today.month, today.day, out_h, out_m, 0, tzinfo=TAIPEI_TZ)

    if not Config.ENABLE_FLEXIBLE_CLOCK_OUT or not actual_clock_in_str:
        return base_clock_out, 0

    actual_clock_in = parse_workdo_punch_time(actual_clock_in_str)
    if not actual_clock_in:
        return base_clock_out, 0

    in_h, in_m = Config.get_clock_in_tuple()
    expected_clock_in = datetime(today.year, today.month, today.day, in_h, in_m, 0, tzinfo=TAIPEI_TZ)

    diff = actual_clock_in - expected_clock_in
    if diff > timedelta(0):
        target_clock_out = base_clock_out + diff
        delay_sec = int(diff.total_seconds())
        delay_min = delay_sec // 60
        logger.info(
            f"今日實際上班打卡時間為 {actual_clock_in.strftime('%H:%M:%S')} (延後 {delay_min} 分鐘)，"
            f"彈性下班時間順延至 {target_clock_out.strftime('%H:%M:%S')}。"
        )
        return target_clock_out, delay_min

    logger.info(f"今日上班打卡正常或提早 ({actual_clock_in.strftime('%H:%M:%S')})，下班時間維持預設 {Config.CLOCK_OUT_TIME}。")
    return base_clock_out, 0

def wait_until_target_time(target_time: datetime, max_wait_seconds: int = 7200) -> None:
    """
    Wait until target datetime is reached.
    If already passed, returns immediately.
    Caps waiting time to max_wait_seconds to prevent indefinite hangs.
    """
    now = get_current_taipei_time()
    wait_seconds = (target_time - now).total_seconds()

    if wait_seconds <= 0:
        return

    if wait_seconds > max_wait_seconds:
        logger.warning(f"等待時間 ({wait_seconds:.0f}s) 超過上限 ({max_wait_seconds}s)，調整為上限。")
        wait_seconds = max_wait_seconds

    logger.info(f"等待中...預計於 {target_time.strftime('%H:%M:%S')} 執行打卡 (尚需等待 {int(wait_seconds)} 秒)")
    time.sleep(wait_seconds)
