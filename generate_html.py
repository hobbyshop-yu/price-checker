#!/usr/bin/env python3
"""
HTMLジェネレーター
data/prices.json と data/products.json からHTMLを自動生成する。
Jinja2不要 - Python標準ライブラリのみで動作。
"""

import json
import os
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "index.html")

# カテゴリ→CSSクラス名＆表示名
CATEGORY_META = {
    "switch2":    {"row_class": "row-switch2",    "label": "Switch 2"},
    "oled":       {"row_class": "row-oled",       "label": "有機EL"},
    "standard":   {"row_class": "row-standard",   "label": "通常"},
    "lite":       {"row_class": "row-lite",       "label": "Lite"},
    "pro":        {"row_class": "row-pro",        "label": "PS5 Pro"},
    "disc":       {"row_class": "row-disc",       "label": "PS5 ディスク"},
    "digital":    {"row_class": "row-digital",    "label": "PS5 DE"},
    "jponly":     {"row_class": "row-jponly",     "label": "PS5 日本語"},
    "portal":     {"row_class": "row-portal",     "label": "Portal"},
    "iphone17pm": {"row_class": "row-iphone17pm", "label": "17 Pro Max"},
    "iphone17p":  {"row_class": "row-iphone17p",  "label": "17 Pro"},
    "iphone17":   {"row_class": "row-iphone17",   "label": "iPhone 17"},
}

SHOPS = [
    {"id": "rudeya",   "name": "ルデヤ",   "url": "https://kaitori-rudeya.com/",         "highlight": True},
    {"id": "morimori", "name": "森森",     "url": "https://www.morimori-kaitori.jp/",    "highlight": True},
    {"id": "homura",   "name": "ホムラ",   "url": "https://kaitori-homura.com/",         "highlight": False},
    {"id": "kaikyo",   "name": "海峡",     "url": "https://www.mobile-ichiban.com/",     "highlight": False},
]


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def fmt_price(price):
    """数値を3桁カンマ区切り文字列に"""
    if price is None:
        return "-"
    return f"{price:,}"


def generate_html():
    products = load_json(os.path.join(DATA_DIR, "products.json"))["products"]
    prices_data = load_json(os.path.join(DATA_DIR, "prices.json"))
    now_str = datetime.now(JST).strftime("%Y/%m/%d (%H:%M)")

    # 各店舗の価格取得時刻
    shop_times = {}
    for shop in SHOPS:
        sid = shop["id"]
        if sid in prices_data.get("shops", {}):
            shop_times[sid] = prices_data["shops"][sid].get("updated_at", "")

    # テーブル行HTML生成
    rows_html = []
    for product in products:
        pid = product["id"]
        cat = product["category"]
        meta = CATEGORY_META.get(cat, {"row_class": "", "label": cat})
        retail = product["retail_price"]

        # 各店舗の価格を取得
        shop_prices = {}
        best_price = 0
        best_shop = None
        for shop in SHOPS:
            sid = shop["id"]
            p = prices_data.get("shops", {}).get(sid, {}).get("prices", {}).get(pid)
            shop_prices[sid] = p
            if p and p > best_price:
                best_price = p
                best_shop = sid

        # 差益計算（最高値 - 定価）
        margin = best_price - retail if best_price else 0
        margin_class = "margin-plus" if margin >= 0 else "margin-minus"
        margin_str = f"+{margin:,}" if margin >= 0 else f"{margin:,}"

        # 差益率計算
        if retail > 0 and best_price:
            margin_pct = (best_price - retail) / retail * 100
            margin_pct_str = f"+{margin_pct:.1f}%" if margin_pct >= 0 else f"{margin_pct:.1f}%"
        else:
            margin_pct = 0
            margin_pct_str = "-"

        # 行HTML構築
        cells = []
        cells.append(f'          <td class="left-sticky-1">{meta["label"]}</td>')
        cells.append(f'          <td class="left-sticky-2">{product["model"]}</td>')
        cells.append(f'          <td class="left-sticky-3">{product["color"]}</td>')
        cells.append(f'          <td class="left-sticky-4">{fmt_price(retail)}</td>')
        cells.append(f'          <td class="left-sticky-5 {margin_class}">{margin_str}</td>')
        cells.append(f'          <td class="left-sticky-6 {margin_class}" data-pct="{margin_pct:.2f}">{margin_pct_str}</td>')

        for shop in SHOPS:
            sid = shop["id"]
            p = shop_prices.get(sid)
            hl = ' class="store-highlight"' if shop.get("highlight") else ""
            is_best = sid == best_shop and p
            if is_best:
                hl = f' class="store-highlight is-best"' if shop.get("highlight") else ' class="is-best"'
                cells.append(f'          <td data-shop="{sid}"{hl}><strong>{fmt_price(p)}</strong></td>')
            else:
                cells.append(f'          <td data-shop="{sid}"{hl}>{fmt_price(p)}</td>')

        row = f'        <tr class="{meta["row_class"]}" data-kind="{cat}">\n'
        row += "\n".join(cells)
        row += "\n        </tr>"
        rows_html.append(row)

    # 店舗ヘッダー生成
    shop_headers = []
    for shop in SHOPS:
        sid = shop["id"]
        hl = ' class="store-highlight"' if shop.get("highlight") else ""
        t = shop_times.get(sid, "")
        shop_headers.append(
            f'          <th data-shop="{sid}"{hl}>{shop["name"]}<br>'
            f'<span class="store-time">{t}</span><br>'
            f'<span class="store-links"><a href="{shop["url"]}" target="_blank">公式</a></span></th>'
        )

    # フィルターのkind一覧
    filter_kinds = []
    seen_cats = set()
    for p in products:
        cat = p["category"]
        if cat not in seen_cats:
            seen_cats.add(cat)
            meta = CATEGORY_META.get(cat, {"label": cat})
            label = meta["label"]
            filter_kinds.append(
                f'      <label><input type="checkbox" class="kind-cb" value="{cat}" checked> {label}</label>'
            )

    # ショップフィルター
    filter_shops = []
    for shop in SHOPS:
        filter_shops.append(
            f'      <label><input type="checkbox" class="shop-cb" value="{shop["id"]}" checked> {shop["name"]}</label>'
        )

    # HTML全体を組み立て
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=1200, initial-scale=0.3, minimum-scale=0.2, maximum-scale=3.0, user-scalable=yes">
  <title>Switch / PS5 / iPhone 買取価格比較表</title>
  <meta name="description" content="Nintendo Switch 2・PS5 Pro・iPhone 17 Pro Maxの最新買取価格を主要買取店で比較。自動更新データ。">
  <link rel="stylesheet" href="style.css">
