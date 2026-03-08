#!/usr/bin/env python3
"""
X (Twitter) 自動ツイート Bot
- alert     : 最高買取価格が1%以上変動した商品をツイート
- noon      : 昼のiPhone速報（前日比）
- daily     : 日報ツイート（本日の値動きサマリー）
- save_open : 日次始値を保存（毎日0:00 JSTに実行）
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

JST = timezone(timedelta(hours=9))

DATA_DIR = Path(__file__).parent / "data"
PRICES_FILE = DATA_DIR / "prices.json"
PREV_FILE = DATA_DIR / "prices_prev.json"
DAILY_OPEN_FILE = DATA_DIR / "prices_daily_open.json"
NOON_POSTED_FILE = DATA_DIR / "noon_posted.json"
PRODUCTS_FILE = DATA_DIR / "products.json"
SITE_URL = "https://kaitori.hobbyshop-yu.com"
HISTORY_URL = "https://kaitori.hobbyshop-yu.com/history.html"

# ハッシュタグ（ツイート末尾に追加）
HASHTAGS_IPHONE = "#iPhone転売 #iPhone17ProMax #買取価格 #せどり"
HASHTAGS_SWITCH = "#Switch2 #NintendoSwitch #買取価格 #せどり"
HASHTAGS_GENERAL = "#買取価格 #せどり #転売"

# 商品表示名マッピング
DISPLAY_NAMES = {
    "switch2_domestic": "Switch 2 国内専用",
    "oled_neon": "有機EL ネオン",
    "oled_white": "有機EL ホワイト",
    "standard_neon": "Switch ネオン",
    "standard_gray": "Switch グレー",
    "lite_turquoise": "Lite ターコイズ",
    "lite_coral": "Lite コーラル",
    "lite_yellow": "Lite イエロー",
    "lite_gray": "Lite グレー",
    "lite_blue": "Lite ブルー",
    "ps5pro_7100": "PS5 Pro 7100",
    "ps5pro_7000": "PS5 Pro 7000",
    "ps5_disc": "PS5 ディスク",
    "ps5_de": "PS5 DE",
    "ps5_jponly": "PS5 日本語版",
    "portal_white": "Portal ホワイト",
    "portal_black": "Portal ブラック",
    "iphone17pm_256_sv": "17PM 256 シルバー",
    "iphone17pm_256_db": "17PM 256 ブルー",
    "iphone17pm_256_co": "17PM 256 オレンジ",
    "iphone17pm_512_sv": "17PM 512 シルバー",
    "iphone17pm_512_db": "17PM 512 ブルー",
    "iphone17pm_512_co": "17PM 512 オレンジ",
    "iphone17pm_1tb_sv": "17PM 1TB シルバー",
    "iphone17pm_1tb_db": "17PM 1TB ブルー",
    "iphone17pm_1tb_co": "17PM 1TB オレンジ",
    "iphone17p_256_sv": "17Pro 256 シルバー",
    "iphone17p_256_db": "17Pro 256 ブルー",
    "iphone17p_256_co": "17Pro 256 オレンジ",
    "iphone17p_512_sv": "17Pro 512 シルバー",
    "iphone17p_512_db": "17Pro 512 ブルー",
    "iphone17p_512_co": "17Pro 512 オレンジ",
    "iphone17_256": "iPhone17 256",
    "iphone17_512": "iPhone17 512",
}

SHOP_NAMES = {
    "rudeya": "ルデヤ",
    "morimori": "森森",
    "homura": "ホムラ",
    "kaikyo": "海峡",
}


def load_json(path):
    """JSONファイルを読み込む。存在しなければ空dictを返す。"""
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_json(path, data):
    """JSONファイルに保存。"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_best_prices(prices_data):
    """各商品IDの最高買取価格と店舗名を返す。"""
    shops = prices_data.get("shops", {})
    best = {}
    for shop_id, shop_info in shops.items():
        for pid, price in shop_info.get("prices", {}).items():
            if price and (pid not in best or price > best[pid]["price"]):
                best[pid] = {"price": price, "shop": shop_id}
    return best


def format_price(n):
    """価格をカンマ区切り文字列に。"""
    return f"{n:,}"


