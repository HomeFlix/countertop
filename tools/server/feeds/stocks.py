"""Stocks: Yahoo's chart API with Stooq as a fallback."""
import json
import re
import time
from urllib.parse import quote
from urllib.request import Request, urlopen


# ---------- stocks: Yahoo's chart API (no key), Stooq as a fallback; cached 5 minutes ----------
STOCK_CACHE = {}


def _stock_one(sym):
    sym = re.sub(r"[^A-Za-z0-9.^=\-]", "", sym)[:15].upper()
    if not sym:
        return None
    c = STOCK_CACHE.get(sym)
    if c and time.time() - c["at"] < 300:
        return c["data"]
    d = {"sym": sym, "error": None}
    try:
        req = Request("https://query1.finance.yahoo.com/v8/finance/chart/%s?range=1d&interval=5m" % quote(sym),
                      headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15", "Accept": "application/json"})
        with urlopen(req, timeout=10) as r:
            j = json.loads(r.read(2_000_000).decode("utf-8", "replace"))
        res = j["chart"]["result"][0]
        m = res["meta"]
        closes = [x for x in ((res.get("indicators") or {}).get("quote") or [{}])[0].get("close") or [] if x is not None]
        d.update(name=m.get("shortName") or m.get("longName") or sym, price=m.get("regularMarketPrice"),
                 prev=m.get("chartPreviousClose") or m.get("previousClose"), cur=m.get("currency") or "USD",
                 spark=[round(x, 4) for x in closes[::max(1, len(closes) // 60)]], at=m.get("regularMarketTime"))
    except Exception as e:
        d["error"] = "yahoo: " + str(e)[:120]
        try:
            q = sym.lower() if "." in sym or sym.startswith("^") else sym.lower() + ".us"
            req = Request("https://stooq.com/q/l/?s=%s&f=sd2t2ohlcv&h&e=csv" % quote(q), headers={"User-Agent": "Mozilla/5.0 kitchen-dashboard"})
            with urlopen(req, timeout=10) as r:
                rows = r.read(20000).decode("utf-8", "replace").strip().splitlines()
            v = dict(zip(rows[0].split(","), rows[1].split(",")))
            if v.get("Close") not in (None, "", "N/D"):
                d.update(name=sym, price=float(v["Close"]), prev=float(v["Open"]), cur="USD", spark=[], error=None, approx=True)
        except Exception as e2:
            d["error"] += "; stooq: " + str(e2)[:80]
    STOCK_CACHE[sym] = {"at": time.time(), "data": d}
    return d


def stocks(syms):
    L = [x for x in (_stock_one(s) for s in syms.split(",")[:12]) if x]
    return {"stocks": L}