</head>
<body>

  <nav class="site-nav">
    <div class="nav-inner">
      <a href="index.html" class="nav-logo">📊 買取価格比較表</a>
      <div class="nav-links">
        <a href="index.html" class="active">価格表</a>
        <a href="about.html">サイトについて</a>
        <a href="contact.html">お問い合わせ</a>
        <a href="privacy.html">プライバシーポリシー</a>
      </div>
    </div>
  </nav>

  <div class="page-header">
    <h1>Nintendo Switch / PS5 / iPhone 買取価格比較表</h1>
    <p class="subtitle">最終更新：{now_str}（自動取得）</p>
  </div>

  <div class="filter-bar" id="filter-bar">
    <button class="btn-reset" id="btn-reset">初期状態に戻す</button>
    <div class="filter-row">
      <span class="filter-label">◆ 機種:</span>
{chr(10).join(filter_kinds)}
    </div>
    <div class="filter-row">
      <span class="filter-label">◆ 買取屋:</span>
{chr(10).join(filter_shops)}
    </div>
  </div>

  <div class="table-container">
    <table class="price-table">
      <thead>
        <tr>
          <th class="left-sticky-1">種別</th>
          <th class="left-sticky-2">型番/ED</th>
          <th class="left-sticky-3">カラー/備考</th>
          <th class="left-sticky-4">定価</th>
          <th class="left-sticky-5 sort-header" id="sort-margin">差益<br>(利益順) ▼</th>
          <th class="left-sticky-6 sort-header" id="sort-pct">差益率<br>(%) ▼</th>
{chr(10).join(shop_headers)}
        </tr>
      </thead>
      <tbody>
{chr(10).join(rows_html)}
      </tbody>
    </table>
  </div>

  <div class="page-footer">
    ※ 価格は新品未開封品の買取価格です。中古品は別途査定となります。<br>
    ※ 価格は随時変動します。最新価格は各買取店の公式サイトをご確認ください。<br>
    ※ 各店舗の実際の買取価格と異なる場合があります。<br>
    最終更新: {now_str}
  </div>

  <script src="filter.js"></script>

  <footer class="site-footer">
    <div class="footer-inner">
      <div class="footer-links">
        <a href="index.html">価格表</a>
        <a href="about.html">サイトについて</a>
        <a href="contact.html">お問い合わせ</a>
        <a href="privacy.html">プライバシーポリシー</a>
      </div>
      <p class="copyright">&copy; 2026 買取価格比較表 - kaitori.hobbyshop-yu.com</p>
    </div>
  </footer>
</body>
</html>"""

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[OK] Generated {OUTPUT_FILE}")


if __name__ == "__main__":
    generate_html()
