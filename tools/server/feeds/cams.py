"""Live cams (YouTube live streams)."""
import re
import time
from urllib.request import Request, urlopen


# --- live cams: resolve YouTube links / @channels to streams that are live right now (cached 20 min) ---
CAM_CACHE = {"at": 0, "key": "", "data": None}


def _yt_page(url):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
                                "Accept-Language": "en-US,en;q=0.9", "Cookie": "CONSENT=YES+1"})
    with urlopen(req, timeout=15) as r:
        return r.read(3_000_000).decode("utf-8", "replace")


def _yt_resolve(item):
    item = item.strip()
    m = re.search(r"(?:v=|youtu\.be/|/live/|/embed/)([\w-]{11})", item) or re.fullmatch(r"([\w-]{11})", item)
    if m:
        vid, page = m.group(1), _yt_page("https://www.youtube.com/watch?v=" + m.group(1))
    else:
        h = item if item.startswith("http") else "https://www.youtube.com/" + (item if item.startswith("@") else "@" + item)
        page = _yt_page(h.rstrip("/") + "/live")
        c = re.search(r'<link rel="canonical" href="https://www\.youtube\.com/watch\?v=([\w-]{11})"', page)
        if not c:
            raise RuntimeError("not live right now")
        vid = c.group(1)
    if '"isLiveNow":true' not in page and '"isLive":true' not in page:
        raise RuntimeError("not live right now")
    if '"playableInEmbed":false' in page:
        raise RuntimeError("owner doesn't allow embedding")
    t = re.search(r'<meta name="title" content="([^"]*)"', page) or re.search(r"<title>(.*?)</title>", page)
    title = (t.group(1) if t else "").replace(" - YouTube", "")
    ch = re.search(r'"ownerChannelName":"([^"]*)"', page)
    import html as _h
    return {"id": vid, "title": _h.unescape(title)[:120], "channel": _h.unescape(ch.group(1)) if ch else ""}


def live_cams(ids=None):
    items = [c.get("url") or "" for c in sources_load().get("cams") or [] if not ids or c.get("id") in ids]
    items = [x for x in items if str(x).strip()]
    key = "|".join(items)
    if CAM_CACHE["data"] is not None and CAM_CACHE["key"] == key and time.time() - CAM_CACHE["at"] < 1200:
        return CAM_CACHE["data"]
    from concurrent.futures import ThreadPoolExecutor
    cams, errors = [], []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for item, f in [(i, pool.submit(_yt_resolve, i)) for i in items]:
            try:
                c = f.result()
                if c["id"] not in [x["id"] for x in cams]:
                    cams.append(dict(c, source=item))
            except Exception as e:
                errors.append("%s: %s" % (item, str(e)[:100]))
    out = {"cams": cams, "errors": errors}
    CAM_CACHE.update(at=time.time(), key=key, data=out)
    return out


# names used only inside functions: imported last, so these modules can use each other
from server.sources import sources_load  # noqa: E402