def get_retail_prices():
    """products.jsonから商品IDと定価のマッピングを返す。"""
    data = load_json(PRODUCTS_FILE)
    retail = {}
    for p in data.get("products", []):
        pid = p.get("id", "")
        rp = p.get("retail_price", 0)
        if pid and rp:
            retail[pid] = rp
    return retail


def get_hashtags(pids):
    """商品IDリストに基づいて適切なハッシュタグを返す。"""
    has_iphone = any(p.startswith("iphone") for p in pids)
    has_switch = any(p.startswith("switch") or p.startswith("oled") or p.startswith("standard") or p.startswith("lite") for p in pids)
    if has_iphone:
        return HASHTAGS_IPHONE
    elif has_switch:
        return HASHTAGS_SWITCH
    return HASHTAGS_GENERAL


def post_tweet(text, dry_run=False):
    """ツイートを投稿する。dry_run=Trueならログ出力のみ。"""
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Tweet ({len(text)}字):")
    print(text)
    print("-" * 40)

    if dry_run:
        return True

    try:
        import tweepy
        client = tweepy.Client(
            consumer_key=os.environ["X_API_KEY"],
            consumer_secret=os.environ["X_API_SECRET"],
            access_token=os.environ["X_ACCESS_TOKEN"],
            access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
        )
        client.create_tweet(text=text)
        print("  → ツイート投稿成功 ✅")
        return True
    except Exception as e:
        print(f"  → ツイート投稿失敗 ❌: {e}")
        return False


# ============================================================
# 価格変動アラート
# ============================================================
def check_price_alerts(dry_run=False):
    """最高買取価格が1%以上変動した商品をツイート。"""
    print("=== 価格変動アラート ===")

    current = load_json(PRICES_FILE)
    prev = load_json(PREV_FILE)

    if not current.get("shops"):
        print("  現在の価格データなし。スキップ。")
        return

    cur_best = get_best_prices(current)

    if not prev:
        print("  前回データなし。初回保存のみ。")
        save_json(PREV_FILE, current)
        return

    prev_best = get_best_prices(prev)

    alerts = []
    for pid, cur_info in cur_best.items():
        if pid not in prev_best:
            continue
        cur_price = cur_info["price"]
        prev_price = prev_best[pid]["price"]
        if prev_price == 0:
            continue
        change_pct = (cur_price - prev_price) / prev_price * 100
        if abs(change_pct) >= 1.0:
            alerts.append({
                "pid": pid,
                "name": DISPLAY_NAMES.get(pid, pid),
                "prev": prev_price,
                "cur": cur_price,
                "pct": change_pct,
                "shop": SHOP_NAMES.get(cur_info["shop"], cur_info["shop"]),
            })

    if not alerts:
        print("  1%以上の変動なし。")
        save_json(PREV_FILE, current)
        return

    # 変動率が大きい順にソート
    alerts.sort(key=lambda x: abs(x["pct"]), reverse=True)

    # 定価データを取得して利益計算
    retail_prices = get_retail_prices()

    # ツイート作成（280字制限を考慮して最大5件）
    lines = []
    for a in alerts[:5]:
        arrow = "📈" if a["pct"] > 0 else "📉"
        sign = "+" if a["pct"] > 0 else ""
        diff = a["cur"] - a["prev"]
        # 利益表示（定価との差額）
        profit_str = ""
        if a["pid"] in retail_prices:
            profit = a["cur"] - retail_prices[a["pid"]]
            if profit > 0:
                profit_str = f"💰利益+{profit:,}円"
            elif profit < 0:
                profit_str = f"⚠️定価割れ{profit:,}円"
        lines.append(
            f"{arrow} {a['name']}\n"
            f"  {format_price(a['cur'])}円（{sign}{diff:,}円）"
            f"{' ' + profit_str if profit_str else ''}"
        )

    all_pids = [a["pid"] for a in alerts]
    tags = get_hashtags(all_pids)
    text = "⚡ 買取価格速報\n\n" + "\n\n".join(lines) + f"\n\n👇 最新価格\n{SITE_URL}\n{tags}"

    # 280字超えたら件数を減らす
    while len(text) > 270 and len(lines) > 1:
        lines.pop()
        text = "⚡ 買取価格速報\n\n" + "\n\n".join(lines) + f"\n\n👇 最新価格\n{SITE_URL}\n{tags}"

    post_tweet(text, dry_run)
    save_json(PREV_FILE, current)
    print(f"  {len(alerts)}件の変動を検出。")


