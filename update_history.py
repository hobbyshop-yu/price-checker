import csv
import io
import json
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))

RM = {}
RM[("17ProMax", "256G")] = "iphone17pm_256"
RM[("17ProMax", "512G")] = "iphone17pm_512"
RM[("17ProMax", "1T")] = "iphone17pm_1tb"
RM[("17Pro", "256G")] = "iphone17p_256"
RM[("17Pro", "512G")] = "iphone17p_512"
RM[("17Pro", "1T")] = "iphone17p_1tb"
RM[("Air", "256G")] = "iphone_air_256"
RM[("Air", "512G")] = "iphone_air_512"
RM[("17", "256G")] = "iphone17_256"
RM[("17", "512G")] = "iphone17_512"

DN = {}
DN["iphone17pm_256"] = "17PM 256GB"
DN["iphone17pm_512"] = "17PM 512GB"
DN["iphone17pm_1tb"] = "17PM 1TB"
DN["iphone17p_256"] = "17Pro 256GB"
DN["iphone17p_512"] = "17Pro 512GB"
DN["iphone17p_1tb"] = "17Pro 1TB"
DN["iphone_air_256"] = "Air 256GB"
DN["iphone_air_512"] = "Air 512GB"
DN["iphone17_256"] = "17 256GB"
DN["iphone17_512"] = "17 512GB"

with open("data/historical_prices_raw.csv", "rb") as f:
    t = f.read().decode("utf-8-sig")

rows = list(csv.reader(io.StringIO(t)))
h = rows[0]

dl = []
yr = 2026
lm = 0
idx = 0
while idx < len(h[4:]):
    r = h[4 + idx].strip()
    if r == "" or "/" not in r:
        dl.append(None)
    else:
        p = r.split("/")
        mo = int(p[0])
        dy = int(p[1])
        if lm > 0 and mo > lm:
            yr = yr - 1
        lm = mo
        dl.append(str(yr) + "-" + str(mo).zfill(2) + "-" + str(dy).zfill(2))
    idx = idx + 1

vcount = 0
for x in dl:
    if x is not None:
        vcount = vcount + 1
print("dates: " + str(vcount))

mg = {}
cm = ""
ri = 2
while ri < len(rows):
    row = rows[ri]
    ri = ri + 1
    if len(row) < 5:
        continue
    if row[0].strip() != "":
        cm = row[0].strip()
    cap = row[1].strip()
    if cap == "":
        continue
    pid = RM.get((cm, cap), None)
    if pid is None:
        continue
    if pid in mg and len(mg[pid]) > 0:
        continue
    pd = {}
    ci = 0
    while ci < len(row[4:]):
        if ci < len(dl) and dl[ci] is not None:
            c = row[4 + ci].strip().replace(",", "").replace(" ", "")
            if c != "":
                try:
                    v = int(c)
                    if v > 0:
                        pd[dl[ci]] = v
                except Exception:
                    pass
        ci = ci + 1
    mg[pid] = pd

ct = 0
for v in mg.values():
    ct = ct + len(v)
print("csv: " + str(len(mg)) + " products, " + str(ct) + " entries")

if True:
    with open("data/prices.json", "r", encoding="utf-8") as f:
        cur = json.load(f)
    td = datetime.now(JST).strftime("%Y-%m-%d")
    shops = cur.get("shops", {})
    best = {}
    for si in shops.values():
        for pid2, pr in si.get("prices", {}).items():
            if pr is not None and pr > 0:
                if pid2 not in best or pr > best[pid2]:
                    best[pid2] = pr
    for pid2, pr in best.items():
        if not pid2.startswith("iphone"):
            continue
        n = pid2
        if n.endswith("_sv"):
            n = n[:-3]
        elif n.endswith("_db"):
            n = n[:-3]
        elif n.endswith("_co"):
            n = n[:-3]
        if n not in mg:
            mg[n] = {}
        old = mg[n].get(td, 0)
        if pr > old:
            mg[n][td] = pr

ad = set()
for dp in mg.values():
    for dd in dp:
        ad.add(dd)
ad = sorted(ad)

out = {}
out["dates"] = ad
out["products"] = {}
out["display_names"] = DN

for pid3 in sorted(mg):
    if pid3 in DN:
        pl = []
        for dd in ad:
            pl.append(mg[pid3].get(dd, None))
        out["products"][pid3] = pl

with open("data/history.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False)

print("OK: " + str(len(out["products"])) + " x " + str(len(ad)))
