#!/usr/bin/env python3
"""WorkDoAuto CLI Entrypoint."""

import argparse
import sys
import time
from datetime import datetime, date, time as dtime
from typing import Optional

from config import Config
from notifier import logger, notify
from workdo_client import WorkDoClient, WorkDoError
from scheduler import (
    get_current_taipei_time,
    compute_scheduled_clock_out,
    wait_until_target_time,
)

def _check_workday_guard(client: WorkDoClient, force: bool, action_name: str) -> bool:
    """
    Check if today is a workday.
    Returns True if execution should proceed, False if it should be skipped.
    """
    today = get_current_taipei_time().date()
    if not force and not client.is_workday(today):
        logger.info(f"今天 ({today}) 非工作日或為國定假日，略過{action_name}。")
        return False
    return True

def handle_punch_in(args: argparse.Namespace) -> int:
    """Handle clock-in punch."""
    Config.validate_credentials()
    client = WorkDoClient()

    if not _check_workday_guard(client, args.force, "上班打卡"):
        return 0

    try:
        client.login()

        if Config.ENABLE_MISSING_PUNCH_SUPPLEMENT:
            client.supplement_missing_punches()

        result = client.punch_with_validation("ClockIn", force=args.force)
        title = "上班打卡成功" if result["was_punched"] else "上班打卡狀態"
        logger.info(f"{title}: {result['message']}")
        return 0
    except WorkDoError as e:
        logger.error(f"上班打卡失敗: {e}")
        return 1
    except Exception as e:
        logger.exception(f"上班打卡發生未預期錯誤: {e}")
        return 1

def handle_punch_out(args: argparse.Namespace) -> int:
    """Handle clock-out punch."""
    Config.validate_credentials()
    client = WorkDoClient()

    if not _check_workday_guard(client, args.force, "下班打卡"):
        return 0

    try:
        client.login()

        if Config.ENABLE_MISSING_PUNCH_SUPPLEMENT:
            client.supplement_missing_punches()

        status = client.query_punch_status()
        existing_out = status.get("ClockOut")
        if existing_out and not args.force:
            logger.info(f"今日已於 {existing_out} 完成下班打卡，跳過重複打卡。")
            return 0

        # Handle flexible clock-out
        if args.flexible or Config.ENABLE_FLEXIBLE_CLOCK_OUT:
            clock_in_time = status.get("ClockIn")
            target_out_dt, delay_min = compute_scheduled_clock_out(clock_in_time)
            wait_until_target_time(target_out_dt)

        result = client.punch_with_validation("ClockOut", force=args.force)
        title = "下班打卡成功" if result["was_punched"] else "下班打卡狀態"
        logger.info(f"{title}: {result['message']}")
        return 0
    except WorkDoError as e:
        logger.error(f"下班打卡失敗: {e}")
        return 1
    except Exception as e:
        logger.exception(f"下班打卡發生未預期錯誤: {e}")
        return 1

def handle_status(args: argparse.Namespace) -> int:
    """Query today's punch status."""
    Config.validate_credentials()
    client = WorkDoClient()

    try:
        client.login()
        status = client.query_punch_status()
        today = get_current_taipei_time().date()
        is_work = client.is_workday(today)

        print("\n" + "=" * 48)
        print("           WorkDo 今日打卡狀態")
        print("=" * 48)
        print(f"日期:        {today.strftime('%Y-%m-%d')} (工作日: {'是' if is_work else '否/假日'})")
        print(f"設定上班時間: {Config.CLOCK_IN_TIME}")
        print(f"設定下班時間: {Config.CLOCK_OUT_TIME} (彈性下班: {'已啟用' if Config.ENABLE_FLEXIBLE_CLOCK_OUT else '未啟用'})")
        print(f"GPS 打卡點:   {Config.GPS_PLACE} ({Config.GPS_LOCATION})")
        print("-" * 48)
        in_res = status.get("ClockInResult")
        out_res = status.get("ClockOutResult")
        in_display = f"請假 ({in_res})" if str(in_res).lower() == "leave" else (status.get('ClockIn') or '尚未打卡')
        out_display = f"請假 ({out_res})" if str(out_res).lower() == "leave" else (status.get('ClockOut') or '尚未打卡')
        print(f"今日上班卡:   {in_display}")
        print(f"今日下班卡:   {out_display}")
        print("=" * 48 + "\n")
        return 0
    except Exception as e:
        logger.error(f"查詢狀態失敗: {e}")
        return 1