# ============================================================
# 日次始値保存
# ============================================================
def save_daily_open():
    """現在の最高価格を日次始値として保存。毎日0:00 JSTに実行。"""
    print("=== 日次始値保存 ===")
    current = load_json(PRICES_FILE)
    if not current.get("shops"):
        print("  価格データなし。スキップ。")
        return
    best = get_best_prices(current)
    today = datetime.now(JST).strftime("%Y-%m-%d")
    data = {"date": today, "prices": {pid: info["price"] for pid, info in best.items()}}
    save_json(DAILY_OPEN_FILE, data)
    print(f"  {today} の始値を {len(best)} 件保存。")


# ============================================================
# 昼 iPhone速報（前日比）
# ============================================================
def post_noon_iphone(dry_run=False):
    """iPhone価格の前日比速報。変動検知時に1日1回だけツイート。"""
    print("=== iPhone 速報チェック ===")

    # 当日既に投稿済みかチェック
    try:
        today = datetime.now(JST).strftime("%-m/%-d")
    except ValueError:
        today = datetime.now(JST).strftime("%m/%d").lstrip("0").replace("/0", "/")
    today_key = datetime.now(JST).strftime("%Y-%m-%d")

    noon_posted = load_json(NOON_POSTED_FILE)
    if noon_posted.get("date") == today_key:
        print("  本日は投稿済み。スキップ。")
        return

    current = load_json(PRICES_FILE)
    daily_open = load_json(DAILY_OPEN_FILE)

    if not current.get("shops") or not daily_open.get("prices"):
        print("  データ不足。スキップ。")
        return

    cur_best = get_best_prices(current)
    open_prices = daily_open["prices"]

    # iPhoneのみ抽出
    iphone_pids = [pid for pid in cur_best if pid.startswith("iphone")]

    if not iphone_pids:
        print("  iPhone価格データなし。スキップ。")
        return

    # 変動があるかチェック
    has_any_change = False
    for pid in iphone_pids:
        if pid in open_prices and open_prices[pid] > 0:
            if cur_best[pid]["price"] != open_prices[pid]:
                has_any_change = True
                break

    if not has_any_change:
        print("  iPhone価格に変動なし。スキップ。")
        return

    print("  ⚡ iPhone価格変動を検知！ツイートします。")

    retail_prices = get_retail_prices()
    lines = [f"📱 iPhone買取速報（{today}）\n"]

    # 容量別に最高値を取得
    groups = [
        ("17PM", "iphone17pm_", ["256", "512", "1tb"]),
        ("17Pro", "iphone17p_", ["256", "512"]),
        ("17", "iphone17_", ["256", "512"]),
    ]

    for group_name, prefix, capacities in groups:
        cap_lines = []
        for cap in capacities:
            cap_pids = []
            for pid in iphone_pids:
                if not pid.startswith(prefix):
                    continue
                if prefix == "iphone17p_" and pid.startswith("iphone17pm_"):
                    continue
                if prefix == "iphone17_" and pid.startswith("iphone17p"):
                    continue
                if f"_{cap}_" in pid or pid.endswith(f"_{cap}"):
                    cap_pids.append(pid)

            if not cap_pids:
                continue

            best_pid = max(cap_pids, key=lambda p: cur_best[p]["price"])
            cur_price = cur_best[best_pid]["price"]
            cap_display = cap.upper() if cap == "1tb" else cap

            # 前日比
            diff_str = ""
            if best_pid in open_prices and open_prices[best_pid] > 0:
                prev_price = open_prices[best_pid]
                diff = cur_price - prev_price
                if diff > 0:
                    diff_str = f"🔺+{diff:,}"
                elif diff < 0:
                    diff_str = f"🔻{diff:,}"
                else:
                    diff_str = "→"

            # 利益表示
            profit_str = ""
            if best_pid in retail_prices:
                profit = cur_price - retail_prices[best_pid]
                if profit > 0:
                    profit_str = f"💰+{profit:,}"
                elif profit < 0:
                    profit_str = f"⚠️{profit:,}"

            parts = [f"{cap_display} {format_price(cur_price)}円"]
            if diff_str:
                parts.append(f"({diff_str})")
            if profit_str:
                parts.append(profit_str)
            cap_lines.append(" ".join(parts))

        if cap_lines:
            lines.append(f"【{group_name}】\n" + "\n".join(f" {cl}" for cl in cap_lines))

    lines.append(f"\n👇 全店比較\n{SITE_URL}\n{HASHTAGS_IPHONE}")
    text = "\n".join(lines)

    result = post_tweet(text, dry_run)
    if result and not dry_run:
        save_json(NOON_POSTED_FILE, {"date": today_key})
        print("  投稿済みフラグを保存。")


