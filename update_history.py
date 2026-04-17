#!/usr/bin/env python3
"""
update_history.py
- Google スプレッドシートから買取価格CSVをダウンロード
- prices.json（スクレイパーの最新データ）も統合
- data/history.json にインクリメンタルに保存
"""

import csv
import io
import json
import ssl
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

JST = timezone(timedelta(hours=9))

DATA_DIR = Path(__file__).parent / "data"
PRICES_FILE = DATA_DIR / "prices.json"
HISTORY_FILE = DATA_DIR / "history.json"

SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1TdD2dhKsiAl5oszoDLrozfXz9jWFlqONUSWwB_iA9jM/"
    "export?format=csv&gid=791044612"
)

# スプレッドシートの機種名 → 内部ID マッピング
ROW_MAP = {}
ROW_MAP[("17ProMax", "256G")] = "iphone17pm_256"
ROW_MAP[("17ProMax", "512G")] = "iphone17pm_512"
ROW_MAP[("17ProMax", "1T")] = "iphone17pm_1tb"
ROW_MAP[("17ProMax", "2T")] = "iphone17pm_2tb"
ROW_MAP[("17Pro", "256G")] = "iphone17p_256"
ROW_MAP[("17Pro", "512G")] = "iphone17p_512"
ROW_MAP[("17Pro", "1T")] = "iphone17p_1tb"
ROW_MAP[("Air", "256G")] = "iphone_air_256"
ROW_MAP[("Air", "512G")] = "iphone_air_512"
ROW_MAP[("Air", "1T")] = "iphone_air_1tb"
ROW_MAP[("17", "256G")] = "iphone17_256"
ROW_MAP[("17", "512G")] = "iphone17_512"
ROW_MAP[("17e", "256G")] = "iphone17e_256"
ROW_MAP[("17e", "512G")] = "iphone17e_512"

# 表示名
DISPLAY_NAMES = {
    "iphone17pm_256": "17PM 256GB",
    "iphone17pm_512": "17PM 512GB",
    "iphone17pm_1tb": "17PM 1TB",
    "iphone17pm_2tb": "17PM 2TB",
    "iphone17p_256": "17Pro 256GB",
    "iphone17p_512": "17Pro 512GB",
    "iphone17p_1tb": "17Pro 1TB",
    "iphone_air_256": "Air 256GB",
    "iphone_air_512": "Air 512GB",
    "iphone_air_1tb": "Air 1TB",
    "iphone17_256": "17 256GB",
    "iphone17_512": "17 512GB",
    "iphone17e_256": "17e 256GB",
    "iphone17e_512": "17e 512GB",
}


def download_csv():
    """スプレッドシートからCSVをダウンロード"""
    print("Downloading spreadsheet CSV...")
    try:
        req = urllib.request.Request(SHEET_URL, headers={"User-Agent": "Mozilla/5.0"})
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            raw = resp.read()
        # BOM付きUTF-8を処理
        text = raw.decode("utf-8-sig")
        print(f"  Downloaded {len(text)} bytes")
        return text
    except Exception as e:
        print(f"  Download failed: {e}")
        return None


