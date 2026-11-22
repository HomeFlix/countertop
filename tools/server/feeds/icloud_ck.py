"""iCloud shared albums created in current Photos (photos.icloud.com/shared/album/<token>).

These are CloudKit shares, not the old "sharedstreams" albums. Public albums can be read
without an Apple ID through the same endpoints the iCloud Photos web page uses:
  records/resolve -> records/query (paged).  Stdlib only.
The flow follows drbartucz/icloud-shared-album-downloader (MIT). Apple does not
document these endpoints, so they may change.

Probe from a shell (prints what iCloud returns, useful if something looks off):
    python3 icloud_ck.py "https://photos.icloud.com/shared/album/<token>"
"""
import json
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

CK_MIN_TOKEN = 20        # legacy sharedstreams tokens are 14-15 chars, CloudKit ones ~25
CONTAINER = "com.apple.photos.cloud"
RESOLVE_URL = "https://ckdatabasews.icloud.com/database/1/%s/production/public/records/resolve" % CONTAINER
QUERY_PATH = "/database/1/%s/production/shared/records/query" % CONTAINER
ASSET_QUERY = "CPLAssetAndMasterByAssetDateWithoutHiddenOrDeleted"
VIDEO_TYPES = {"com.apple.quicktime-movie", "public.mpeg-4", "public.movie", "public.avi"}
HEADERS = {"Origin": "https://photos.icloud.com", "Referer": "https://photos.icloud.com/",
           "Content-Type": "text/plain", "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}

_TOKEN_RE = re.compile(r"(?:/shared/album/|share\.icloud\.com/photos/|icloud\.com/photos/#|"
                       r"icloud\.com/sharedalbum/#)([A-Za-z0-9_-]+)")


def album_token(link):
    """The album token from any iCloud shared-album link format, or a bare token."""
    link = (link or "").strip()
    m = _TOKEN_RE.search(link)
    return m.group(1) if m else link.split("#")[-1].split(";")[0].strip("/")


def is_cloudkit_token(token):
    return len(token) >= CK_MIN_TOKEN and re.fullmatch(r"[A-Za-z0-9_-]+", token) is not None


def _post(url, body, params):
    req = Request(url + "?" + urlencode(params), data=json.dumps(body).encode(),
                  headers=HEADERS, method="POST")
    with urlopen(req, timeout=30) as r:
        return json.loads(r.read(16_000_000).decode("utf-8", "replace"))


def resolve(token):
    d = _post(RESOLVE_URL, {"shortGUIDs": [{"value": token}]},
              {"remapEnums": "true", "sharing_url_key": token})
    res = (d.get("results") or [None])[0]
    if not res or "anonymousPublicAccess" not in res:
        raise ValueError("album is not public (turn on Public Website / Anyone with the link)")
    acc = res["anonymousPublicAccess"]
    title = ((res.get("share") or {}).get("fields") or {}).get("cloudkit.title") or {}
    return {"title": title.get("value") or "", "zone": res["zoneID"],
            "partition": acc["databasePartition"].replace(":443", ""), "access": acc["token"]}


def records(token, alb):
    url = alb["partition"] + QUERY_PATH
    params = {"remapEnums": "true", "sharing_url_key": token, "publicAccessAuthToken": alb["access"]}
    out, marker = [], None
    for _ in range(100):                                  # 200 per page
        body = {"query": {"recordType": ASSET_QUERY, "filterBy": [
                    {"fieldName": "startRank", "comparator": "EQUALS",
                     "fieldValue": {"type": "INT64", "value": 0}},
                    {"fieldName": "direction", "comparator": "EQUALS",
                     "fieldValue": {"type": "STRING", "value": "ASCENDING"}}]},
                "zoneID": alb["zone"], "resultsLimit": 200}
        if marker:
            body["continuationMarker"] = marker
        d = _post(url, body, params)
        out += d.get("records", [])
        marker = d.get("continuationMarker")
        if not marker:
            break
    return out


def _f(rec, name):
    return ((rec.get("fields") or {}).get(name) or {}).get("value")


def build_photos(recs):
    """Pair each asset with its master; take Apple's ~2048px JPEG (edited version first)."""
    masters = {r["recordName"]: r for r in recs if r.get("recordType") == "CPLMaster"}
    photos = []
    for a in recs:
        if a.get("recordType") != "CPLAsset" or a.get("deleted"):
            continue
        m = masters.get((_f(a, "masterRef") or {}).get("recordName"))
        if m is None or _f(m, "itemType") in VIDEO_TYPES:
            continue
        pick = None
        for rec in (a, m):
            res = _f(rec, "resJPEGMedRes")
            if res and res.get("downloadURL"):
                pick = (rec, res)
                break
        if pick is None:
            continue
        rec, res = pick
        ms = _f(a, "assetDate") or _f(m, "originalCreationDate")
        when = ""
        if ms:
            tz = timezone(timedelta(seconds=_f(a, "timeZoneOffset") or 0))
            when = datetime.fromtimestamp(ms / 1000, tz=tz).isoformat()
        photos.append({"url": res["downloadURL"].replace("${f}", "image"), "caption": "",
                       "date": when,
                       "w": int(_f(rec, "resJPEGMedWidth") or 0),      # best effort, 0 if absent
                       "h": int(_f(rec, "resJPEGMedHeight") or 0)})
    return photos


def album(token):
    """Same shape as the sharedstreams path: {"photos": [...], "album": title, "error": None}."""
    alb = resolve(token)
    return {"photos": build_photos(records(token, alb)), "album": alb["title"], "error": None}


if __name__ == "__main__":
    import sys
    tok = album_token(sys.argv[1] if len(sys.argv) > 1 else "")
    print("token: %s... (%d chars, cloudkit=%s)" % (tok[:6], len(tok), is_cloudkit_token(tok)))
    alb = resolve(tok)
    recs = records(tok, alb)
    ph = build_photos(recs)
    print("title: %r, records: %d, photos: %d" % (alb["title"], len(recs), len(ph)))
    for t in ("CPLAsset", "CPLMaster"):
        r = next((x for x in recs if x.get("recordType") == t), None)
        print(t, "fields:", sorted((r or {}).get("fields", {}))[:60])
    if ph:
        print("first photo:", dict(ph[0], url=ph[0]["url"][:80] + "..."))
        print("photos with unknown size (w or h = 0): %d" % sum(1 for p in ph if not p["w"] or not p["h"]))
