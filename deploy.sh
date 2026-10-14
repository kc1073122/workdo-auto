#!/usr/bin/env bash
set -e

PI_HOST="${1:-192.168.68.65}"
PI_USER="${2:-bot}"
REMOTE_DIR="/home/$PI_USER/workdo-auto"
LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================================="
echo "  WorkDoAuto 樹莓派部署程式 (Systemd Timers / Linux)"
echo "  目標主機: $PI_USER@$PI_HOST"
echo "  目標目錄: $REMOTE_DIR"
echo "=========================================================="

# 1. 檢查連線
echo "[1/5] 檢查樹莓派連線..."
ssh -o ConnectTimeout=5 "$PI_USER@$PI_HOST" "echo '連線正常: \$(uname -n)'"

# 2. 建立遠端目錄
echo "[2/5] 建立遠端工作目錄..."
ssh "$PI_USER@$PI_HOST" "mkdir -p $REMOTE_DIR/logs $REMOTE_DIR/systemd"

# 3. 同步程式碼 (排除 venv、logs、.git、.env)
echo "[3/5] 同步程式碼至樹莓派..."
rsync -avz --exclude 'venv' \
          --exclude 'logs' \
          --exclude '__pycache__' \
          --exclude '.git' \
          --exclude '.env' \
          --exclude '.DS_Store' \
          "$LOCAL_DIR/" "$PI_USER@$PI_HOST:$REMOTE_DIR/"

# 4. 在樹莓派上設定 Python 虛擬環境與安裝依賴套件
echo "[4/5] 遠端安裝 Python 依賴環境..."
ssh "$PI_USER@$PI_HOST" "bash -s" << 'EOF'
set -e
cd /home/bot/workdo-auto
if [ ! -d "venv" ]; then
    echo "正在建立 Python 3 虛擬環境 (venv)..."
    python3 -m venv venv
fi
echo "正在安裝/更新 Python 套件..."
./venv/bin/pip install --upgrade pip --quiet
./venv/bin/pip install -r requirements.txt --quiet
chmod +x main.py setup_cron.sh setup_systemd.sh
EOF

# 5. 檢查 .env 設定檔與安裝 Systemd Timers 排程
echo "[5/5] 設定環境與排程..."
ssh "$PI_USER@$PI_HOST" "bash -s" << 'EOF'
set -e
cd /home/bot/workdo-auto
if [ ! -f ".env" ]; then
    echo "注意: 樹莓派尚未建立 .env 設定檔，已自動由 .env.example 複製。"
    cp .env.example .env
    echo ">>> 請務必在樹莓派上編輯 .env 填入你的 WorkDo 帳號密碼！<<<"
fi

echo "正在安裝 Systemd Timers (工作日 09:00 上班 / 18:00 下班)..."
./setup_systemd.sh 1
EOF

echo ""
echo "=========================================================="
echo "部署完成！"
echo ""
echo "常用操作提示："
echo "1. 測試登入狀態:"
echo "   ssh $PI_USER@$PI_HOST \"$REMOTE_DIR/venv/bin/python $REMOTE_DIR/main.py test-login\""
echo ""
echo "2. 查詢今日打卡狀態:"
echo "   ssh $PI_USER@$PI_HOST \"$REMOTE_DIR/venv/bin/python $REMOTE_DIR/main.py status\""
echo ""
echo "3. 手動測試打上班卡 / 下班卡:"
echo "   ssh $PI_USER@$PI_HOST \"$REMOTE_DIR/venv/bin/python $REMOTE_DIR/main.py punch-in\""
echo "   ssh $PI_USER@$PI_HOST \"$REMOTE_DIR/venv/bin/python $REMOTE_DIR/main.py punch-out\""
echo ""
echo "4. 查看 Systemd 定時器排程狀態:"
echo "   ssh $PI_USER@$PI_HOST \"systemctl --user list-timers | grep workdo\""
echo ""
echo "5. 查看執行日誌:"
echo "   ssh $PI_USER@$PI_HOST \"tail -n 30 -f $REMOTE_DIR/logs/workdo.log\""
echo "=========================================================="
