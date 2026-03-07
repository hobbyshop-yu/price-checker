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
    # iPhone 17 Pro Max
    "iphone17pm_256_sv":  "iPhone 17 Pro Max 256GB シルバー",
    "iphone17pm_256_db":  "iPhone 17 Pro Max 256GB ディープブルー",
    "iphone17pm_256_co":  "iPhone 17 Pro Max 256GB コズミックオレンジ",
    "iphone17pm_512_sv":  "iPhone 17 Pro Max 512GB シルバー",
    "iphone17pm_512_db":  "iPhone 17 Pro Max 512GB ディープブルー",
    "iphone17pm_512_co":  "iPhone 17 Pro Max 512GB コズミックオレンジ",
    "iphone17pm_1tb_sv":  "iPhone 17 Pro Max 1TB シルバー",
    "iphone17pm_1tb_db":  "iPhone 17 Pro Max 1TB ディープブルー",
    "iphone17pm_1tb_co":  "iPhone 17 Pro Max 1TB コズミックオレンジ",
    # iPhone 17 Pro
    "iphone17p_256_sv":   "iPhone 17 Pro 256GB シルバー",
    "iphone17p_256_db":   "iPhone 17 Pro 256GB ディープブルー",
    "iphone17p_256_co":   "iPhone 17 Pro 256GB コズミックオレンジ",
    "iphone17p_512_sv":   "iPhone 17 Pro 512GB シルバー",
    "iphone17p_512_db":   "iPhone 17 Pro 512GB ディープブルー",
    "iphone17p_512_co":   "iPhone 17 Pro 512GB コズミックオレンジ",
    # iPhone 17
    "iphone17_256":       "iPhone 17 256GB",
    "iphone17_512":       "iPhone 17 512GB",
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

# 森森 iPhone カテゴリページ (キーワードマッチで価格取得)
MORIMORI_IPHONE_CATS = {
    "promax": "https://www.morimori-kaitori.jp/category/0301066",
    "pro":    "https://www.morimori-kaitori.jp/category/0301065",
    "17":     "https://www.morimori-kaitori.jp/category/0301063",
}

