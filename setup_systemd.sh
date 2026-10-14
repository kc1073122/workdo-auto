#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$DIR/logs"

USER_SYSTEMD_DIR="$HOME/.config/systemd/user"
mkdir -p "$USER_SYSTEMD_DIR"

# Ensure user lingering is active so user systemd timers survive reboots
loginctl enable-linger "$USER" 2>/dev/null || true

MODE="${1:-1}"

if [ "$MODE" == "1" ]; then
    echo "正在安裝 Systemd Timers (定時器模式)..."
    cp "$DIR/systemd/workdo-clockin.service" "$USER_SYSTEMD_DIR/"
    cp "$DIR/systemd/workdo-clockin.timer" "$USER_SYSTEMD_DIR/"
    cp "$DIR/systemd/workdo-clockout.service" "$USER_SYSTEMD_DIR/"
    cp "$DIR/systemd/workdo-clockout.timer" "$USER_SYSTEMD_DIR/"

    systemctl --user daemon-reload
    systemctl --user enable --now workdo-clockin.timer
    systemctl --user enable --now workdo-clockout.timer

    echo "=============================================="
    echo "Systemd Timers 安裝並啟動完成！"
    echo "查看定時器排程: systemctl --user list-timers | grep workdo"
    echo "查看執行日誌: tail -f $DIR/logs/systemd.log"
    echo "=============================================="
else
    echo "正在安裝 Systemd Daemon (常駐模式)..."
    cp "$DIR/systemd/workdo-auto.service" "$USER_SYSTEMD_DIR/"

    systemctl --user daemon-reload
    systemctl --user enable --now workdo-auto.service

    echo "=============================================="
    echo "Systemd Daemon 服務安裝並啟動完成！"
    echo "查看服務狀態: systemctl --user status workdo-auto"
    echo "查看執行日誌: journalctl --user -u workdo-auto -f"
    echo "=============================================="
fi
