"""Notification and logging utilities with level-based push filtering."""

import logging
import traceback
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Optional
import requests
from config import Config

Config.LOG_DIR.mkdir(parents=True, exist_ok=True)
log_file = Config.LOG_DIR / "workdo.log"

class WebhookPushHandler(logging.Handler):
    """
    推播處理器：
    - 規則：只有 DEBUG 等級不會推播，INFO、WARNING、ERROR、CRITICAL 都會自動推播至 Discord / Webhook。
    - 支援例外追蹤 (Traceback) 格式化與長訊息截斷防爆 (1900 字元)。
    """
    def __init__(self, level: int = logging.INFO):
        super().__init__(level)

    def emit(self, record: logging.LogRecord) -> None:
        # 僅排除 DEBUG，其餘層級均推播
        if record.levelno < logging.INFO:
            return

        level_icons = {
            logging.INFO: "ℹ️",
            logging.WARNING: "⚠️",
            logging.ERROR: "❌",
            logging.CRITICAL: "🚨",
        }
        icon = level_icons.get(record.levelno, "📢")
        time_str = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        msg = record.getMessage()

        # 若有包含例外堆疊資訊 (exc_info)，附加簡短堆疊日誌
        if record.exc_info:
            tb_lines = traceback.format_exception(*record.exc_info)
            msg += "\n\n```python\n" + "".join(tb_lines)[-800:] + "```"

        content = f"{icon} **【WorkDo 打卡服務】[{record.levelname}]**\n`{time_str}`\n{msg}"

        # Discord 單則訊息上限為 2000 字元，安全裁切為 1900 字元
        if len(content) > 1900:
            content = content[:1890] + "..."

        self._send_pushes(content)

    def _send_pushes(self, content: str) -> None:
        """發送推播至已啟用的通訊管道。"""
        # 1. Discord Webhook
        if Config.DISCORD_WEBHOOK_URL:
            try:
                requests.post(Config.DISCORD_WEBHOOK_URL, json={"content": content}, timeout=8)
            except Exception:
                pass

        # 2. Telegram
        if Config.TELEGRAM_BOT_TOKEN and Config.TELEGRAM_CHAT_ID:
            try:
                tg_url = f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}/sendMessage"
                # Discord markdown 轉為 Telegram 簡易文字相容
                tg_text = content.replace("**", "").replace("`", "")
                requests.post(tg_url, json={"chat_id": Config.TELEGRAM_CHAT_ID, "text": tg_text}, timeout=8)
            except Exception:
                pass

        # 3. LINE Notify
        if Config.LINE_NOTIFY_TOKEN:
            try:
                line_url = "https://notify-api.line.me/api/notify"
                headers = {"Authorization": f"Bearer {Config.LINE_NOTIFY_TOKEN}"}
                requests.post(line_url, headers=headers, data={"message": content}, timeout=8)
            except Exception:
                pass


logger = logging.getLogger("WorkDoAuto")
logger.setLevel(logging.DEBUG)
logger.propagate = False  # 防止重複冒泡至根 logger

# 避免重複掛載 Handlers (例如模組重載或重複引用時)
if not logger.handlers:
    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 1. 控制台輸出 (DEBUG 及以上)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 2. 本地滾動日誌 (5MB x 5 個備份，DEBUG 及以上)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 3. Webhook 外部推播處理器 (預設 INFO 及以上，DEBUG 不推播)
    webhook_handler = WebhookPushHandler(level=logging.INFO)
    logger.addHandler(webhook_handler)


def notify(title: str, message: str, level: int = logging.INFO) -> None:
    """相容舊有 notify 呼叫，直接以指定 log level 記錄並觸發推播。"""
    if level >= logging.CRITICAL:
        logger.critical(f"{title}: {message}")
    elif level >= logging.ERROR:
        logger.error(f"{title}: {message}")
    elif level >= logging.WARNING:
        logger.warning(f"{title}: {message}")
    elif level == logging.DEBUG:
        logger.debug(f"{title}: {message}")
    else:
        logger.info(f"{title}: {message}")
