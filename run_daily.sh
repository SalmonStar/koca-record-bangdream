#!/bin/bash
# 每天由 Mac 的 launchd 執行：抓 KOCA → 產生網頁 → 推到 GitHub
cd "$(dirname "$0")" || exit 1
LOG="$HOME/Library/Logs/koca-record.log"
{
  echo "=== $(date '+%F %T') ==="
  git pull --quiet --rebase origin main
  ./.venv/bin/python koca_weekly.py || { echo "抓取失敗"; exit 1; }
  git add data docs
  git diff --cached --quiet || git commit -q -m "更新 $(date +%F)"
  git push --quiet origin main && echo "已推送"
} >> "$LOG" 2>&1
