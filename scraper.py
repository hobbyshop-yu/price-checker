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
    "oled_white":  "https://www.morimori-kaitori.jp/category/0104001/product/68109",
    "oled_neon":   "https://www.morimori-kaitori.jp/category/0104001/product/68111",
    "lite_coral":  "https://www.morimori-kaitori.jp/category/0104001/product/281",
    "ps5_disc":    "https://www.morimori-kaitori.jp/category/0101001/product/189440",
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
# ホムラ (Playwright - JSレンダリング必要)
# ============================================================
HOMURA_SWITCH_URL = "https://kaitori-homura.com/products?q%5Bproduct_sub_category_id_eq%5D=124&q%5Bproduct_sub_category_product_category_id_eq%5D=13"
HOMURA_PS_URL = "https://kaitori-homura.com/products?q%5Bproduct_sub_category_id_eq%5D=122&q%5Bproduct_sub_category_product_category_id_eq%5D=13"

# ホムラのJANコード→product_idマッピング
HOMURA_JAN_MAP = {
    # Switch 系
    "4902370553024": "switch2_domestic",   # Switch 2 国内専用
    # 有機EL
    "4902370548495": "oled_white",         # 有機EL ホワイト
    "4902370548501": "oled_neon",          # 有機EL ネオン
    # 通常Switch
    "4902370549901": "standard_neon",      # 通常 ネオン
    "4902370549895": "standard_gray",      # 通常 グレー
    # Lite
    "4902370542936": "lite_yellow",
    "4902370542943": "lite_turquoise",
    "4902370545302": "lite_coral",
    "4902370542929": "lite_gray",
    "4902370548204": "lite_blue",
    # PS5 系
    "4948872415934": "ps5_disc",           # PS5 Slim disc
    "4948872415958": "ps5_de",             # PS5 DE
    "4948872016674": "portal_white",       # Portal White
}

