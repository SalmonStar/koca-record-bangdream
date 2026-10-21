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
| 角色排行 | 星球所有圖鑑的角色標記，跟前一天比對新增的圖鑑 id | 只算單一角色的圖鑑；多人款（團體、合照）另計。角色頭像用 KOCA 星球上的角色圖 |

每日筆數從 2026-10-22 開始累積（10/21 是第一份基準資料）。在那之前的週次只有「新系列」，因為 KOCA 有記錄系列的建立時間。

## 網址

https://salmonstar.github.io/koca-record-bangdream/

（Settings → Pages 設定為 main 分支的 /docs 資料夾）

## 每天自動更新（在自己的 Mac 上）

KOCA 會擋 GitHub 雲端主機（403），所以改在自己電腦上跑。只要設定一次：

```bash
cd ~
git clone https://github.com/SalmonStar/koca-record-bangdream.git
cd koca-record-bangdream
./setup_mac.sh
```

之後每天 23:47 會自動抓資料、更新網頁、推到 GitHub。電腦那時候在睡覺的話，醒來會補跑；
幾天沒開機也沒關係，筆數差額會算在下次執行的那一天，不會漏。

- 看執行紀錄：`cat ~/Library/Logs/koca-record.log`
- 想馬上更新一次：`./run_daily.sh`
- 停止自動更新：`launchctl unload ~/Library/LaunchAgents/com.salmonstar.koca-record.plist`

## 檔案

```
koca_weekly.py              抓資料、比對、產生網頁
template.html               網頁範本（改外觀改這個）
data/snapshots/*.json       每天一份快照
data/items_state.json       上次看到的所有圖鑑 id（用來找出新增的圖鑑）
data/members.json           角色名稱與 KOCA 頭像
docs/index.html             產生出來的網頁（GitHub Pages 發布這個）
setup_mac.sh                Mac 一鍵安裝每日排程
run_daily.sh                每天執行的內容
.github/workflows/update.yml 雲端手動執行（目前被 KOCA 擋）
```

## 想改的話

- 換人或換星球：改 `koca_weekly.py` 最上面的 `NICKNAME`、`USERNAME`、`PLANET`。
- 只想重新產生網頁、不想連網：`python koca_weekly.py --no-fetch`
