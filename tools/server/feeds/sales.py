"""Sales: what you usually buy vs this week's store ads."""
import json
import re
import threading
import time
from datetime import datetime, timedelta
from server.core import WORK


# ---------- sales: what you usually buy vs this week's store ads ----------
# work/purchases/ holds store exports and the library built from them: any *.csv with the columns
# date,store,brand,item,size,price (one row per item bought; see _parse_csv) from any store, or a
# Schnucks receipts export (schnucks_receipts.json from tools/schnucks_export.js). Everything stays on this machine; only short search words (e.g. "ghost energy")
# and the ZIP code go to Flipp, the weekly-ad service most US chains publish through.
PURCH_DIR = WORK / "purchases"
LIB_FILE = PURCH_DIR / "library.json"
LISTLOG_FILE = PURCH_DIR / "list_log.json"
SALES_FILE = PURCH_DIR / "sales_cache.json"
SALES = {"at": 0, "key": "", "data": None, "busy": False}
SALES_LOCK = threading.Lock()
_STOP = set("a an and the with of in for to or zero sugar free original classic pack count ct oz lb gr g fl size party king "
            "family value bag box can cans bottle bottles each pk pkg ounce ounces x".split())


def _words(s):
    return [w for w in re.findall(r"[a-z0-9]+", (s or "").lower().replace("'", "")) if w not in _STOP and not w.isdigit() and len(w) > 1]


def _parse_schnucks(d):
    """Schnucks' in-store purchase pages, saved as page text: item, $paid, Price: q/unit, Rewards Points, n."""
    out = []
    for r in d.get("receipts", []):
        t = r.get("text") or ""
        m = re.search(r"Date:\s*\n\s*(\d+/\d+/\d{4})", t)
        L = [x.strip() for x in t.split("\n")]
        start = next((k for k, x in enumerate(L) if x.startswith("Items Purchased")), None)
        if not m or start is None:
            continue
        day = datetime.strptime(m.group(1), "%m/%d/%Y").date().isoformat()
        for k in range(start + 1, len(L) - 2):
            if re.fullmatch(r"-?\$\d+\.\d\d", L[k + 1]) and L[k + 2].startswith("Price:"):
                paid = float(L[k + 1].replace("$", ""))
                pm = re.match(r"Price:\s*([\d.]+)\s*/\s*([\d.]+)", L[k + 2])
                q, unit = (float(pm.group(1)), float(pm.group(2))) if pm else (1.0, paid)
                sm = re.match(r"(?:(.+?) - )?(.+?)(?: \(([^)]*)\))?$", L[k])
                out.append({"store": "Schnucks", "day": day, "brand": sm.group(1) or "", "name": sm.group(2), "size": sm.group(3) or "",
                            "paid": paid, "reg": unit, "sale": q >= 1 and paid < round(q * unit, 2) - 0.01})
    return out


def _parse_csv(path):
    """Generic purchase history, one row per item bought. Columns (header row, any order, case ignored):
    date (YYYY-MM-DD or M/D/YYYY), store, brand (optional), item, size (optional), price (what you paid),
    regular (optional: the usual price, to spot sales). Other columns are ignored."""
    import csv
    out = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            r = {(k or "").strip().lower(): (v or "").strip() for k, v in r.items()}
            name, raw = r.get("item") or r.get("name") or "", r.get("date") or ""
            if not name or not raw:
                continue
            day = None
            for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
                try:
                    day = datetime.strptime(raw[:10], fmt).date().isoformat()
                    break
                except ValueError:
                    pass
            if not day:
                continue
            money = lambda v: float(re.sub(r"[^\d.]", "", v) or 0)
            paid = money(r.get("price") or r.get("paid") or "")
            reg = money(r.get("regular") or "") or paid
            out.append({"store": r.get("store") or "", "day": day, "brand": r.get("brand") or "", "name": name,
                        "size": r.get("size") or "", "paid": paid, "reg": reg, "sale": paid < reg - 0.01})
    return out


