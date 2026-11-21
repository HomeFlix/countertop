"""Around you: rain radar, NASA's picture of the day, the ISS and planes overhead."""
import time
from datetime import datetime


# --- big tile data: rain radar frames, NASA picture of the day, space station position ---
RADAR_CACHE = {"at": 0, "data": None}


def radar_frames():
    if RADAR_CACHE["data"] and time.time() - RADAR_CACHE["at"] < 300:
        return RADAR_CACHE["data"]
    try:
        j = _get_json("https://api.rainviewer.com/public/weather-maps.json")
        rad = j.get("radar") or {}
        out = {"host": j.get("host") or "https://tilecache.rainviewer.com",
               "past": rad.get("past") or [], "nowcast": rad.get("nowcast") or [], "error": None}
        RADAR_CACHE.update(at=time.time(), data=out)
        return out
    except Exception as e:
        return dict(RADAR_CACHE["data"] or {"host": "", "past": [], "nowcast": []}, error=str(e)[:200])


SPACE_CACHE = {"day": "", "at": 0, "data": None}


def space_picture():
    day = datetime.now().strftime("%Y-%m-%d")
    if SPACE_CACHE["data"] and (SPACE_CACHE["day"] == day or time.time() - SPACE_CACHE["at"] < 1800):
        return SPACE_CACHE["data"]
    try:
        j = _get_json("https://api.nasa.gov/planetary/apod?api_key=DEMO_KEY&thumbs=true")
        out = {k: j.get(k) for k in ("title", "date", "url", "media_type", "thumbnail_url", "explanation", "copyright")}
        out["error"] = None
        SPACE_CACHE.update(day=j.get("date") or day, at=time.time(), data=out)
        return out
    except Exception as e:
        SPACE_CACHE["at"] = time.time()
        return dict(SPACE_CACHE["data"] or {}, error=str(e)[:200])


# ---------- planes overhead: adsb.lol (free, no key; community ADS-B receivers), cached 15 s ----------
PLANE_CACHE = {}


def planes_near(radius_mi=15):
    g = config_load()["modules"]["general"]["settings"]
    lat, lon = g.get("lat"), g.get("lon")
    if lat in (None, "") or lon in (None, ""):
        return {"planes": [], "error": "no location set"}
    r_nm = max(2, min(50, round(float(radius_mi) / 1.15078)))
    key = "%s,%s,%s" % (lat, lon, r_nm)
    c = PLANE_CACHE.get(key)
    if c and time.time() - c["at"] < 15:
        return c["data"]
    out = {"planes": [], "error": None, "lat": lat, "lon": lon, "radius": radius_mi}
    try:
        j = None
        for url in ("https://api.adsb.lol/v2/point/%s/%s/%s" % (lat, lon, r_nm),
                    "https://api.airplanes.live/v2/point/%s/%s/%s" % (lat, lon, r_nm)):
            try:
                j = _get_json(url, timeout=8)
                break
            except Exception as e:
                out["error"] = str(e)[:160]
        if j is not None:
            out["error"] = None
            for a in (j.get("ac") or j.get("aircraft") or [])[:200]:
                if a.get("lat") is None or a.get("lon") is None:
                    continue
                alt = a.get("alt_baro")
                out["planes"].append({
                    "flight": (a.get("flight") or "").strip(), "reg": a.get("r") or "", "type": a.get("t") or "",
                    "desc": a.get("desc") or "", "lat": a.get("lat"), "lon": a.get("lon"),
                    "alt": None if alt in (None, "ground") else alt, "ground": alt == "ground",
                    "speed": a.get("gs"), "track": a.get("track"), "from": a.get("orig") or "", "to": a.get("dest") or ""})
        PLANE_CACHE.clear()
        PLANE_CACHE[key] = {"at": time.time(), "data": out}
    except Exception as e:
        out["error"] = str(e)[:200]
    return out


ISS_CACHE = {"at": 0, "now": None, "track_at": 0, "track": []}


def iss_now():
    base = "https://api.wheretheiss.at/v1/satellites/25544"
    out = {"error": None}
    try:
        if time.time() - ISS_CACHE["at"] > 4:
            ISS_CACHE.update(at=time.time(), now=_get_json(base, timeout=8))
        if time.time() - ISS_CACHE["track_at"] > 600:
            t0 = int(time.time())
            stamps = [t0 + 120 * i for i in range(-15, 31)]            # -30 min to +60 min, every 2 min
            track = []
            for i in range(0, len(stamps), 10):                          # the API takes 10 at a time
                track += _get_json(base + "/positions?units=kilometers&timestamps=" +
                                   ",".join(str(x) for x in stamps[i:i + 10]), timeout=10)
            ISS_CACHE.update(track_at=time.time(), track=[{"t": p["timestamp"], "lat": p["latitude"], "lon": p["longitude"]} for p in track])
    except Exception as e:
        out["error"] = str(e)[:200]
    n = ISS_CACHE["now"] or {}
    out.update(lat=n.get("latitude"), lon=n.get("longitude"), alt=n.get("altitude"), vel=n.get("velocity"),
               vis=n.get("visibility"), t=n.get("timestamp"), track=ISS_CACHE["track"])
    return out


# names used only inside functions: imported last, so these modules can use each other
from server.config import config_load  # noqa: E402
from server.core import _get_json  # noqa: E402
