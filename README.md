# WorkDoAuto for Linux / Raspberry Pi

本專案參考 [akitosun/WorkDoAuto](https://github.com/akitosun/WorkDoAuto.git) 的打卡與驗證邏輯，改寫為適合 Linux 及樹莓派（Raspberry Pi）環境運行的輕量 Python 自動化打卡服務。

---

## 🌟 核心特色

1. **跨平台輕量化**：擺脫原先 Windows Forms / .NET Framework 4.7.2 與桌面視窗的依賴，專門為 Linux / 樹莓派無頭環境（Headless）設計。
2. **台北市政府 GPS 定位**：
   - 座標格式：`POINT (121.564451 25.037517)`
   - 地址：`台北市信義區市府路1號`
3. **工作日排程 (Systemd Timers)**：
   - 上班打卡：工作日（週一至週五）`09:00`
   - 下班打卡：工作日（週一至週五）`18:00`
4. **彈性下班支援**：若早上上班打卡延遲（例如 09:05），下班時間自動等比例順延（18:05），提早打卡則不提前。
5. **國定假日自動偵測**：自動同步 WorkDo 或 iCal 行事曆，國定假日與週末自動休假不打卡。
6. **防重複打卡機制**：每次送出前先向 WorkDo 查詢當日打卡狀態，已打過卡時自動略過。
7. **缺卡自動補打**：自動查詢缺卡申請並依照設定自動補登。
8. **嚴格分級推播與原始報錯**：
   - **Log 分級**：只有 `DEBUG` 保留於本地日誌，`INFO`、`WARNING`、`ERROR`、`CRITICAL` 自動推播至 Discord Webhook、Telegram 或 LINE Notify。
   - **原始報錯**：WorkDo API 回傳之錯誤代碼與伺服器訊息（如缺上班卡無法下班等）如實呈現於日誌與推播，不作多餘轉譯。
9. **完整單元測試**：內建完整單元測試套件（Config、Notifier、Scheduler、Client、Main CLI），零額外第三方測試依賴。

---

## 📁 專案結構

```text
workdo-auto/
├── .env.example              # 設定檔範本
├── config.py                 # 設定檔讀取器與參數驗證
├── workdo_client.py          # WorkDo API 客戶端（登入、查狀態、打卡、缺卡補登、假日解析）
├── scheduler.py              # 排程計算與彈性下班等待邏輯
├── notifier.py               # 分級推播通知與 Rotating Log 模組
├── main.py                   # 命令行工具主入口 (支援 aliases)
├── requirements.txt          # Python 依賴清單
├── deploy.sh                 # 一鍵部署至樹莓派 (192.168.68.65)
├── setup_systemd.sh          # Systemd 服務/定時器安裝腳本
├── tests/                    # 單元測試套件 (27+ tests)
│   ├── test_config.py
│   ├── test_notifier.py
│   ├── test_scheduler.py
│   ├── test_workdo_client.py
│   └── test_main.py
└── systemd/                  # Systemd 設定檔目錄
    ├── workdo-clockin.service
    ├── workdo-clockin.timer
    ├── workdo-clockout.service
    ├── workdo-clockout.timer
    └── workdo-auto.service
```

---

## 🚀 部署至樹莓派 (192.168.68.65)

在本地端（Mac）的 `~/Documents/codes/workdo-auto` 目錄下執行：

```bash
chmod +x deploy.sh setup_systemd.sh main.py
./deploy.sh 192.168.68.65 bot
```

部署程式將會：
1. 透過 SSH 檢查樹莓派連線
2. 同步程式碼至 `/home/bot/workdo-auto`
3. 在樹莓派上建立專屬 Python 虛擬環境 (`venv`) 並安裝依賴套件
4. 自動配置工作日 `09:00` 上班與 `18:00` 下班的 **Systemd Timers** 定時器排程

---

## ⚙️ 設定檔說明 (.env)

連線至樹莓派編輯設定檔：

```bash
ssh bot@192.168.68.65
cd ~/workdo-auto
nano .env
```

核心參數配置範例：

```ini
# WorkDo 登入資訊（必填）
WORKDO_EMAIL=your_account@company.com
WORKDO_PASSWORD=your_password

# 打卡時間設定 (HH:MM)
CLOCK_IN_TIME=09:00
CLOCK_OUT_TIME=18:00

# 工作日設定 (1=週一, 2=週二, 3=週三, 4=週四, 5=週五)
WORKDAYS=1,2,3,4,5

# 彈性下班時間 (true/false)
ENABLE_FLEXIBLE_CLOCK_OUT=true

# GPS 打卡資訊 (已預設為台北市政府)
GPS_LOCATION="POINT (121.564451 25.037517)"
GPS_PLACE="台北市信義區市府路1號"

# 國定假日與缺卡自動補送
ENABLE_HOLIDAY_CHECK=true
ENABLE_MISSING_PUNCH_SUPPLEMENT=true

# 通知管道 (選填)
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
LINE_NOTIFY_TOKEN=
```

---

## 💻 常用 CLI 操作指令

在樹莓派上可直接透過 `main.py` 進行測試與操作：

### 1. 測試帳號密碼登入
```bash
~/workdo-auto/venv/bin/python ~/workdo-auto/main.py test-login
```

### 2. 查詢今日打卡狀態
```bash
~/workdo-auto/venv/bin/python ~/workdo-auto/main.py status
```

### 3. 手動執行上班打卡
```bash
~/workdo-auto/venv/bin/python ~/workdo-auto/main.py punch-in
# 或使用縮寫別名
~/workdo-auto/venv/bin/python ~/workdo-auto/main.py in
```
> 若欲強制打卡（忽略假日或防重複打卡檢查），可加上 `--force`。

### 4. 手動執行下班打卡
```bash
~/workdo-auto/venv/bin/python ~/workdo-auto/main.py punch-out --flexible
# 或使用縮寫別名
~/workdo-auto/venv/bin/python ~/workdo-auto/main.py out --flexible
```

### 5. 執行單元測試
```bash
~/workdo-auto/venv/bin/python -m unittest discover -s tests
```

### 6. 查看排程定時器與執行日誌
```bash
# 查看 Systemd 定時器排程
systemctl --user list-timers | grep workdo

# 查看即時日誌
tail -n 50 -f ~/workdo-auto/logs/workdo.log
tail -n 50 -f ~/workdo-auto/logs/systemd.log
```
