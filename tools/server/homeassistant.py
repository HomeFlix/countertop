"""Home Assistant: reading states and calling services for the Home and Sensor tiles."""
import collections
import json
import re
import ssl
import threading
import time
from urllib.parse import urlparse
from urllib.request import Request, urlopen


# ---------- Home Assistant (Setup > Home Assistant; the Home and Sensor tiles) ----------
# The server talks to Home Assistant's REST API with the token from Setup; tiles only ever talk to this server.
# States are fetched on demand and kept for a few seconds, so several tiles share one request.
HA_CACHE = {}             # source id -> {at, states: {entity_id: compact state}, error}
HA_LOCKS = collections.defaultdict(threading.Lock)
HA_STATUS = {}            # source id -> {name, at, ok, error, count, version}
HA_TTL = 4
HA_TAPS = {"light": "toggle", "switch": "toggle", "fan": "toggle", "input_boolean": "toggle", "scene": "turn_on", "script": "turn_on"}


def ha_source(sid=""):
    L = [x for x in sources_load().get("homeassistant") or [] if x.get("url") and x.get("token")]
    return next((x for x in L if x.get("id") == sid), None) or (L[0] if L and not sid else None) or (L[0] if len(L) == 1 else None)


def _ha_url(src):
    u = (src.get("url") or "").strip().rstrip("/")
    if u and "://" not in u:
        u = "http://" + u
    return u


def _ha_error(e, src):
    """A plain-words reason, never the token (urllib errors don't carry request headers; the address is reduced to its host)."""
    host = urlparse(_ha_url(src)).hostname or "Home Assistant"
    code = getattr(e, "code", None)
    if code == 401:
        return "Home Assistant didn't accept the access token. Make a new one and paste it in Setup."
    if code == 404:
        return "%s answered, but it doesn't look like Home Assistant (check the address and port, usually 8123)." % host
    if code:
        return "Home Assistant answered with error %s." % code
    r = str(getattr(e, "reason", e))
    if isinstance(getattr(e, "reason", None), ssl.SSLError) or "CERTIFICATE" in r.upper():
        return "Couldn't check %s's certificate. Try its http:// address on your network instead." % host
    if "Name or service not known" in r or "nodename nor servname" in r or "getaddrinfo" in r or "No address associated" in r:
        return "Couldn't find %s. Use its IP address instead, e.g. http://192.168.1.20:8123%s." % (host, " (names ending in .local often don't work in Docker)" if host.endswith(".local") else "")
    if "refused" in r.lower():
        return "%s refused the connection. Is Home Assistant running, and is the port right (usually 8123)?" % host
    if "timed out" in r.lower():
        return "%s didn't answer in time." % host
    return ("Couldn't reach Home Assistant: " + r.replace(src.get("token") or "\0", "<token>"))[:200]


def ha_request(src, method, path, body=None, timeout=10):
    req = Request(_ha_url(src) + path, data=json.dumps(body).encode() if body is not None else None, method=method,
                  headers={"Authorization": "Bearer " + (src.get("token") or "").strip(), "Content-Type": "application/json",
                           "User-Agent": "Countertop/" + VERSION})
    with urlopen(req, timeout=timeout) as r:
        raw = r.read(8_000_000)
    return json.loads(raw.decode("utf-8", "replace")) if raw else None


def _ha_compact(st):
    a = st.get("attributes") or {}
    eid = st.get("entity_id") or ""
    o = {"id": eid, "domain": eid.split(".")[0], "state": st.get("state"), "name": a.get("friendly_name") or eid,
         "unit": a.get("unit_of_measurement") or "", "dc": a.get("device_class") or "", "icon": a.get("icon") or "",
         "changed": st.get("last_changed") or ""}
    if eid.startswith("light.") and a.get("brightness") is not None:
        o["level"] = round(a["brightness"] / 255 * 100)
    if eid.startswith("fan.") and a.get("percentage") is not None:
        o["level"] = a["percentage"]
    if eid.startswith(("climate.", "water_heater.")):
        o["current"] = a.get("current_temperature")
        o["target"] = a.get("temperature")
    if eid.startswith("weather."):
        o["temp"] = a.get("temperature")
        o["unit"] = a.get("temperature_unit") or ""
    if eid.startswith("cover.") and a.get("current_position") is not None:
        o["level"] = a["current_position"]
    if eid.startswith("media_player.") and a.get("media_title"):
        o["media"] = " \u00b7 ".join(str(x) for x in (a.get("media_title"), a.get("media_artist")) if x)
    return o