def handle_test_login(args: argparse.Namespace) -> int:
    """Test WorkDo login credentials."""
    Config.validate_credentials()
    client = WorkDoClient()

    try:
        data = client.login()
        user_name = data.get("skyWebInfo", {}).get("dispUserNickname") or data.get("skyWebInfo", {}).get("name") or Config.EMAIL
        print(f"[SUCCESS] 登入成功！使用者: {user_name}, Tenant ID: {client.tenant_id}")
        return 0
    except Exception as e:
        print(f"[FAIL] 登入失敗: {e}")
        return 1

def handle_daemon(args: argparse.Namespace) -> int:
    """Run WorkDoAuto in persistent daemon loop with safe time comparison."""
    Config.validate_credentials()
    logger.info("WorkDoAuto 常駐守護進程啟動中...")
    logger.info(f"上班時間: {Config.CLOCK_IN_TIME}, 下班時間: {Config.CLOCK_OUT_TIME}, 工作日: {Config.WORKDAYS}")
    logger.info(f"打卡地點: {Config.GPS_PLACE}")

    last_punched_in_date: Optional[date] = None
    last_punched_out_date: Optional[date] = None

    while True:
        try:
            now = get_current_taipei_time()
            today = now.date()
            curr_time = now.time()

            in_h, in_m = Config.get_clock_in_tuple()
            out_h, out_m = Config.get_clock_out_tuple()

            target_in_time = dtime(in_h, in_m)
            target_out_time = dtime(out_h, out_m)

            client = WorkDoClient()

            # 僅於工作日執行打卡排程
            if client.is_workday(today):
                # 1. 上班打卡檢查 (到達上班時間且今日尚未打卡)
                if last_punched_in_date != today and curr_time >= target_in_time:
                    logger.info("觸發上班打卡排程...")
                    args_mock = argparse.Namespace(force=False)
                    res = handle_punch_in(args_mock)
                    if res == 0:
                        last_punched_in_date = today

                # 2. 下班打卡檢查 (到達下班時間且今日尚未打卡)
                if last_punched_out_date != today and curr_time >= target_out_time:
                    logger.info("觸發下班打卡排程...")
                    args_mock = argparse.Namespace(force=False, flexible=Config.ENABLE_FLEXIBLE_CLOCK_OUT)
                    res = handle_punch_out(args_mock)
                    if res == 0:
                        last_punched_out_date = today

            # 每 30 秒輪詢一次
            time.sleep(30)
        except KeyboardInterrupt:
            logger.info("接收到中斷訊號，守護進程停止。")
            break
        except Exception as e:
            logger.error(f"守護進程發生異常: {e}")
            time.sleep(60)

    return 0

def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="workdo-auto",
        description="WorkDoAuto: Headless Automatic Punch System for Linux / Raspberry Pi"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # punch-in
    p_in = subparsers.add_parser("punch-in", aliases=["in"], help="執行上班打卡")
    p_in.add_argument("--force", action="store_true", help="強制打卡（忽略假日/工作日檢查及重複檢查）")
    p_in.set_defaults(func=handle_punch_in)

    # punch-out
    p_out = subparsers.add_parser("punch-out", aliases=["out"], help="執行下班打卡")
    p_out.add_argument("--force", action="store_true", help="強制打卡（忽略假日/工作日檢查及重複檢查）")
    p_out.add_argument("--flexible", action="store_true", help="啟用彈性下班等待（依上班打卡延遲時間順延）")
    p_out.set_defaults(func=handle_punch_out)

    # status
    p_status = subparsers.add_parser("status", help="查詢今日打卡狀態")
    p_status.set_defaults(func=handle_status)

    # test-login
    p_test = subparsers.add_parser("test-login", help="測試 WorkDo 帳號密碼登入")
    p_test.set_defaults(func=handle_test_login)

    # daemon
    p_daemon = subparsers.add_parser("daemon", help="以背景守護程式持續執行排程")
    p_daemon.set_defaults(func=handle_daemon)

    return parser

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    code = args.func(args)
    sys.exit(code)

if __name__ == "__main__":
    main()