# ============================================================
# 日報ツイート
# ============================================================
def post_daily_report(dry_run=False):
    """本日の値動きサマリーをツイート。"""
    print("=== 日報ツイート ===")

    current = load_json(PRICES_FILE)
    daily_open = load_json(DAILY_OPEN_FILE)

    if not current.get("shops") or not daily_open.get("prices"):
        print("  データ不足。スキップ。")
        return

    cur_best = get_best_prices(current)
    open_prices = daily_open["prices"]

    changes = []
    for pid, cur_info in cur_best.items():
        if pid not in open_prices:
            continue
        cur_price = cur_info["price"]
        open_price = open_prices[pid]
        if open_price == 0:
            continue
        diff = cur_price - open_price
        if diff == 0:
            continue
        pct = diff / open_price * 100
        changes.append({
            "pid": pid,
            "name": DISPLAY_NAMES.get(pid, pid),
            "open": open_price,
            "close": cur_price,
            "diff": diff,
            "pct": pct,
        })

    today = datetime.now(JST).strftime("%-m/%-d")
    # Windows対応
    try:
        today = datetime.now(JST).strftime("%-m/%-d")
    except ValueError:
        today = datetime.now(JST).strftime("%m/%d").lstrip("0").replace("/0", "/")

    if not changes:
        text = f"📊 本日の買取価格まとめ（{today}）\n\n本日は大きな値動きはありませんでした。\n\n👇 最新価格\n{SITE_URL}\n{HASHTAGS_GENERAL}"
        post_tweet(text, dry_run)
        return

    # 利益データも追加
    retail_prices = get_retail_prices()
    for c in changes:
        rp = retail_prices.get(c["pid"], 0)
        c["profit"] = c["close"] - rp if rp else None

    # 値上がり/値下がりに分けてソート
    ups = sorted([c for c in changes if c["diff"] > 0], key=lambda x: abs(x["pct"]), reverse=True)
    downs = sorted([c for c in changes if c["diff"] < 0], key=lambda x: abs(x["pct"]), reverse=True)

    lines = [f"📊 本日の買取価格まとめ（{today}）\n"]

    if ups:
        lines.append("🔺 値上がり")
        for u in ups[:3]:
            profit_mark = ""
            if u["profit"] is not None and u["profit"] > 0:
                profit_mark = f" 💰+{u['profit']:,}"
            lines.append(f"・{u['name']} +{u['diff']:,}円{profit_mark}")

    if downs:
        lines.append("\n🔻 値下がり")
        for d in downs[:3]:
            lines.append(f"・{d['name']} {d['diff']:,}円")

    if not ups and not downs:
        lines.append("変動なし")

    all_pids = [c["pid"] for c in changes]
    tags = get_hashtags(all_pids)
    lines.append(f"\n👇 最新価格\n{SITE_URL}\n{tags}")
    text = "\n".join(lines)

    # 文字数制限
    while len(text) > 270:
        if ups and len(ups) > 1:
            ups.pop()
        elif downs and len(downs) > 1:
            downs.pop()
        else:
            break
        lines = [f"📊 本日の買取価格まとめ（{today}）\n"]
        if ups:
            lines.append("🔺 値上がり")
            for u in ups:
                profit_mark = ""
                if u["profit"] is not None and u["profit"] > 0:
                    profit_mark = f" 💰+{u['profit']:,}"
                lines.append(f"・{u['name']} +{u['diff']:,}円{profit_mark}")
        if downs:
            lines.append("\n🔻 値下がり")
            for d in downs:
                lines.append(f"・{d['name']} {d['diff']:,}円")
        lines.append(f"\n👇 最新価格\n{SITE_URL}\n{tags}")
        text = "\n".join(lines)

    post_tweet(text, dry_run)


