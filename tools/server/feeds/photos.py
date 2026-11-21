"""Shared photo albums."""
import json
import time


# --- photos: iCloud Shared Album ("Public Website" on), cached 30 minutes ---
PHOTO_CACHES = {}          # album link -> {at, key, data}
B62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def album_photos(sid=""):
    A = sources_load().get("albums") or []
    src = next((a for a in A if a.get("id") == sid), A[0] if A else None)
    link = ((src or {}).get("url") or "").strip()
    if not link:
        return {"photos": [], "error": "no album set up"}
    PHOTO_CACHE = PHOTO_CACHES.setdefault(link, {"at": 0, "key": link, "data": None})
    if PHOTO_CACHE["data"] is not None and time.time() - PHOTO_CACHE["at"] < 1800:
        return PHOTO_CACHE["data"]
    out = {"photos": [], "error": None, "album": ""}
    try:
        token = link.split("#")[-1].split(";")[0].strip("/")
        n = 0
        for ch in (token[1:2] if token[0] == "A" else token[1:3]):
            n = n * 62 + B62.index(ch)
        host = "p%02d-sharedstreams.icloud.com" % n
        base = "https://%s/%s/sharedstreams/" % (host, token)
        try:
            stream = _get_json(base + "webstream", {"streamCtag": None})
        except Exception as e:
            # Apple answers 330 with the right partition host
            hdr = getattr(e, "headers", None)
            moved = hdr.get("X-Apple-MMe-Host") if hdr else None
            if not moved and hasattr(e, "read"):
                try:
                    moved = json.loads(e.read().decode()).get("X-Apple-MMe-Host")
                except Exception:
                    moved = None
            if not moved:
                raise
            base = "https://%s/%s/sharedstreams/" % (moved, token)
            stream = _get_json(base + "webstream", {"streamCtag": None})
        out["album"] = stream.get("streamName", "")
        photos = stream.get("photos") or []
        guids = [p["photoGuid"] for p in photos if p.get("photoGuid")]
        urls = {}
        for i in range(0, len(guids), 25):
            assets = _get_json(base + "webasseturls", {"photoGuids": guids[i:i + 25]})
            for cs, it in (assets.get("items") or {}).items():
                urls[cs] = "https://" + it["url_location"] + it["url_path"]
        for p in photos:
            ders = p.get("derivatives") or {}
            # largest version that is still a sensible size for a 1920x1080 screen
            best = None
            for d in ders.values():
                w = int(d.get("width") or 0)
                if d.get("checksum") in urls and w <= 2600 and (best is None or w > int(best.get("width") or 0)):
                    best = d
            if best:
                out["photos"].append({"url": urls[best["checksum"]], "caption": p.get("caption", ""),
                                      "date": p.get("dateCreated", ""), "w": int(best.get("width") or 0),
                                      "h": int(best.get("height") or 0)})
    except Exception as e:
        out["error"] = str(e)[:200]
    PHOTO_CACHE.update(at=time.time(), key=link, data=out)
    return out


# names used only inside functions: imported last, so these modules can use each other
from server.core import _get_json  # noqa: E402
from server.sources import sources_load  # noqa: E402