def ha_states(src, force=False):
    sid = src.get("id")
    with HA_LOCKS[sid]:
        c = HA_CACHE.get(sid)
        if c and not force and time.time() - c["at"] < HA_TTL:
            return c
        try:
            L = ha_request(src, "GET", "/api/states")
            c = {"at": time.time(), "states": {st["entity_id"]: _ha_compact(st) for st in L or [] if st.get("entity_id")}, "error": ""}
            HA_STATUS[sid] = dict(HA_STATUS.get(sid) or {}, name=src.get("name") or "Home Assistant", at=c["at"], ok=True, error="", count=len(c["states"]))
        except Exception as e:
            msg = _ha_error(e, src)
            old = HA_CACHE.get(sid) or {}
            c = {"at": time.time(), "states": old.get("states") or {}, "error": msg}       # keep showing the last states we had
            HA_STATUS[sid] = dict(HA_STATUS.get(sid) or {}, name=src.get("name") or "Home Assistant", ok=False, error=msg, tried=time.time())
        HA_CACHE[sid] = c
        return c


def ha_view(sid, ids):
    src = ha_source(sid)
    if not src:
        return {"error": "Set up Home Assistant in Controls \u2192 Setup first.", "states": []}
    c = ha_states(src)
    want = [x for x in ids if x]
    S = c["states"]
    return {"error": c["error"], "at": c["at"], "src": src.get("id"),
            "states": [S.get(x) or {"id": x, "domain": x.split(".")[0], "state": "missing", "name": x} for x in want]}


def ha_entities(sid):
    src = ha_source(sid)
    if not src:
        return {"error": "Set up Home Assistant in Controls \u2192 Setup first.", "entities": []}
    c = ha_states(src)
    L = sorted(c["states"].values(), key=lambda o: (o["domain"], o["name"].lower()))
    return {"error": c["error"], "entities": [{"id": o["id"], "name": o["name"], "domain": o["domain"], "state": o["state"], "unit": o["unit"]} for o in L]}


def _ha_allowed(sid, entity):
    """Taps may only switch things a Home tile on the dashboard is set up to switch: anyone on the network can reach this server."""
    try:
        items = config_load()["modules"]["tiles"]["settings"].get("items") or []
    except Exception:
        items = []
    first = (ha_source("") or {}).get("id")
    for it in items:
        s = it.get("settings") or {}
        if it.get("type") != "ha" or s.get("taps") is False:
            continue
        if (s.get("src") or first) != sid:
            continue
        if entity in (s.get("entities") or []):
            return True
    return False


def ha_call(body):
    src = ha_source(str(body.get("src") or ""))
    entity = str(body.get("entity") or "")
    if not src:
        return 400, {"error": "Home Assistant isn't set up"}
    dom = entity.split(".")[0]
    if dom not in HA_TAPS or not re.fullmatch(r"[a-z_]+\.[a-z0-9_]+", entity):
        return 403, {"error": "That can't be switched from the screen"}
    if not _ha_allowed(src.get("id"), entity):
        return 403, {"error": "Add it to a Home tile first"}
    try:
        ha_request(src, "POST", "/api/services/%s/%s" % (dom, HA_TAPS[dom]), {"entity_id": entity})
    except Exception as e:
        return 502, {"error": _ha_error(e, src)}
    log_entry({"t": time.strftime("%H:%M:%S"), "kind": "ha", "task": "tap", "result": entity})
    c = ha_states(src, force=True)
    return 200, {"ok": True, "state": c["states"].get(entity)}


def ha_test(body):
    """Setup's Test button: the fields as typed, with the saved token when the token box was left blank."""
    item = body.get("item") or {}
    saved = next((x for x in sources_load().get("homeassistant") or [] if x.get("id") == item.get("id")), {}) if item.get("id") else {}
    src = {"url": (item.get("url") or saved.get("url") or "").strip(), "token": (item.get("token") or saved.get("token") or "").strip(), "id": "test"}
    if not src["url"]:
        return {"ok": False, "error": "Type the address first."}
    if not src["token"]:
        return {"ok": False, "error": "Paste an access token first."}
    try:
        cfg = ha_request(src, "GET", "/api/config")
        n = len(ha_request(src, "GET", "/api/states") or [])
    except Exception as e:
        return {"ok": False, "error": _ha_error(e, src)}
    return {"ok": True, "version": cfg.get("version"), "name": cfg.get("location_name"), "count": n}


# names used only inside functions: imported last, so these modules can use each other
from server.config import config_load  # noqa: E402
from server.core import VERSION, log_entry  # noqa: E402
from server.sources import sources_load  # noqa: E402
