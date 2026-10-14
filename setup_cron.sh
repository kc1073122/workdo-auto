#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_EXEC="$DIR/venv/bin/python"
MAIN_SCRIPT="$DIR/main.py"
LOG_FILE="$DIR/logs/cron.log"

if [ ! -f "$PYTHON_EXEC" ]; then
    echo "Python 虛擬環境不存在，正在建立..."
    python3 -m venv "$DIR/venv"
    "$DIR/venv/bin/pip" install --upgrade pip
    "$DIR/venv/bin/pip" install -r "$DIR/requirements.txt"
fi

mkdir -p "$DIR/logs"

# Prepare crontab lines
CRON_IN="0 9 * * 1-5 $PYTHON_EXEC $MAIN_SCRIPT punch-in >> $LOG_FILE 2>&1"
CRON_OUT="0 18 * * 1-5 $PYTHON_EXEC $MAIN_SCRIPT punch-out --flexible >> $LOG_FILE 2>&1"

# Read existing crontab
EXISTING_CRON=$(crontab -l 2>/dev/null || true)

# Remove old workdo-auto entries if any
NEW_CRON=$(echo "$EXISTING_CRON" | grep -v "workdo-auto" | grep -v "$MAIN_SCRIPT" || true)

# Add new entries
NEW_CRON=$(cat <<EOF
$NEW_CRON
# WorkDoAuto 打卡排程 (工作日 Mon-Fri 09:00 上班卡, 18:00 下班卡)
$CRON_IN
$CRON_OUT
EOF
)

# Install new crontab
echo "$NEW_CRON" | sed '/^$/N;/^\n$/D' | crontab -

echo "=============================================="
echo "Crontab 排程安裝成功！"
echo "已設定工作日 (週一至週五)："
echo "  - 09:00 上班打卡"
echo "  - 18:00 下班打卡 (啟用彈性下班等待)"
echo "查看目前 crontab: crontab -l"
echo "查看執行日誌: tail -f $LOG_FILE"
echo "=============================================="
