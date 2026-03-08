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
SITE_URL = "https://kaitori.hobbyshop-yu.com"

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

    # ツイート作成（280字制限を考慮して最大5件）
    lines = []
    for a in alerts[:5]:
        arrow = "📈" if a["pct"] > 0 else "📉"
        sign = "+" if a["pct"] > 0 else ""
        diff = a["cur"] - a["prev"]
        lines.append(
            f"{arrow} {a['name']}\n"
            f"  {format_price(a['prev'])}→{format_price(a['cur'])}円"
            f"（{sign}{diff:,}円/{sign}{a['pct']:.1f}%）"
            f"by {a['shop']}"
        )

    text = "⚡ 買取価格速報\n\n" + "\n\n".join(lines) + f"\n\n👇 最新価格\n{SITE_URL}"

    # 280字超えたら件数を減らす
    while len(text) > 270 and len(lines) > 1:
        lines.pop()
        text = "⚡ 買取価格速報\n\n" + "\n\n".join(lines) + f"\n\n👇 最新価格\n{SITE_URL}"

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

            if best_pid in open_prices and open_prices[best_pid] > 0:
                prev_price = open_prices[best_pid]
                diff = cur_price - prev_price
                if diff > 0:
                    mark = f"🔺+{diff:,}"
                elif diff < 0:
                    mark = f"🔻{diff:,}"
                else:
                    mark = "→"
                cap_lines.append(f" {cap_display} {format_price(cur_price)}円({mark})")
            else:
                cap_lines.append(f" {cap_display} {format_price(cur_price)}円")

        if cap_lines:
            lines.append(f"【{group_name}】" + " ".join(cap_lines))

    lines.append(f"\n👇 色別・全店比較\n{SITE_URL}")
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
        text = f"📊 本日の買取価格まとめ（{today}）\n\n本日は大きな値動きはありませんでした。\n\n👇 最新価格\n{SITE_URL}"
        post_tweet(text, dry_run)
        return

    # 値上がり/値下がりに分けてソート
    ups = sorted([c for c in changes if c["diff"] > 0], key=lambda x: abs(x["pct"]), reverse=True)
    downs = sorted([c for c in changes if c["diff"] < 0], key=lambda x: abs(x["pct"]), reverse=True)

    lines = [f"📊 本日の買取価格まとめ（{today}）\n"]

    if ups:
        lines.append("🔺 値上がり")
        for u in ups[:3]:
            lines.append(f"・{u['name']} +{u['diff']:,}円（+{u['pct']:.1f}%）")

    if downs:
        lines.append("\n🔻 値下がり")
        for d in downs[:3]:
            lines.append(f"・{d['name']} {d['diff']:,}円（{d['pct']:.1f}%）")

    if not ups and not downs:
        lines.append("変動なし")

    lines.append(f"\n👇 最新価格\n{SITE_URL}")
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
                lines.append(f"・{u['name']} +{u['diff']:,}円（+{u['pct']:.1f}%）")
        if downs:
            lines.append("\n🔻 値下がり")
            for d in downs:
                lines.append(f"・{d['name']} {d['diff']:,}円（{d['pct']:.1f}%）")
        lines.append(f"\n👇 最新価格\n{SITE_URL}")
        text = "\n".join(lines)

    post_tweet(text, dry_run)


# ============================================================
# メイン
# ============================================================
def main():
    if len(sys.argv) < 2:
        print("Usage: tweet_bot.py [alert|noon|daily|save_open] [--dry-run]")
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
    elif cmd == "save_open":
        save_daily_open()
    else:
        print(f"Unknown command: {cmd}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
