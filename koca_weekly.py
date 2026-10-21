#!/usr/bin/env python3
"""俗頭的 KOCA 圖鑑週報

每天跑一次：
  1. 抓 KOCA 公開資料（俗頭的累計圖鑑數、BanG Dream! 星球的系列與收藏集）
  2. 存成 data/snapshots/YYYY-MM-DD.json
  3. 跟前幾天的快照比對，算出每天／每週新增了什麼
  4. 產生 docs/index.html（GitHub Pages 直接發布這個資料夾）

不需要任何 AI，也不需要登入。

用法：
  python koca_weekly.py              # 抓資料 + 產生網頁
  python koca_weekly.py --no-fetch   # 只用現有快照重新產生網頁
  python koca_weekly.py --fixture f.json  # 用離線資料測試（不連網）
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# ── 設定 ──────────────────────────────────────────────
NICKNAME = "俗頭"
USERNAME = "Bonnie1760"
PLANET = "bang_dream"
LNG = "zh-TW"
BASE = "https://koca.shop"
TZ = timezone(timedelta(hours=8))  # 台北時間

ROOT = Path(__file__).resolve().parent
SNAP_DIR = ROOT / "data" / "snapshots"
TEMPLATE = ROOT / "template.html"
ITEMS_STATE = ROOT / "data" / "items_state.json"   # 上次看到的所有圖鑑 id（每天覆寫）
MEMBERS = ROOT / "data" / "members.json"           # 角色名稱與 KOCA 大頭照
OUT = ROOT / "docs" / "index.html"
STAMP_WEEKS = 8  # 集章卡顯示最近幾週


# ── 抓資料 ────────────────────────────────────────────
def make_session():
    """KOCA 前面有 Cloudflare。curl_cffi 能模擬 Chrome，被擋的機率較低；沒裝就退回 requests。"""
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-TW,zh;q=0.9,ja;q=0.8,en;q=0.7",
        "Referer": f"{BASE}/{LNG}/planets/{PLANET}",
    }
    try:
        from curl_cffi import requests as cr  # type: ignore

        s = cr.Session(impersonate="chrome")
        s.headers.update(headers)
        return s
    except ImportError:
        import requests  # type: ignore

        s = requests.Session()
        headers["User-Agent"] = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/129.0 Safari/537.36"
        )
        s.headers.update(headers)
        return s


def get_json(s, path: str, **params):
    params.setdefault("lng", LNG)
    for attempt in range(3):
        r = s.get(BASE + path, params=params, timeout=30)
        ctype = r.headers.get("content-type", "")
        if r.status_code == 200 and "json" in ctype:
            return r.json()
        if r.status_code in (403, 429, 503):
            time.sleep(5 * (attempt + 1))
            continue
        break
    raise RuntimeError(
        f"{path} 回應 {r.status_code}（{ctype or '無類型'}）。"
        "如果是 403，多半是被 Cloudflare 擋下，請改在自己電腦上執行。"
    )


def paged(s, path: str, **params):
    out, cursor = [], None
    for _ in range(500):
        p = dict(params)
        if cursor:
            p["cursor"] = cursor
        data = get_json(s, path, **p)
        out.extend(data.get("records", []))
        cursor = data.get("next")
        if not cursor:
            return out
        time.sleep(0.3)
    raise RuntimeError(f"{path} 分頁超過 500 頁，停止")


def fetch_snapshot() -> dict:
    s = make_session()
    planet = get_json(s, f"/api/planets/{PLANET}")["planet"]
    me = next((c for c in planet.get("captains", []) if c.get("username") == USERNAME), None)

    profile_items = None
    try:
        html = s.get(f"{BASE}/{LNG}/users/{USERNAME}", timeout=30).text
        m = re.search(r"已新增\s*([\d,]+)\s*圖鑑", html)
        if m:
            profile_items = int(m.group(1).replace(",", ""))
    except Exception as e:  # 個人頁抓不到不影響其他資料
        print("個人頁讀取失敗：", e, file=sys.stderr)

    series = paged(s, f"/api/planets/{PLANET}/series", limit=50)
    batches = paged(s, f"/api/planets/{PLANET}/batches")
    all_items = paged(s, f"/api/planets/{PLANET}/items")
    members = [
        {
            "name": m["name"],
            "id": m["id"],
            "img": ((m.get("media") or [{}])[0].get("thumbnailUrl") or (m.get("cover") or {}).get("thumbnailUrl")),
            "url": f"{BASE}/{LNG}/planets/{m['id']}",
        }
        for m in planet.get("members", [])
    ]

    items = profile_items or (me or {}).get("totalItemCreateCount")
    if items is None:
        raise RuntimeError(f"找不到 {NICKNAME} 的圖鑑數")
    return {
        "fetched_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "user": {
            "nickname": NICKNAME,
            "username": USERNAME,
            "items": items,
            "planet_items": (me or {}).get("totalItemCreateCount"),
        },
        "series": [
            [x["id"], x["name"], x["createdAt"][:19], x.get("totalItems", 0)] for x in series
        ],
        "batches": [[x["id"], x["name"], x.get("releaseDate")] for x in batches],
        "_items": [[x["id"], x.get("artistName") or ""] for x in all_items],
        "_members": members,
    }


# ── 角色統計 ──────────────────────────────────────────
def norm_name(s: str) -> str:
    return re.sub(r"[\s\u3000]", "", s or "")


def count_new_items(snap: dict) -> None:
    """跟上次的圖鑑 id 比對，把新增的圖鑑依角色分類，寫進 snap["new_items"]。
    單一角色的圖鑑算給該角色；標了多個角色的（團體款、合照）另計，不分給個人。"""
    items = snap.pop("_items", None)
    members = snap.pop("_members", None)
    if members:
        MEMBERS.write_text(json.dumps(members, ensure_ascii=False, indent=0), encoding="utf-8")
    if items is None:
        return
    display = {norm_name(m["name"]): m["name"] for m in (members or [])}
    if ITEMS_STATE.exists():
        prev = set(json.loads(ITEMS_STATE.read_text(encoding="utf-8")))
        new = [it for it in items if it[0] not in prev]
        chars: dict[str, int] = {}
        group = other = 0
        for _id, artist in new:
            parts = [norm_name(a) for a in artist.split(",") if norm_name(a)]
            if len(parts) == 1 and parts[0] in display:
                name = display[parts[0]]
                chars[name] = chars.get(name, 0) + 1
            elif len(parts) > 1:
                group += 1
            else:
                other += 1
        snap["new_items"] = {"total": len(new), "chars": chars, "group": group, "other": other}
    ITEMS_STATE.write_text(json.dumps(sorted(it[0] for it in items)), encoding="utf-8")


# ── 快照存取 ──────────────────────────────────────────
def save_snapshot(snap: dict, day: date) -> Path:
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    p = SNAP_DIR / f"{day.isoformat()}.json"
    p.write_text(json.dumps(snap, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return p


def load_snapshots() -> list[tuple[date, dict]]:
    out = []
    for p in sorted(SNAP_DIR.glob("*.json")):
        try:
            out.append((date.fromisoformat(p.stem), json.loads(p.read_text(encoding="utf-8"))))
        except ValueError:
            continue
    return out


def merge_same_day(snap: dict, day: date) -> None:
    """同一天跑第二次時，快照會覆寫；把當天前幾次已經算到的角色新增累加進來，才不會遺失。"""
    p = SNAP_DIR / f"{day.isoformat()}.json"
    if not p.exists() or "new_items" not in snap:
        return
    old = json.loads(p.read_text(encoding="utf-8")).get("new_items")
    if not old:
        return
    ni = snap["new_items"]
    for name, n in old.get("chars", {}).items():
        ni["chars"][name] = ni["chars"].get(name, 0) + n
    for k in ("total", "group", "other"):
        ni[k] = ni.get(k, 0) + old.get(k, 0)


# ── 計算 ──────────────────────────────────────────────
def tw_date(iso_utc: str) -> date:
    return datetime.fromisoformat(iso_utc).replace(tzinfo=timezone.utc).astimezone(TZ).date()


def monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def batch_ids(snap: dict) -> set[int] | None:
    if "batches" in snap:
        return {b[0] for b in snap["batches"]}
    return None


def new_batches_between(prev: dict, cur: dict) -> list[list]:
    if "batches" not in cur:
        return []
    ids = batch_ids(prev)
    if ids is not None:
        return [b for b in cur["batches"] if b[0] not in ids]
    max_id = prev.get("max_batch_id", 10**12)  # 種子快照只記最大 id；收藏集 id 是遞增的
    return [b for b in cur["batches"] if b[0] > max_id]


def build_report(snaps: list[tuple[date, dict]], today: date) -> dict:
    latest = snaps[-1][1]
    series_all = latest.get("series", [])

    # 每天的變化（相鄰兩份快照相減，記在後面那天）
    days: dict[str, dict] = {}
    growth_by_day: dict[str, dict[int, int]] = {}
    for (d0, s0), (d1, s1) in zip(snaps, snaps[1:]):
        k = d1.isoformat()
        day = days.setdefault(k, {"items": 0, "batches": [], "series": 0})
        day["items"] += max(0, s1["user"]["items"] - s0["user"]["items"])
        day["batches"] += new_batches_between(s0, s1)
        if "series" in s0 and "series" in s1:
            before = {x[0]: x[3] for x in s0["series"]}
            g = growth_by_day.setdefault(k, {})
            for x in s1["series"]:
                if x[0] in before and x[3] > before[x[0]]:
                    g[x[0]] = g.get(x[0], 0) + x[3] - before[x[0]]

    # 每天各角色新增的圖鑑（記在該次快照的日期）
    for d, sn in snaps:
        ni = sn.get("new_items")
        if ni:
            day = days.setdefault(d.isoformat(), {"items": 0, "batches": [], "series": 0})
            day["chars"] = ni["chars"]
            day["group"] = ni["group"]

    names = {x[0]: x[1] for x in series_all}
    series_by_day: dict[str, list] = {}
    for sid, name, created, _total in series_all:
        series_by_day.setdefault(tw_date(created).isoformat(), []).append(
            {"id": sid, "name": name, "date": tw_date(created).isoformat()}
        )
    for k, lst in series_by_day.items():
        days.setdefault(k, {"items": 0, "batches": [], "series": 0})["series"] = len(lst)

    tracked_from = snaps[1][0].isoformat() if len(snaps) > 1 else None

    # 每週彙整
    weeks: dict[str, dict] = {}
    for k, d in days.items():
        w = monday(date.fromisoformat(k)).isoformat()
        wk = weeks.setdefault(
            w, {"start": w, "items": None, "batches": [], "series": [], "grown": {}, "chars": {}, "group": 0}
        )
        for name, n in d.get("chars", {}).items():
            wk["chars"][name] = wk["chars"].get(name, 0) + n
        wk["group"] += d.get("group", 0)
        if tracked_from and k >= tracked_from:
            wk["items"] = (wk["items"] or 0) + d["items"]
        wk["batches"] += [{"id": b[0], "name": b[1], "release": b[2], "date": k} for b in d["batches"]]
        wk["series"] += series_by_day.get(k, [])
        for sid, n in growth_by_day.get(k, {}).items():
            wk["grown"][sid] = wk["grown"].get(sid, 0) + n

    week_list = []
    for w in sorted(weeks, reverse=True):
        wk = weeks[w]
        wk["series"].sort(key=lambda s: s["date"], reverse=True)
        wk["batches"].sort(key=lambda b: (b["date"], b["id"]), reverse=True)
        week_series = {s["id"] for s in wk["series"]}
        wk["grown"] = sorted(
            [
                {"id": sid, "name": names.get(sid, str(sid)), "n": n}
                for sid, n in wk["grown"].items()
                if sid not in week_series
            ],
            key=lambda g: -g["n"],
        )
        wk["chars"] = sorted(wk["chars"].items(), key=lambda kv: -kv[1])
        if wk["items"] or wk["batches"] or wk["series"] or wk["grown"]:
            week_list.append(wk)
    # 本週即使空的也要有
    this_w = monday(today).isoformat()
    if not week_list or week_list[0]["start"] != this_w:
        week_list.insert(0, {"start": this_w, "items": 0 if tracked_from else None,
                             "batches": [], "series": [], "grown": [], "chars": [], "group": 0})

    stamp_start = monday(today) - timedelta(weeks=STAMP_WEEKS - 1)
    stamp_days = {
        k: {"items": v["items"] if tracked_from and k >= tracked_from else None,
            "series": v["series"], "batches": len(v["batches"]),
            "chars": sorted(v.get("chars", {}).items(), key=lambda kv: -kv[1]),
            "group": v.get("group", 0)}
        for k, v in days.items()
        if date.fromisoformat(k) >= stamp_start
    }

    return {
        "generated_at": datetime.now(TZ).isoformat(timespec="minutes"),
        "today": today.isoformat(),
        "tracked_from": tracked_from or snaps[0][0].isoformat(),
        "user": latest["user"] | {"url": f"{BASE}/{LNG}/users/{USERNAME}"},
        "planet": {
            "id": PLANET,
            "url": f"{BASE}/{LNG}/planets/{PLANET}",
            "series": len(series_all),
            "batches": len(latest.get("batches", [])) or latest.get("batch_count"),
        },
        "weeks": week_list,
        "stamp_start": stamp_start.isoformat(),
        "days": stamp_days,
        "members": {m["name"]: {"img": m["img"], "url": m["url"]}
                    for m in (json.loads(MEMBERS.read_text(encoding="utf-8")) if MEMBERS.exists() else [])},
    }


def render(report: dict) -> None:
    tpl = TEMPLATE.read_text(encoding="utf-8")
    payload = json.dumps(report, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = re.sub(
        r"(<script id=\"koca-data\" type=\"application/json\">).*?(</script>)",
        lambda m: m.group(1) + payload + m.group(2),
        tpl,
        count=1,
        flags=re.S,
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fetch", action="store_true", help="不連網，只用現有快照產生網頁")
    ap.add_argument("--fixture", help="用離線 JSON 當作今天抓到的資料（測試用）")
    ap.add_argument("--date", help="指定今天日期 YYYY-MM-DD（測試用）")
    args = ap.parse_args()

    today = date.fromisoformat(args.date) if args.date else datetime.now(TZ).date()
    if args.fixture:
        snap = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
        count_new_items(snap)
        save_snapshot(snap, today)
    elif not args.no_fetch:
        snap = fetch_snapshot()
        count_new_items(snap)
        merge_same_day(snap, today)
        p = save_snapshot(snap, today)
        print(f"已存快照 {p.name}：{NICKNAME} 累計 {snap['user']['items']} 筆，"
              f"{len(snap['series'])} 個系列，{len(snap['batches'])} 個收藏集")

    snaps = load_snapshots()
    if not snaps:
        print("沒有任何快照，請先連網執行一次", file=sys.stderr)
        return 1
    report = build_report(snaps, today)
    render(report)
    w = report["weeks"][0]
    print(f"本週（{w['start']} 起）：圖鑑 +{w['items'] if w['items'] is not None else '?'}，"
          f"收藏集 {len(w['batches'])}，系列 {len(w['series'])} → {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