# ============================================================
# 週次利益ランキング
# ============================================================
def post_weekly_ranking(dry_run=False):
    """今週の利益ランキングTOP5をツイート。"""
    print("=== 週次利益ランキング ===")

    current = load_json(PRICES_FILE)
    if not current.get("shops"):
        print("  価格データなし。スキップ。")
        return

    cur_best = get_best_prices(current)
    retail_prices = get_retail_prices()

    # 利益ランキング作成
    rankings = []
    seen_models = set()  # 同モデル重複防止
    for pid, info in cur_best.items():
        if pid not in retail_prices:
            continue
        profit = info["price"] - retail_prices[pid]
        # モデル名で重複排除（色違いは最高利益のみ）
        base_name = DISPLAY_NAMES.get(pid, pid).split(" ")[0]  # 「17PM" etc
        cap_part = DISPLAY_NAMES.get(pid, pid).split(" ")[1] if len(DISPLAY_NAMES.get(pid, pid).split(" ")) > 1 else ""
        model_key = f"{base_name}_{cap_part}"
        if model_key in seen_models:
            # 既に同モデルがある場合、利益が高い方を採用
            existing = [r for r in rankings if r["model_key"] == model_key]
            if existing and profit > existing[0]["profit"]:
                rankings.remove(existing[0])
                seen_models.discard(model_key)
            else:
                continue
        seen_models.add(model_key)
        rankings.append({
            "pid": pid,
            "name": DISPLAY_NAMES.get(pid, pid),
            "price": info["price"],
            "retail": retail_prices[pid],
            "profit": profit,
            "pct": profit / retail_prices[pid] * 100,
            "model_key": model_key,
        })

    rankings.sort(key=lambda x: x["profit"], reverse=True)

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    lines = ["🏆 今週の転売利益ランキング\n"]

    for i, r in enumerate(rankings[:5]):
        if r["profit"] > 0:
            lines.append(f"{medals[i]} {r['name']} +{r['profit']:,}円（{r['pct']:.1f}%）")
        else:
            lines.append(f"{medals[i]} {r['name']} {r['profit']:,}円")

    # 定価割れワースト
    worst = sorted(rankings, key=lambda x: x["profit"])[:2]
    if worst and worst[0]["profit"] < 0:
        lines.append("\n⚠️ 仕入れ注意")
        for w in worst:
            if w["profit"] < 0:
                lines.append(f"・{w['name']} {w['profit']:,}円")

    lines.append(f"\n📈 価格推移\n{HISTORY_URL}\n{HASHTAGS_IPHONE}")
    text = "\n".join(lines)

    # 文字数制限
    while len(text) > 270 and len(rankings) > 3:
        rankings.pop()
        lines = ["🏆 今週の転売利益ランキング\n"]
        for i, r in enumerate(rankings[:5]):
            if r["profit"] > 0:
                lines.append(f"{medals[i]} {r['name']} +{r['profit']:,}円（{r['pct']:.1f}%）")
            else:
                lines.append(f"{medals[i]} {r['name']} {r['profit']:,}円")
        lines.append(f"\n📈 価格推移\n{HISTORY_URL}\n{HASHTAGS_IPHONE}")
        text = "\n".join(lines)

    post_tweet(text, dry_run)


# ============================================================
# メイン
# ============================================================
def main():
    if len(sys.argv) < 2:
        print("Usage: tweet_bot.py [alert|noon|daily|weekly|save_open] [--dry-run]")
        return 1

    cmd = sys.argv[1]
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        print("🔧 DRY RUN モード（実際のツイートは行いません）\n")

    if cmd == "alert":
        check_price_alerts(dry_run)
    elif cmd == "noon":
        post_noon_iphone(dry_run)
    elif cmd == "daily":
        post_daily_report(dry_run)
    elif cmd == "weekly":
        post_weekly_ranking(dry_run)
    elif cmd == "save_open":
        save_daily_open()
    else:
        print(f"Unknown command: {cmd}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
