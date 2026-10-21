# 俗頭的 KOCA 集章卡

每天自動抓 KOCA 公開資料，整理成一個網頁：這週新增了幾筆圖鑑、哪些新收藏集、哪些新系列。
全部由 Python 完成，不用 AI，也不會消耗任何 token。

## 會記錄什麼

| 項目 | 來源 | 精確度 |
|---|---|---|
| 你這週新增幾筆圖鑑 | 你個人頁的「已新增 N 圖鑑」，每天相減 | 精確，就是你的帳號 |
| 新收藏集 | BanG Dream! 星球的收藏集清單，跟前一天比對 | 星球上的所有新增（KOCA 沒公開建立者） |
| 新系列 | 星球系列的建立時間 | 同上 |
| 舊系列補了圖鑑 | 每個系列的圖鑑數，跟前一天比對 | 同上 |

每日筆數從 2026-10-22 開始累積（10/21 是第一份基準資料）。在那之前的週次只有「新系列」，因為 KOCA 有記錄系列的建立時間。

## 架到網路上（GitHub Pages，免費）

1. 在 GitHub 建一個新的 repository，例如 `koca-record-bangdream`，設成 Public。
2. 把這個資料夾的所有檔案上傳上去（包含隱藏的 `.github` 資料夾）。
   用網頁上傳時 `.github` 可能被略過，可以在 GitHub 上手動新增 `.github/workflows/update.yml`，內容複製過去。
3. Settings → Pages → Build and deployment：Source 選 **Deploy from a branch**，Branch 選 `main`、資料夾選 `/docs`，按 Save。
4. Settings → Actions → General → Workflow permissions：選 **Read and write permissions**，按 Save。
5. 到 Actions 分頁，點「每日更新 KOCA 集章卡」→ **Run workflow** 先手動跑一次。
6. 幾分鐘後網址就會生效：`https://salmonstar.github.io/koca-record-bangdream/`

之後每天台北時間 23:47 會自動更新。

## 如果 GitHub Actions 被 KOCA 擋下

KOCA 前面有 Cloudflare 防護，雲端主機的連線有可能被擋（Actions 會顯示 403 錯誤）。
這時改成在自己電腦上跑，家裡的網路通常不會被擋：

```bash
pip install -r requirements.txt
python koca_weekly.py
```

跑完會更新 `docs/index.html`，再 push 到 GitHub 即可。

- **Mac**：可以用「捷徑」或 `crontab -e` 加一行 `47 23 * * * cd ~/koca-record-bangdream && python3 koca_weekly.py && git add -A && git commit -m 更新 && git push`
- **Windows**：用「工作排程器」每天執行同樣的指令。

電腦沒開的那幾天不會記錄，但下次執行時會把中間的差額算在那一天，筆數不會漏。

## 檔案

```
koca_weekly.py              抓資料、比對、產生網頁
template.html               網頁範本（改外觀改這個）
data/snapshots/*.json       每天一份快照
docs/index.html             產生出來的網頁（GitHub Pages 發布這個）
.github/workflows/update.yml 每日自動執行
```

## 想改的話

- 換人或換星球：改 `koca_weekly.py` 最上面的 `NICKNAME`、`USERNAME`、`PLANET`。
- 只想重新產生網頁、不想連網：`python koca_weekly.py --no-fetch`
