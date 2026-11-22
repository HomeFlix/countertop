"""Community: the gallery's list of layouts, themes and effects, for Library → Community.

The gallery is a separate repository (github.com/kizit/countertop-gallery) that publishes one index.json on GitHub Pages:
every item inline, and a `revoked` list of items that were taken down. This reads it only when someone opens Community
in Controls (never in the background), keeps it for ten minutes, and sends nothing about this install. Items are checked
again in the browser when they're downloaded, exactly as a shared file from a friend is.
"""
import json
import os
import re
import threading
import time
from urllib.request import Request, urlopen

from server.core import VERSION

GALLERY_URL = "https://kizit.github.io/countertop-gallery/index.json"
KEEP_FOR = 600
MAX_BYTES = 8_000_000
KINDS = {"layout": "layouts", "theme": "themes", "effect": "effects"}
ID = re.compile(r"^(layouts|themes|effects)/[a-z0-9][a-z0-9-]{0,60}$")
CACHE = {"at": 0.0, "data": None}
LOCK = threading.Lock()


def _clean(raw):
    """The index, keeping only items that look right (the browser checks each one's contents when it's downloaded)."""
    if not isinstance(raw, dict) or raw.get("countertop") != "gallery" or not isinstance(raw.get("items"), list):
        raise ValueError("that isn't a Countertop gallery")
    if not isinstance(raw.get("format"), int) or raw["format"] > 1:
        raise ValueError("this gallery needs a newer Countertop")
    items = []
    for i in raw["items"]:
        if not isinstance(i, dict) or not isinstance(i.get("item"), dict):
            continue
        iid, kind = i.get("id"), i.get("kind")
        if not isinstance(iid, str) or not ID.match(iid) or kind not in KINDS or not iid.startswith(KINDS[kind] + "/"):
            continue
        if i["item"].get("countertop") != kind or not isinstance(i.get("version"), int) or isinstance(i["version"], bool) or i["version"] < 1:
            continue
        items.append({"id": iid, "kind": kind, "name": str(i.get("name") or i["item"].get("name") or "")[:80],
                      "description": str(i.get("description") or "")[:500], "author": str(i.get("author") or "")[:39],
                      "version": i["version"], "updated": str(i.get("updated") or "")[:10], "item": i["item"]})
    revoked = [x for x in raw.get("revoked") or [] if isinstance(x, str) and ID.match(x)]
    return {"items": items, "revoked": revoked, "updated": str(raw.get("updated") or "")[:10]}


def community_index(refresh=False):
    """{items, revoked, updated, fetched, error}. On a failure the last good list is kept and the error says why."""
    with LOCK:
        now = time.time()
        if CACHE["data"] and not refresh and now - CACHE["at"] < KEEP_FOR:
            return dict(CACHE["data"], error="")
        try:
            url = os.environ.get("COUNTERTOP_GALLERY_URL") or GALLERY_URL
            req = Request(url, headers={"User-Agent": "Countertop/" + VERSION, "Accept": "application/json"})
            data = _clean(json.loads(urlopen(req, timeout=12).read(MAX_BYTES).decode("utf-8")))
            data["fetched"] = int(now)
            CACHE.update(at=now, data=data)
            return dict(data, error="")
        except Exception as e:
            if CACHE["data"]:
                return dict(CACHE["data"], error="Couldn't reach the gallery just now (%s). Showing what was loaded earlier." % str(e)[:100])
            return {"items": [], "revoked": [], "updated": "", "fetched": 0, "error": "Couldn't reach the gallery (%s). Check your internet connection and try again." % str(e)[:100]}