MORIMORI_IPHONE_KW = {
    "iphone17pm_256_sv":  ["ProMax", "256", "シルバー"],
    "iphone17pm_256_db":  ["ProMax", "256", "ディープブルー"],
    "iphone17pm_256_co":  ["ProMax", "256", "コズミック"],
    "iphone17pm_512_sv":  ["ProMax", "512", "シルバー"],
    "iphone17pm_512_db":  ["ProMax", "512", "ディープブルー"],
    "iphone17pm_512_co":  ["ProMax", "512", "コズミック"],
    "iphone17pm_1tb_sv":  ["ProMax", "1TB", "シルバー"],
    "iphone17pm_1tb_db":  ["ProMax", "1TB", "ディープブルー"],
    "iphone17pm_1tb_co":  ["ProMax", "1TB", "コズミック"],
    "iphone17p_256_sv":   ["Pro", "256", "シルバー"],
    "iphone17p_256_db":   ["Pro", "256", "ディープブルー"],
    "iphone17p_256_co":   ["Pro", "256", "コズミック"],
    "iphone17p_512_sv":   ["Pro", "512", "シルバー"],
    "iphone17p_512_db":   ["Pro", "512", "ディープブルー"],
    "iphone17p_512_co":   ["Pro", "512", "コズミック"],
    "iphone17_256":       ["iPhone17", "256"],
    "iphone17_512":       ["iPhone17", "512"],
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

        # iPhone カテゴリページからリンクを取得し個別ページで価格取得
        for cat_label, cat_url in MORIMORI_IPHONE_CATS.items():
            time.sleep(DELAY)
            try:
                soup_cat = fetch(cat_url)
                # a[href*=/product/]リンクから商品名とURLを取得
                for link in soup_cat.select("a[href*='/product/']"):
                    name = link.get_text(separator=" ", strip=True)
                    href = link.get("href", "")
                    if not href or not name:
                        continue
                    # キーワードマッチ
                    for pid, kws in MORIMORI_IPHONE_KW.items():
                        if pid in prices:
                            continue
                        if all(k in name for k in kws):
                            if pid.startswith("iphone17p_") and "Max" in name:
                                continue
                            if pid.startswith("iphone17_") and ("Pro" in name or "Air" in name):
                                continue
                            # 個別ページにアクセスして価格取得
                            product_url = "https://www.morimori-kaitori.jp" + href
                            time.sleep(DELAY)
                            try:
                                soup_prod = fetch(product_url)
                                pt = soup_prod.get_text()
                                pm = re.search(r"通常買取価格\s*([\d,]+)\s*円", pt)
                                if not pm:
                                    pm = re.search(r"買取価格\s*([\d,]+)\s*円", pt)
                                if pm:
                                    price = int(pm.group(1).replace(",", ""))
                                    prices[pid] = price
                                    print(f"  [OK] {pid}: {price:,} (morimori-cat)")
                            except Exception as e2:
                                print(f"  [NG] {pid}: {e2}")
                            break
            except Exception as e:
                print(f"  [NG] iPhone-{cat_label}: {e}")

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

            # iPhone カテゴリページから取得
            HOMURA_IPHONE_URL = "https://kaitori-homura.com/products?category_id=73"
            HOMURA_IPHONE_KW = {
                "iphone17pm_256_sv":  ["17 Pro Max", "256", "silver"],
                "iphone17pm_256_db":  ["17 Pro Max", "256", "blue"],
                "iphone17pm_256_co":  ["17 Pro Max", "256", "orange"],
                "iphone17pm_512_sv":  ["17 Pro Max", "512", "silver"],
                "iphone17pm_512_db":  ["17 Pro Max", "512", "blue"],
                "iphone17pm_512_co":  ["17 Pro Max", "512", "orange"],
                "iphone17pm_1tb_sv":  ["17 Pro Max", "1TB", "silver"],
                "iphone17pm_1tb_db":  ["17 Pro Max", "1TB", "blue"],
                "iphone17pm_1tb_co":  ["17 Pro Max", "1TB", "orange"],
                "iphone17p_256_sv":   ["17 Pro", "256", "silver"],
                "iphone17p_256_db":   ["17 Pro", "256", "blue"],
                "iphone17p_256_co":   ["17 Pro", "256", "orange"],
                "iphone17p_512_sv":   ["17 Pro", "512", "silver"],
                "iphone17p_512_db":   ["17 Pro", "512", "blue"],
                "iphone17p_512_co":   ["17 Pro", "512", "orange"],
                "iphone17_256":       ["iPhone 17", "256"],
                "iphone17_512":       ["iPhone 17", "512"],
            }
            try:
                page.goto(HOMURA_IPHONE_URL, wait_until="networkidle", timeout=30000)
                time.sleep(3)
                text = page.inner_text("body")
                # 行単位で商品名+価格を抽出
                lines = text.split("\n")
                iphone_items = []
                for i, line in enumerate(lines):
                    pm = re.search(r"([\d,]+)\s*円", line)
                    if pm and int(pm.group(1).replace(",", "")) > 10000:
                        ctx = " ".join(lines[max(0,i-5):i+1])
                        iphone_items.append((ctx, pm.group(1)))
                print(f"  iPhone (homura): {len(iphone_items)} items found")
                for name_part, price_str in iphone_items:
                    price = int(price_str.replace(",", ""))
                    for pid, kws in HOMURA_IPHONE_KW.items():
                        if pid in prices:
                            continue
                        if all(k.lower() in name_part.lower() for k in kws):
                            if pid.startswith("iphone17p_") and "max" in name_part.lower():
                                continue
                            if pid.startswith("iphone17_") and ("pro" in name_part.lower() or "air" in name_part.lower()):
                                continue
                            prices[pid] = price
                            print(f"  [OK] {pid}: {price:,} (homura-iphone)")
                            break
            except Exception as e:
                print(f"  [NG] iPhone (homura): {e}")

            browser.close()

    except Exception as e:
        print(f"  [ERROR] {e}")

    return prices


# ============================================================
# 海峡 / モバイル一番 (Playwright - JSレンダリング必要)
# ============================================================
KAIKYO_SWITCH_URL = "https://www.mobile-ichiban.com/Prod/2/01/01"
KAIKYO_PS5_URL = "https://www.mobile-ichiban.com/Prod/2/01/02"
# iPhone: モデル別サブカテゴリURLで精度向上
KAIKYO_IPHONE_URLS = [
    ("iPhone17PM", "https://www.mobile-ichiban.com/Prod/1/01/37"),
    ("iPhone17P",  "https://www.mobile-ichiban.com/Prod/1/01/36"),
    ("iPhone17",   "https://www.mobile-ichiban.com/Prod/1/01/34"),
]

KAIKYO_KEYWORDS = {
    "switch2_domestic":   ["Switch 2", "国内専用"],
    "switch2_mariokart":  ["マリオカート", "ワールド"],
    "switch2_pokemon":    ["Pokemon", "LEGENDS"],
    "oled_neon":          ["有機EL", "ネオン"],
    "oled_white":         ["有機EL", "ホワイト"],
    "standard_neon":      ["ネオンブルー"],
    "standard_gray":      ["グレー"],
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
    # iPhone 17 Pro Max (海峡では色情報なしのため全色同一キーワード)
    "iphone17pm_256_sv":  ["17 Pro Max", "256"],
    "iphone17pm_256_db":  ["17 Pro Max", "256"],
    "iphone17pm_256_co":  ["17 Pro Max", "256"],
    "iphone17pm_512_sv":  ["17 Pro Max", "512"],
    "iphone17pm_512_db":  ["17 Pro Max", "512"],
    "iphone17pm_512_co":  ["17 Pro Max", "512"],
    "iphone17pm_1tb_sv":  ["17 Pro Max", "1TB"],
    "iphone17pm_1tb_db":  ["17 Pro Max", "1TB"],
    "iphone17pm_1tb_co":  ["17 Pro Max", "1TB"],
    # iPhone 17 Pro
    "iphone17p_256_sv":   ["17 Pro", "256"],
    "iphone17p_256_db":   ["17 Pro", "256"],
    "iphone17p_256_co":   ["17 Pro", "256"],
    "iphone17p_512_sv":   ["17 Pro", "512"],
    "iphone17p_512_db":   ["17 Pro", "512"],
    "iphone17p_512_co":   ["17 Pro", "512"],
    # iPhone 17
    "iphone17_256":       ["iPhone 17", "256"],
    "iphone17_512":       ["iPhone 17", "512"],
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

            # Switch / PS5 カテゴリページ
            categories = [
                ("Switch", KAIKYO_SWITCH_URL),
                ("PS5", KAIKYO_PS5_URL),
            ]
            # iPhone: モデル別サブカテゴリ
            categories += KAIKYO_IPHONE_URLS
            for cat_idx, (cat_name, cat_url) in enumerate(categories):
                if cat_idx > 0:
                    time.sleep(5)  # レート制限回避
                try:
                    page.goto(cat_url, wait_until="domcontentloaded", timeout=60000)
                    time.sleep(8)  # JSレンダリング待ち（SPAのため長めに）

                    # DOM構造ベース: div.imgShowResult 内の
                    # label.hideText (商品名) + label[id^='NewPrice_'] (価格) をペアで取得
                    cards = page.query_selector_all("div.imgShowResult")
                    print(f"  {cat_name}: {len(cards)} product cards found")

                    items = []
                    color_discounts = {}  # {name_base: {"青": -5000, "橙": -8000}}
                    if len(cards) > 0:
                        for card in cards:
                            name_label = card.query_selector("label.hideText")
                            price_label = card.query_selector("label[id^='NewPrice_']")
                            if not name_label or not price_label:
                                continue
                            name = name_label.get_attribute("title") or name_label.inner_text()
                            price_text = price_label.inner_text()
                            price_m = re.search(r"([\d,]+)\s*円", price_text)
                            if price_m:
                                price = int(price_m.group(1).replace(",", ""))
                                if price > 1000:
                                    items.append({"name": name.strip(), "price": price})
                            # 色割引テキストを取得 (label.px-5)
                            discount_label = card.query_selector("label.px-5")
                            if discount_label:
                                disc_text = discount_label.inner_text().strip()
                                if disc_text:
                                    discounts = {}
                                    # "青-5000\n橙-8000" or "青、橙-5000" 形式をパース
                                    for part in re.split(r"[\n\r]+", disc_text):
                                        part = part.strip()
                                        # "青、橙-5000" パターン
                                        m_multi = re.match(r"([青橙赤白黑、・]+)-?(\d+)", part)
                                        if m_multi:
                                            colors = re.findall(r"[青橙赤白黑]", m_multi.group(1))
                                            val = int(m_multi.group(2))
                                            for c in colors:
                                                discounts[c] = -val
                                        else:
                                            # "青-5000" 単色パターン
                                            m_single = re.match(r"([青橙赤白黑])-?(\d+)", part)
                                            if m_single:
                                                discounts[m_single.group(1)] = -int(m_single.group(2))
                                    if discounts:
                                        color_discounts[name.strip()] = discounts
                    else:
                        # フォールバック: テキスト解析
                        print(f"  {cat_name}: フォールバックテキスト解析")
                        text = page.inner_text("body")
                        lines = text.split("\n")
                        current_name = ""
                        for line in lines:
                            line = line.strip()
                            if not line:
                                continue
                            price_m = re.search(r"([\d,]+)\s*円", line)
                            if price_m:
                                price = int(price_m.group(1).replace(",", ""))
                                if price > 1000 and current_name:
                                    items.append({"name": current_name, "price": price})
                                    current_name = ""
                            else:
                                if len(line) > 5 and "円" not in line:
                                    current_name = current_name + " " + line if current_name else line

                    print(f"  {cat_name}: {len(items)} name-price pairs")
                    if color_discounts:
                        print(f"  {cat_name}: {len(color_discounts)} items with color discounts")

                    # キーワードマッチ (色割引反映)
                    # 色マッピング: 青=ディープブルー(db), 橙=コズミックオレンジ(co)
                    COLOR_MAP = {"_db": "青", "_co": "橙", "_sb": "青", "_sv": None}  # sv=基準価格, sb(スカイブルー)も青
                    # カテゴリフィルタ: 各カテゴリページでは関連キーワードのみ試す
                    CAT_FILTER = {
                        "iPhone17PM": "iphone17pm_",
                        "iPhone17P":  "iphone17p_",
                        "iPhone17":   "iphone17_",
                    }
                    cat_prefix = CAT_FILTER.get(cat_name, "")
                    for pid, kws in KAIKYO_KEYWORDS.items():
                        if pid in prices:
                            continue
                        # カテゴリフィルタ: iPhoneサブカテゴリでは対応pidのみ
                        if cat_prefix and not pid.startswith(cat_prefix):
                            continue
                        for item in items:
                            if all(k in item["name"] for k in kws):
                                # Pro MaxとProの誤マッチ防止
                                if pid.startswith("iphone17p_") and "Max" in item["name"]:
                                    continue
                                if pid.startswith("iphone17_") and ("Pro" in item["name"] or "Air" in item["name"]):
                                    continue
                                # 通常Switchと有機ELの誤マッチ防止
                                if pid.startswith("standard_") and "有機EL" in item["name"]:
                                    continue
                                # Liteとあつ森セットの誤マッチ防止
                                if pid.startswith("lite_") and ("どうぶつ" in item["name"] or "あつまれ" in item["name"]):
                                    continue
                                base_price = item["price"]
                                # 色別価格調整
                                color_suffix = None
                                for suffix in ["_db", "_co", "_sv", "_lg", "_sb", "_cw", "_bk"]:
                                    if pid.endswith(suffix):
                                        color_suffix = suffix
                                        break
                                if color_suffix and color_suffix in COLOR_MAP:
                                    color_key = COLOR_MAP[color_suffix]
                                    if color_key and item["name"] in color_discounts:
                                        disc = color_discounts[item["name"]].get(color_key, 0)
                                        base_price = item["price"] + disc  # disc は負の値
                                prices[pid] = base_price
                                print(f"  [OK] {pid}: {base_price:,}")
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