def purchases_library():
    """Rebuild library.json when an export is newer; returns {items:[...]}"""
    try:
        exports = sorted(PURCH_DIR.glob("*_receipts.json")) + sorted(PURCH_DIR.glob("*.csv"))
    except Exception:
        exports = []
    newest = max([f.stat().st_mtime for f in exports] or [0])
    if LIB_FILE.exists() and LIB_FILE.stat().st_mtime >= newest:
        try:
            return json.loads(LIB_FILE.read_text())
        except Exception:
            pass
    lines = []
    for f in exports:
        try:
            if f.suffix.lower() == ".csv":
                lines += _parse_csv(f)
                continue
            d = json.loads(f.read_text())
            if "schnucks" in f.name.lower() or "schnucks" in str(d.get("store", "")).lower():
                lines += _parse_schnucks(d)
        except Exception:
            continue
    agg = {}
    for x in lines:
        key = (x["brand"] + " - " + x["name"]).lower().strip(" -")
        e = agg.setdefault(key, {"key": key, "brand": x["brand"], "name": x["name"], "size": x["size"], "stores": set(),
                                 "days": set(), "count": 0, "paid": [], "reg": 0, "saleHits": 0})
        e["stores"].add(x["store"]); e["days"].add(x["day"]); e["count"] += 1; e["paid"].append(x["paid"])
        e["reg"] = max(e["reg"], x["reg"]); e["saleHits"] += x["sale"]
    items = []
    for e in agg.values():
        days = sorted(e.pop("days"))
        items.append(dict(e, stores=sorted(e["stores"]), trips=len(days), first=days[0], last=days[-1],
                          avg=round(sum(e["paid"]) / len(e["paid"]), 2), paid=None))
    for i in items:
        i.pop("paid")
    items.sort(key=lambda i: (-i["trips"], -i["count"]))
    lib = {"built": datetime.now().isoformat(timespec="seconds"), "lines": len(lines), "items": items}
    if exports:
        PURCH_DIR.mkdir(parents=True, exist_ok=True)
        LIB_FILE.write_text(json.dumps(lib, indent=1))
    return lib


def purchases_log_list(items):
    """Count each grocery-list entry once (by its id) so things you add often count as usual items too."""
    try:
        log = json.loads(LISTLOG_FILE.read_text()) if LISTLOG_FILE.exists() else {}
    except Exception:
        log = {}
    seen, words, today, changed = set(log.get("seen", [])), log.get("words", {}), datetime.now().date().isoformat(), False
    for i in items:
        if i.get("id") in seen or not i.get("text"):
            continue
        seen.add(i["id"]); changed = True
        k = " ".join(_words(i["text"]))
        if k:
            w = words.setdefault(k, {"text": i["text"], "count": 0, "first": today})
            w["count"] += 1; w["last"] = today; w["text"] = i["text"]
    if changed:
        PURCH_DIR.mkdir(parents=True, exist_ok=True)
        LISTLOG_FILE.write_text(json.dumps({"seen": sorted(seen)[-3000:], "words": words}, indent=1))


def _wanted(s, list_items):
    """Things worth watching: on the list now, bought often (recently weighted), added to the list often, or named in settings."""
    lib, want = purchases_library(), []
    cut = (datetime.now() - timedelta(days=max(30, s.get("recentDays") or 180))).date().isoformat()
    for i in lib.get("items", []):
        if i["trips"] >= 2 and (i["last"] >= cut or i["trips"] >= 4):
            score = i["trips"] + (3 if i["last"] >= cut else 0)
            want.append({"label": i["name"], "brand": i["brand"], "avg": i["avg"], "reg": i["reg"], "trips": i["trips"], "score": score, "why": "usual"})
    want.sort(key=lambda w: -w["score"])
    want = want[:max(5, s.get("watch") or 40)]
    try:
        log = json.loads(LISTLOG_FILE.read_text()).get("words", {}) if LISTLOG_FILE.exists() else {}
    except Exception:
        log = {}
    for w in log.values():
        if w["count"] >= 2:
            want.append({"label": w["text"], "brand": "", "score": w["count"], "why": "list"})
    for t in s.get("always") or []:
        if t.strip():
            want.append({"label": t.strip(), "brand": "", "score": 99, "why": "always"})
    for i in list_items:
        want.append({"label": i, "brand": "", "score": 100, "why": "onlist"})
    return want


def _query(w, stores):
    """Search by brand when there is one (one search covers all its flavors); else by the first product words."""
    store_words = {x for st in stores for x in _words(st)}
    b = [x for x in _words(w["brand"]) if x not in store_words][:2]   # a store's own brand rarely shows in other ads
    n = [x for x in _words(w["label"]) if x not in b]
    return (" ".join(b) if b else " ".join(n[:3])), b, n


def _flipp(q, zip_code):
    url = ("https://backflipp.wishabi.com/flipp/items/search?locale=en-us&postal_code=" + re.sub(r"\D", "", zip_code)[:5] +
           "&q=" + re.sub(r"\s+", "+", q))
    return _get_json(url, timeout=15)


def _price(it):
    p, pre, post = it.get("current_price"), (it.get("pre_price_text") or "").strip(), (it.get("post_price_text") or "").strip()
    if p in (None, "", 0):
        return (it.get("sale_story") or "").strip()
    try:
        p = "$%.2f" % float(p)
    except Exception:
        p = str(p)
    return (pre + (" " if pre and not pre.endswith("/") else "") + p + ((" " + post) if post else "")).strip()