def parse_csv(text):
    """CSVをパースして {product_id: {date_str: price}} を返す"""
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return {}

    header = rows[0]

    # 日付列（col 4以降）をパース
    # ヘッダー行の日付は "04/16", "04/15", ... 形式（新しい順）
    dates = []
    year = 2026
    last_month = 0
    for i in range(4, len(header)):
        cell = header[i].strip()
        if not cell or "/" not in cell:
            dates.append(None)
            continue
        parts = cell.split("/")
        try:
            mo = int(parts[0])
            dy = int(parts[1])
        except ValueError:
            dates.append(None)
            continue
        # 月が増加した = 前年（日付は新→古の降順）
        if last_month > 0 and mo > last_month:
            year -= 1
        last_month = mo
        dates.append(f"{year}-{mo:02d}-{dy:02d}")

    print(f"  Dates range: {dates[-1] if dates and dates[-1] else '?'} to {dates[0] if dates and dates[0] else '?'}")

    # データ行をパース
    products = {}  # {pid: {date: price}}
    current_model = ""

    for row in rows[2:]:  # ヘッダー2行をスキップ
        if len(row) < 5:
            continue
        # 機種名列
        if row[0].strip():
            current_model = row[0].strip()
        capacity = row[1].strip()
        if not capacity:
            continue

        # 「データ取得時刻」や空行、利益額セクション等をスキップ
        if current_model in ("データ取得時刻", "利益額", "利益率", "色減額", ""):
            continue

        pid = ROW_MAP.get((current_model, capacity))
        if pid is None:
            continue

        # 重複登録防止（最初に見つかった行を優先 = 買取価格セクション）
        if pid in products and len(products[pid]) > 0:
            continue

        price_data = {}
        for ci in range(len(dates)):
            if ci >= len(row) - 4:
                break
            if dates[ci] is None:
                continue
            cell = row[4 + ci].strip().replace(",", "").replace(" ", "")
            if not cell:
                continue
            try:
                val = int(cell)
                if val > 0:
                    price_data[dates[ci]] = val
            except ValueError:
                pass

        if price_data:
            products[pid] = price_data

    return products


def get_scraper_prices():
    """prices.json から当日の最高買取価格を取得"""
    if not PRICES_FILE.exists():
        return {}

    with open(PRICES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    shops = data.get("shops", {})
    best = {}
    for shop_info in shops.values():
        for pid, price in shop_info.get("prices", {}).items():
            if price and price > 0:
                if pid not in best or price > best[pid]:
                    best[pid] = price

    # 色違い統合（_sv, _db, _co サフィックスを除く）
    merged = {}
    for pid, price in best.items():
        if not pid.startswith("iphone"):
            continue
        base = pid
        for suffix in ("_sv", "_db", "_co"):
            if base.endswith(suffix):
                base = base[:-len(suffix)]
                break
        if base not in merged or price > merged[base]:
            merged[base] = price

    return merged


def load_history():
    """既存のhistory.jsonを読み込む"""
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"dates": [], "products": {}, "display_names": {}}


def merge_and_save(csv_products):
    """CSVデータとスクレイパーデータを統合してhistory.jsonに保存"""

    # スクレイパーの当日データを取得
    today = datetime.now(JST).strftime("%Y-%m-%d")
    scraper_prices = get_scraper_prices()

    # CSVデータにスクレイパーデータをマージ（当日分）
    for pid, price in scraper_prices.items():
        if pid not in csv_products:
            csv_products[pid] = {}
        old = csv_products[pid].get(today, 0)
        if price > old:
            csv_products[pid][today] = price

    # 全日付を収集してソート
    all_dates = set()
    for pd in csv_products.values():
        all_dates.update(pd.keys())
    all_dates = sorted(all_dates)

    # 出力形式に変換
    output = {
        "dates": all_dates,
        "products": {},
        "display_names": DISPLAY_NAMES,
    }

    for pid in sorted(csv_products.keys()):
        if pid in DISPLAY_NAMES:
            prices_list = []
            for d in all_dates:
                prices_list.append(csv_products[pid].get(d, None))
            output["products"][pid] = prices_list

    # 保存
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False)

    product_count = len(output["products"])
    date_count = len(all_dates)
    total_entries = sum(1 for pl in output["products"].values() for p in pl if p is not None)
    print(f"OK: {product_count} products x {date_count} dates ({total_entries} entries)")
    if all_dates:
        print(f"  Date range: {all_dates[0]} to {all_dates[-1]}")


def main():
    # 1. スプレッドシートからCSVダウンロード
    csv_text = download_csv()
    if csv_text is None:
        print("Falling back to local CSV...")
        csv_path = DATA_DIR / "historical_prices_raw.csv"
        if csv_path.exists():
            with open(csv_path, "rb") as f:
                csv_text = f.read().decode("utf-8-sig")
        else:
            print("No CSV data available. Exiting.")
            return

    # 2. CSVをパース
    csv_products = parse_csv(csv_text)
    print(f"CSV: {len(csv_products)} products parsed")

    # 3. マージして保存
    merge_and_save(csv_products)


if __name__ == "__main__":
    main()
