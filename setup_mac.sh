#!/bin/bash
# 在 Mac 上執行一次即可：建 Python 環境、測試抓取、設定每天 23:47 自動執行
set -e
cd "$(dirname "$0")"
DIR="$(pwd)"

echo "① 建立 Python 環境"
python3 -m venv .venv
./.venv/bin/pip install --quiet --upgrade pip
./.venv/bin/pip install --quiet -r requirements.txt

echo "② 測試抓 KOCA"
./.venv/bin/python koca_weekly.py

echo "③ 測試推到 GitHub"
git add data docs
git diff --cached --quiet || git commit -q -m "更新 $(date +%F)"
git push origin main

echo "④ 設定每天 23:47 自動執行"
PLIST="$HOME/Library/LaunchAgents/com.salmonstar.koca-record.plist"
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.salmonstar.koca-record</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$DIR/run_daily.sh</string></array>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>23</integer><key>Minute</key><integer>47</integer></dict>
</dict></plist>
PL
chmod +x run_daily.sh
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "完成！每天 23:47 自動更新（電腦睡著的話，醒來後會補跑）。紀錄檔：~/Library/Logs/koca-record.log"