def sales_refresh(s, list_items):
    stores = [x.strip() for x in (s.get("stores") or []) if x.strip()]
    store_keys = [" ".join(_words(x)) for x in stores]
    want, seen_q, deals, errs, checked = _wanted(s, list_items), {}, [], [], 0
    for w in want:
        q, bw, nw = _query(w, stores)
        if not q:
            continue
        if q not in seen_q:
            try:
                seen_q[q] = _flipp(q, s.get("zip") or "")
                checked += 1
            except Exception as e:
                seen_q[q] = {}
                errs.append(str(e)[:120])
            time.sleep(0.4)
        best = None
        for it in (seen_q[q].get("items") or []):
            merch = " ".join(_words(it.get("merchant_name") or it.get("merchant") or ""))
            if store_keys and not any(k and (k in merch or merch in k) for k in store_keys):
                continue
            name = set(_words(it.get("name")))
            if bw and not all(x in name for x in bw):
                continue
            hit = len(name & set(nw))
            if not bw and hit < min(2, len(nw)):
                continue
            score = hit + (2 if bw else 0)
            if not best or score > best[0]:
                best = (score, it)
        if best:
            it = best[1]
            try:
                now_p = float(it.get("current_price")) if it.get("current_price") not in (None, "") else None
                m = re.match(r"\s*(\d+)\s*/", it.get("pre_price_text") or "")
                if now_p and m and int(m.group(1)) > 1:
                    now_p = round(now_p / int(m.group(1)), 2)          # "2/$5" is $2.50 each
            except Exception:
                now_p = None
            deals.append({"want": w["label"], "brand": w.get("brand", ""), "why": w["why"], "score": w["score"],
                          "name": it.get("name"), "store": it.get("merchant_name") or it.get("merchant") or "",
                          "price": _price(it), "now": now_p, "was": it.get("original_price"), "story": it.get("sale_story") or "",
                          "usual": w.get("avg"), "until": it.get("valid_to") or "", "img": it.get("clean_image_url") or it.get("clipping_image_url") or ""})
    seen, out = set(), []
    for d in sorted(deals, key=lambda d: (d["now"] is None, -d["score"])):
        k = (d["name"], d["store"])
        if k in seen:
            continue
        seen.add(k)
        # skip "deals" that cost more than you usually pay
        if d["usual"] and d["now"] and d["now"] > d["usual"] * 1.05 and d["why"] == "usual":
            continue
        if d["story"].strip().lower() in ("sale", "on sale", d["price"].strip().lower()):
            d["story"] = ""                                  # Target writes just "SALE": not worth repeating
        out.append(d)
    return {"deals": out[:30], "checked": checked, "watching": len(want), "at": int(time.time()),
            "error": (errs[0] if errs and not out and len(errs) >= checked else None), "library": bool(LIB_FILE.exists())}


def sales_view():
    s = config_load()["modules"].get("deals", {}).get("settings", {})
    try:
        nv = notes_view()
        list_items = [i["text"] for i in nv.get("items", []) if not i.get("done")]
    except Exception:
        list_items = []
    key = json.dumps([s.get("zip"), s.get("stores"), s.get("always"), s.get("watch"), sorted(list_items)])
    if SALES["data"] is None and SALES_FILE.exists():
        try:
            c = json.loads(SALES_FILE.read_text())
            SALES.update(at=c["at"], key=c["key"], data=c["data"])
        except Exception:
            pass
    age = time.time() - SALES["at"]
    stale = age > 6 * 3600 or (SALES["key"] != key and age > 300)
    if stale and not SALES["busy"]:
        SALES["busy"] = True

        def run():
            try:
                data = sales_refresh(s, list_items)
                SALES.update(at=time.time(), key=key, data=data)
                PURCH_DIR.mkdir(parents=True, exist_ok=True)
                SALES_FILE.write_text(json.dumps({"at": SALES["at"], "key": key, "data": data}))
            except Exception as e:
                SALES.update(at=time.time() - 6 * 3600 + 900, data={"deals": [], "error": str(e)[:200]})
            finally:
                SALES["busy"] = False
        threading.Thread(target=run, daemon=True).start()
    return dict(SALES["data"] or {"deals": [], "loading": True}, busy=SALES["busy"])


# names used only inside functions: imported last, so these modules can use each other
from server.config import config_load  # noqa: E402
from server.core import _get_json  # noqa: E402
from server.lists import notes_view  # noqa: E402
