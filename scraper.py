#!/usr/bin/env python3
"""
買取価格スクレイパー v4
ルデヤ / 森森 / ホムラ / 海峡 から Switch / PS5 の最新買取価格を取得

ルデヤ・森森: requests + BeautifulSoup (HTML直接取得)
ホムラ・海峡: Playwright (JSレンダリング必要)
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta

import requests
from bs4 import BeautifulSoup

# Playwright はオプション（GitHub Actions上で利用）
try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

JST = timezone(timedelta(hours=9))
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
PRODUCTS_FILE = os.path.join(DATA_DIR, "products.json")
PRICES_FILE = os.path.join(DATA_DIR, "prices.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}
TIMEOUT = 30
DELAY = 1.5


def load_products():
    with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)["products"]


def save_prices(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(PRICES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("[OK] prices.json saved")


def fetch(url):
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding
    return BeautifulSoup(resp.text, "html.parser")


# ============================================================
# ルデヤ (requests)
# ============================================================
RUDEYA_MATCH = {
    "switch2_domestic":   "日本国内専用版 BEE-S-KB6CA",
    "switch2_mariokart":  "マリオカート ワールド セット BEE-S-KB6PA",
    "switch2_pokemon":    "Pokemon LEGENDS Z-A セット",
    "oled_neon":          "有機ELモデル ネオンブルー・ネオンレッド",
    "oled_white":         "有機ELモデル ホワイト",
    "standard_neon":      "2022年箱小型版 ネオン HADSKABAH",
    "standard_gray":      "2022年箱小型版 グレー HADSKAAAH",
    "lite_yellow":        "Switch Lite [イエロー]",
    "lite_turquoise":     "Switch Lite [ターコイズ]",
    "lite_coral":         "Switch Lite [コーラル]",
    "lite_gray":          "Switch Lite [グレー]",
    "lite_blue":          "Switch Lite [ブルー]",
    "ps5pro_7100":        "CFI-7100B01",
    "ps5pro_7000":        "CFI-7000B01",
    "ps5_disc":           "Slimモデル (CFI-2000A01)",
    "ps5_de":             "(CFI-2000B01)デジタル",
    "ps5_jponly":         "日本語専用",
    "portal_white":       "Portal リモートプレーヤー (CFIJ-18000)",
    "portal_black":       "ミッドナイト ブラック",
}


def scrape_rudeya(products):
    print("\n=== ルデヤ ===")
    prices = {}
    try:
        soup = fetch("https://kaitori-rudeya.com/")
        items = []
        for link in soup.select("a[href*='/category/detail/']"):
            text = link.get_text(separator=" ", strip=True)
            m = re.search(r"買取価格[：:]\s*([\d,]+)\s*円", text)
            if m:
                price = int(m.group(1).replace(",", ""))
                name = re.sub(r"\s*新品\s*", " ", text.split("買取価格")[0]).strip()
                items.append({"name": name, "price": price})
        print(f"  {len(items)} items found")

        for p in products:
            kw = RUDEYA_MATCH.get(p["id"], "")
            if not kw:
                continue
            for item in items:
                if kw in item["name"]:
                    prices[p["id"]] = item["price"]
                    print(f"  [OK] {p['id']}: {item['price']:,}")
                    break
            else:
                print(f"  [NG] {p['id']}")
    except Exception as e:
        print(f"  [ERROR] {e}")
    return prices


# ============================================================
# 森森 (requests)
# ============================================================
MORIMORI_URLS = {
    # Switch 2
    "switch2_domestic":  "https://www.morimori-kaitori.jp/category/0104001/product/295062",
    # 有機EL
    "oled_white":        "https://www.morimori-kaitori.jp/category/0104001/product/68109",
    "oled_neon":         "https://www.morimori-kaitori.jp/category/0104001/product/68110",
    # 通常Switch
    "standard_neon":     "https://www.morimori-kaitori.jp/category/0104001/product/154048",
    "standard_gray":     "https://www.morimori-kaitori.jp/category/0104001/product/154158",
    # Lite
    "lite_coral":        "https://www.morimori-kaitori.jp/category/0104001/product/281",
    "lite_gray":         "https://www.morimori-kaitori.jp/category/0104001/product/279",
    "lite_turquoise":    "https://www.morimori-kaitori.jp/category/0104001/product/280",
    "lite_blue":         "https://www.morimori-kaitori.jp/category/0104001/product/1588",
    "lite_yellow":       "https://www.morimori-kaitori.jp/category/0104001/product/278",
    # PS5
    "ps5pro_7000":       "https://www.morimori-kaitori.jp/category/0101001/product/278515",
    "ps5pro_7100":       "https://www.morimori-kaitori.jp/category/0101001/product/307430",
    "ps5_disc":          "https://www.morimori-kaitori.jp/category/0101001/product/189440",
    "ps5_de":            "https://www.morimori-kaitori.jp/category/0101001/product/189441",
    "ps5_jponly":        "https://www.morimori-kaitori.jp/category/0101001/product/303985",
    "portal_white":      "https://www.morimori-kaitori.jp/category/0101003/product/190534",
}


def scrape_morimori(products):
    print("\n=== 森森 ===")
    prices = {}
    try:
        soup = fetch("https://www.morimori-kaitori.jp/")
        jan_urls = {}
        for link in soup.select("a[href*='/product/']"):
            text = link.get_text(separator=" ", strip=True)
            jan_m = re.search(r"JAN[：:]?\s*(\d{13})", text)
            if jan_m:
                jan_urls[jan_m.group(1)] = "https://www.morimori-kaitori.jp" + link.get("href", "")

        for p in products:
            jan = p.get("morimori_jan", "")
            url = jan_urls.get(jan) or MORIMORI_URLS.get(p["id"])
            if not url:
                continue
            time.sleep(DELAY)
            try:
                soup2 = fetch(url)
                text = soup2.get_text()
                m = re.search(r"通常買取価格\s*([\d,]+)\s*円", text)
                if not m:
                    m = re.search(r"買取価格\s*([\d,]+)\s*円", text)
                if m:
                    prices[p["id"]] = int(m.group(1).replace(",", ""))
                    print(f"  [OK] {p['id']}: {prices[p['id']]:,}")
                else:
                    print(f"  [NG] {p['id']}: price not found")
            except Exception as e:
                print(f"  [NG] {p['id']}: {e}")
    except Exception as e:
        print(f"  [ERROR] {e}")
    return prices


# ============================================================
# ホムラ (Playwright - 個別商品ページに直接アクセス)
# ============================================================

# 確認済み個別商品ページURL (ブラウザで動作確認済み)
HOMURA_DIRECT_URLS = {
    "switch2_domestic":  "https://kaitori-homura.com/products/5148",
    "switch2_mariokart": "https://kaitori-homura.com/products/5147",
    "switch2_pokemon":   "https://kaitori-homura.com/products/5146",
    "oled_white":        "https://kaitori-homura.com/products/5144",
    "oled_neon":         "https://kaitori-homura.com/products/5143",
    "standard_neon":     "https://kaitori-homura.com/products/5138",
    "standard_gray":     "https://kaitori-homura.com/products/5137",
    "lite_turquoise":    "https://kaitori-homura.com/products/5136",
    "lite_coral":        "https://kaitori-homura.com/products/5135",
    "lite_yellow":       "https://kaitori-homura.com/products/5134",
    "lite_gray":         "https://kaitori-homura.com/products/5133",
    "lite_blue":         "https://kaitori-homura.com/products/5132",
}


def scrape_homura(products):
    print("\n=== ホムラ ===")
    if not HAS_PLAYWRIGHT:
        print("  [SKIP] Playwright not available")
        return {}

    prices = {}
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()

            # まずトップページの「強化買取商品」リストから一括取得を試みる
            page.goto("https://kaitori-homura.com/", wait_until="networkidle", timeout=30000)
            time.sleep(3)
            top_text = page.inner_text("body")

            # トップページから「商品名 買取金額（税込） XX,XXX円」パターンで抽出
            # 例: "Nintendo Switch 有機ELモデル ホワイト ... 買取金額（税込） 42,300円"
            top_items = re.findall(
                r"(Nintendo\s+Switch[^\n]*?|PlayStation[^\n]*?|PS5[^\n]*?|Portal[^\n]*?)"
                r"買取金額[（(]税込[）)]\s*([\d,]+)\s*円",
                top_text
            )
            print(f"  Top page: {len(top_items)} items from featured list")

            # トップページの結果をキーワードマッチ
            HOMURA_KW = {
                "switch2_domestic":   "Switch 2 日本国内専用",
                "switch2_mariokart":  "マリオカート ワールド",
                "switch2_pokemon":    "Pokemon LEGENDS",
                "oled_white":         "有機ELモデル ホワイト",
                "oled_neon":          "ネオンブルーネオンレッド",
                "standard_neon":      "バッテリー強化版 新型ネオン",
                "standard_gray":      "バッテリー強化版 新型グレー",
                "lite_turquoise":     "Lite ターコイズ",
                "lite_coral":         "Lite コーラル",
                "lite_yellow":        "Lite イエロー",
                "lite_gray":          "Lite グレー",
                "lite_blue":          "Lite ブルー",
                "ps5_disc":           "Slim CFI-2000",
                "ps5pro_7100":        "CFI-7100",
                "ps5pro_7000":        "CFI-7000",
                "portal_white":       "Portal",
            }
            for name_part, price_str in top_items:
                price = int(price_str.replace(",", ""))
                for pid, kw in HOMURA_KW.items():
                    if pid not in prices and kw in name_part:
                        prices[pid] = price
                        print(f"  [OK] {pid}: {price:,} (top)")
                        break

            # 足りない分は個別ページに直接アクセス
            for pid, url in HOMURA_DIRECT_URLS.items():
                if pid in prices:
                    continue
                time.sleep(DELAY)
                try:
                    page.goto(url, wait_until="networkidle", timeout=20000)
                    time.sleep(1.5)
                    text = page.inner_text("body")

                    # "買取価格（税込）：XX,XXX円"
                    m = re.search(r"買取価格[（(]税込[）)][：:]\s*([\d,]+)\s*円", text)
                    if not m:
                        m = re.search(r"([\d,]+)\s*円", text)
                    if m:
                        price = int(m.group(1).replace(",", ""))
                        if price > 1000:
                            prices[pid] = price
                            print(f"  [OK] {pid}: {price:,} (direct)")
                        else:
                            print(f"  [NG] {pid}: price too low")
                    else:
                        print(f"  [NG] {pid}: not found")
                except Exception as e:
                    print(f"  [NG] {pid}: {e}")

            browser.close()

    except Exception as e:
        print(f"  [ERROR] {e}")

    return prices


# ============================================================
# 海峡 / モバイル一番 (Playwright - JSレンダリング必要)
# ============================================================
KAIKYO_SWITCH_URL = "https://www.mobile-ichiban.com/Prod/2/01/01"
KAIKYO_PS5_URL = "https://www.mobile-ichiban.com/Prod/2/01/02"

KAIKYO_KEYWORDS = {
    "switch2_domestic":   ["Switch 2", "国内専用"],
    "switch2_mariokart":  ["マリオカート", "ワールド"],
    "switch2_pokemon":    ["Pokemon", "LEGENDS"],
    "oled_neon":          ["有機EL", "ネオン"],
    "oled_white":         ["有機EL", "ホワイト"],
    "standard_neon":      ["ネオンブルー", "ネオンレッド"],
    "standard_gray":      ["グレー", "HAD"],
    "lite_yellow":        ["Lite", "イエロー"],
    "lite_turquoise":     ["Lite", "ターコイズ"],
    "lite_coral":         ["Lite", "コーラル"],
    "lite_gray":          ["Lite", "グレー"],
    "lite_blue":          ["Lite", "ブルー"],
    "ps5pro_7100":        ["CFI-7100"],
    "ps5pro_7000":        ["CFI-7000"],
    "ps5_disc":           ["CFI-2000A"],
    "ps5_de":             ["CFI-2000B"],
    "ps5_jponly":         ["日本語専用", "CFI-2"],
    "portal_white":       ["Portal", "CFIJ-18000"],
    "portal_black":       ["ミッドナイト"],
}


def scrape_kaikyo(products):
    print("\n=== 海峡 ===")
    if not HAS_PLAYWRIGHT:
        print("  [SKIP] Playwright not available")
        return {}

    prices = {}
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()

            # Switch / PS5 カテゴリページに直接アクセス
            for cat_name, cat_url in [("Switch", KAIKYO_SWITCH_URL), ("PS5", KAIKYO_PS5_URL)]:
                try:
                    page.goto(cat_url, wait_until="networkidle", timeout=30000)
                    time.sleep(5)  # JSレンダリング待ち

                    # NewPrice_ ラベルから価格を取得
                    price_labels = page.query_selector_all("label[id^='NewPrice_']")
                    print(f"  {cat_name}: {len(price_labels)} NewPrice labels found")

                    if len(price_labels) == 0:
                        # フォールバック: テキスト全体から取得
                        text = page.inner_text("body")
                        lines = text.split("\n")
                        items = []
                        for i, line in enumerate(lines):
                            line = line.strip()
                            price_m = re.search(r"([\d,]+)\s*円", line)
                            if price_m:
                                price = int(price_m.group(1).replace(",", ""))
                                if price > 5000:
                                    context = " ".join(lines[max(0,i-3):i+1])
                                    items.append({"text": context, "price": price})
                        print(f"  {cat_name}: {len(items)} text items found (fallback)")
                        for pid, kws in KAIKYO_KEYWORDS.items():
                            if pid in prices:
                                continue
                            for item in items:
                                if all(k in item["text"] for k in kws):
                                    prices[pid] = item["price"]
                                    print(f"  [OK] {pid}: {item['price']:,} (text)")
                                    break
                    else:
                        # 各商品カードからラベルと価格をペアで取得
                        cards = page.query_selector_all(".product-card, .item, [class*='prod'], tr, .row")
                        if not cards:
                            # カードが見つからない場合、ページ全体のテキストで処理
                            text = page.inner_text("body")
                            # 商品ブロック単位で分割してマッチ
                            blocks = re.split(r"カートに入れる|カートへ", text)
                            for block in blocks:
                                price_m = re.search(r"(\d[\d,]+)\s*円", block)
                                if price_m:
                                    price = int(price_m.group(1).replace(",", ""))
                                    if price > 5000:
                                        for pid, kws in KAIKYO_KEYWORDS.items():
                                            if pid not in prices and all(k in block for k in kws):
                                                prices[pid] = price
                                                print(f"  [OK] {pid}: {price:,}")
                                                break
                except Exception as e:
                    print(f"  [NG] {cat_name}: {e}")

            browser.close()

    except Exception as e:
        print(f"  [ERROR] {e}")

    return prices


# ============================================================
# メイン
# ============================================================
def main():
    print("=" * 60)
    print(f"Price Scraper v4 - {datetime.now(JST).strftime('%Y/%m/%d %H:%M:%S')} JST")
    print(f"Playwright: {'available' if HAS_PLAYWRIGHT else 'NOT available (skipping JS sites)'}")
    print("=" * 60)

    products = load_products()
    print(f"Target: {len(products)} products")

    now_str = datetime.now(JST).strftime("%Y/%m/%d %H:%M")

    scrapers = [
        ("rudeya",   "買取ルデヤ", "ルデヤ", "https://kaitori-rudeya.com/",       scrape_rudeya),
        ("morimori", "森森買取",   "森森",   "https://www.morimori-kaitori.jp/",  scrape_morimori),
        ("homura",   "買取ホムラ", "ホムラ", "https://kaitori-homura.com/",       scrape_homura),
        ("kaikyo",   "海峡通信",   "海峡",   "https://www.mobile-ichiban.com/",   scrape_kaikyo),
    ]

    shops_data = {}
    for sid, name, short, url, func in scrapers:
        p = func(products)
        time.sleep(DELAY)
        shops_data[sid] = {
            "name": name,
            "short_name": short,
            "url": url,
            "updated_at": now_str,
            "prices": p,
        }

    prices_data = {"updated_at": now_str, "shops": shops_data}

    print(f"\n=== Summary ===")
    for sid, info in shops_data.items():
        print(f"  {info['short_name']}: {len(info['prices'])}/{len(products)}")

    save_prices(prices_data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