# キーワードマッチ（JANが見つからない場合のフォールバック）
HOMURA_KEYWORDS = {
    "switch2_domestic":   "Switch 2 日本国内専用版",
    "switch2_mariokart":  "マリオカート ワールド セット",
    "switch2_pokemon":    "Pokemon LEGENDS Z-A",
    "oled_white":         "有機ELモデル ホワイト",
    "oled_neon":          "有機EL",
    "standard_neon":      "バッテリー強化版 新型ネオン",
    "standard_gray":      "バッテリー強化版 新型グレー",
    "lite_yellow":        "Lite イエロー",
    "lite_turquoise":     "Lite ターコイズ",
    "lite_coral":         "Lite コーラル",
    "lite_gray":          "Lite グレー",
    "lite_blue":          "Lite ブルー",
    "ps5pro_7100":        "CFI-7100B01",
    "ps5pro_7000":        "CFI-7000B01",
    "ps5_disc":           "Slim CFI-2000A01",
    "ps5_de":             "CFI-2000B01",
    "ps5_jponly":         "日本語専用",
    "portal_white":       "Portal リモートプレーヤー",
    "portal_black":       "ミッドナイト ブラック",
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

            # 各商品の個別ページからJANと価格を取得
            # まずSwitchカテゴリページから商品URL一覧を取得
            all_product_urls = []

            for cat_url in [HOMURA_SWITCH_URL, HOMURA_PS_URL]:
                page.goto(cat_url, wait_until="networkidle", timeout=30000)
                time.sleep(2)

                # 商品リンクを取得
                links = page.query_selector_all("a[href*='/products/']")
                for link in links:
                    href = link.get_attribute("href") or ""
                    if "/products/" in href and "?" not in href.split("/products/")[-1]:
                        full_url = href if href.startswith("http") else f"https://kaitori-homura.com{href}"
                        if full_url not in all_product_urls:
                            all_product_urls.append(full_url)

            print(f"  {len(all_product_urls)} product pages found")

            # 各商品ページにアクセスして価格取得
            for url in all_product_urls:
                time.sleep(DELAY)
                try:
                    page.goto(url, wait_until="networkidle", timeout=20000)
                    time.sleep(1)
                    text = page.inner_text("body")

                    # 価格取得: "買取価格（税込）：XX,XXX円" パターン
                    price_m = re.search(r"買取価格[（(]税込[）)][：:]\s*([\d,]+)\s*円", text)
                    if not price_m:
                        price_m = re.search(r"買取価格[：:]\s*([\d,]+)\s*円", text)
                    if not price_m:
                        continue

                    price = int(price_m.group(1).replace(",", ""))
                    if price < 1000:
                        continue

                    # JANコードでマッチ
                    jan_m = re.search(r"JAN[コード]*[：:]\s*(\d{13})", text)
                    if jan_m:
                        jan = jan_m.group(1)
                        pid = HOMURA_JAN_MAP.get(jan)
                        if pid:
                            prices[pid] = price
                            print(f"  [OK] {pid}: {price:,} (JAN: {jan})")
                            continue

                    # JANで見つからない場合はキーワードマッチ
                    for pid, kw in HOMURA_KEYWORDS.items():
                        if pid not in prices and kw in text:
                            prices[pid] = price
                            print(f"  [OK] {pid}: {price:,} (keyword)")
                            break

                except Exception as e:
                    print(f"  [NG] {url}: {e}")

            browser.close()

    except Exception as e:
        print(f"  [ERROR] {e}")

    return prices


# ============================================================
# 海峡 / モバイル一番 (Playwright - JSレンダリング必要)
# ============================================================
KAIKYO_PS5_URL = "https://www.mobile-ichiban.com/categories/212"
KAIKYO_SWITCH_URL = "https://www.mobile-ichiban.com/categories/128"

KAIKYO_KEYWORDS = {
    "switch2_domestic":   "Switch 2 日本国内専用",
    "switch2_mariokart":  "マリオカート ワールド",
    "switch2_pokemon":    "Pokemon LEGENDS",
    "oled_neon":          "有機ELモデル ネオンブルー",
    "oled_white":         "有機ELモデル ホワイト",
    "standard_neon":      "ネオンブルー/ネオンレッド",
    "standard_gray":      "グレー HAD-S",
    "lite_yellow":        "Lite イエロー",
    "lite_turquoise":     "Lite ターコイズ",
    "lite_coral":         "Lite コーラル",
    "lite_gray":          "Lite グレー",
    "lite_blue":          "Lite ブルー",
    "ps5pro_7100":        "CFI-7100B01",
    "ps5pro_7000":        "CFI-7000B01",
    "ps5_disc":           "slim CFI-2000A01",
    "ps5_de":             "デジタル・エディション 日本語専用 CFI-2200",
    "ps5_jponly":         "日本語専用 CFI-2200B",
    "portal_white":       "Portal リモートプレーヤー",
    "portal_black":       "ミッドナイト ブラック",
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

            # トップページから商品一覧を取得
            page.goto("https://www.mobile-ichiban.com/", wait_until="networkidle", timeout=30000)
            time.sleep(3)

            # ページ全体のテキストから商品+価格を抽出
            text = page.inner_text("body")

            # テーブル行やリスト形式で「商品名 XX,XXX円」を探す
            # 海峡のフォーマット: 商品名 + 新品価格
            lines = text.split("\n")
            items = []
            for line in lines:
                line = line.strip()
                price_m = re.search(r"([\d,]+)\s*円", line)
                if price_m:
                    price = int(price_m.group(1).replace(",", ""))
                    if price > 5000:
                        items.append({"text": line, "price": price})

            print(f"  {len(items)} price items found")

            # キーワードマッチ
            for pid, kw in KAIKYO_KEYWORDS.items():
                for item in items:
                    if kw.lower() in item["text"].lower():
                        prices[pid] = item["price"]
                        print(f"  [OK] {pid}: {item['price']:,}")
                        break

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
