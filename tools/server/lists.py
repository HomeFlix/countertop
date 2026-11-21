"""Lists: the shared grocery list and note, Apple Reminders, lists read from a web address or sent from another app, and lists kept on this dashboard."""
import json
import re
import subprocess
import threading
import time
import uuid
from datetime import datetime
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from server.core import WORK


# ---------- shared grocery list + note (work/notes.json) ----------


def notes_load():
    try:
        d = json.loads(NOTES.read_text())
        if isinstance(d, dict) and isinstance(d.get("items"), list):
            d.setdefault("note", "")
            return d
    except Exception:
        pass
    return {"items": [], "note": "", "updated": 0}


# ---------- optional: mirror an Apple Reminders list (work/reminders_list.txt holds its name) ----------
# The Mac's Reminders app (signed in to iCloud) is the source of truth; the server reads it with
# osascript. The first run makes macOS ask whether Terminal may control Reminders: click OK.
REM_FILE = WORK / "reminders_list.txt"
REM = {"items": [], "error": None, "at": 0, "done": {}}   # done: id -> (text, ts) for recently ticked items
REM_LOCK = threading.Lock()

# one bulk request for ids + names: asking item by item is very slow on big iCloud lists
REM_READ = """on run argv
  tell application "Reminders"
    set L to list (item 1 of argv)
    set {theIds, theNames} to {id, name} of (reminders of L whose completed is false)
  end tell
  set out to ""
  repeat with i from 1 to count of theIds
    set out to out & (item i of theIds) & tab & (item i of theNames) & linefeed
  end repeat
  return out
end run"""
REM_ADD = """on run argv
  tell application "Reminders" to make new reminder at end of list (item 1 of argv) with properties {name:(item 2 of argv)}
end run"""
REM_SET = """on run argv
  tell application "Reminders"
    set r to (first reminder of list (item 1 of argv) whose id is (item 2 of argv))
    set completed of r to ((item 3 of argv) is "true")
  end tell
end run"""
REM_DEL = """on run argv
  tell application "Reminders" to delete (first reminder of list (item 1 of argv) whose id is (item 2 of argv))
end run"""


def reminders_list_name():
    # the first list in Setup > Sources kept in Apple Reminders (older installs: work/reminders_list.txt)
    try:
        for L in sources_load().get("lists") or []:
            if L.get("kind") == "Apple Reminders" and (L.get("remName") or "").strip():
                return L["remName"].strip()
        return ""
    except Exception:
        pass
    try:
        return REM_FILE.read_text().strip().splitlines()[0].strip()
    except Exception:
        return ""


REM_READING = threading.Lock()


def _osa(script, *args, timeout=90):
    r = subprocess.run(["osascript", "-", *args], input=script, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or "osascript failed").strip()[:200])
    return r.stdout


def reminders_refresh():
    name = reminders_list_name()
    if not name or not REM_READING.acquire(blocking=False):
        return                                   # a read is already running
    try:
        t0 = time.time()
        out = _osa(REM_READ, name)
        items = []
        for ln in out.splitlines():
            if "\t" in ln:
                rid, text = ln.split("\t", 1)
                items.append({"id": rid, "text": text.strip(), "done": False})
        with REM_LOCK:
            REM["items"], REM["error"], REM["at"] = items, None, time.time()
            REM["took"] = round(time.time() - t0, 1)
        try:
            purchases_log_list(items)
        except Exception:
            pass
    except subprocess.TimeoutExpired:
        with REM_LOCK:
            REM["error"], REM["at"] = ("Reminders didn't answer in 90 s. Is a permission prompt waiting on the Mac?"), time.time()
    except Exception as e:
        with REM_LOCK:
            REM["error"], REM["at"] = str(e), time.time()
    finally:
        REM_READING.release()


def reminders_loop():
    while True:
        try:
            reminders_refresh()
        except Exception:
            pass
        time.sleep(120)


# ---------- a list read from a web address (a published text file, a Markdown checklist, JSON, iCal to-dos) ----------
URL_LISTS = {}            # list id -> {at, items, error, host, key}
URL_LIST_LOCK = threading.Lock()
_BULLET = re.compile(r"^\s*(?:[-*+\u2022\u25e6\u25aa]|\d+[.)])?\s*(?:\[( |x|X)\]\s*)?")


def _list_from_text(raw):
    raw = raw.lstrip("\ufeff")
    t = raw.strip()
    if t[:1] in "[{":
        try:
            d = json.loads(t)
            if isinstance(d, dict):
                d = next((d[k] for k in ("items", "list", "tasks", "todos", "data") if isinstance(d.get(k), list)), [])
            out = []
            for x in d if isinstance(d, list) else []:
                if isinstance(x, dict):
                    if x.get("done") or x.get("completed") or x.get("checked") or x.get("complete"):
                        continue
                    x = x.get("text") or x.get("title") or x.get("name") or x.get("content") or x.get("summary") or ""
                out.append(str(x))
            return out
        except ValueError:
            pass
    if "BEGIN:VTODO" in raw:
        out = []
        for block in _unfold(raw).split("BEGIN:VTODO")[1:]:
            block = block.split("END:VTODO")[0]
            status = (_field(block, "STATUS") or "").upper()
            if status in ("COMPLETED", "CANCELLED") or _field(block, "COMPLETED"):
                continue
            out.append(_field(block, "SUMMARY") or "")
        return out
    out = []
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith(("#", "//")):
            continue
        m = _BULLET.match(line)
        if m and m.group(1) in ("x", "X"):
            continue                                   # a ticked Markdown checkbox
        out.append(line[m.end():] if m else line)
    return out


def url_list(L, max_age=300):
    """The list at a web address, read at most every five minutes."""
    url = (L.get("url") or "").strip()
    if url.startswith("webcal://"):
        url = "https://" + url[len("webcal://"):]
    host = urlparse(url).hostname or ""
    with URL_LIST_LOCK:
        c = URL_LISTS.get(L["id"])
        if c and c.get("key") == url and time.time() - c["at"] < max_age:
            return c
    try:
        if not url.startswith(("http://", "https://")):
            raise ValueError("the address should start with https://")
        req = Request(url, headers={"User-Agent": "Countertop/%s (+https://github.com/%s)" % (VERSION, REPO),
                                    "Accept": "text/plain, application/json, text/calendar, */*"})
        raw = urlopen(req, timeout=15).read(1_000_000).decode("utf-8", "replace")
        items, seen = [], set()
        for x in _list_from_text(raw)[:300]:
            t = " ".join(str(x).split())[:80]
            if t and t.lower() not in seen:
                seen.add(t.lower())
                items.append({"id": "u%d" % len(items), "text": t, "done": False})
        out = {"at": time.time(), "items": items, "error": None, "host": host, "key": url}
    except Exception as e:
        prev = URL_LISTS.get(L["id"]) or {}
        out = {"at": time.time(), "items": prev.get("items", []) if prev.get("key") == url else [], "host": host, "key": url,
               "error": "Couldn't read the list: " + str(e).replace(url, "(link)")[:140]}
    with URL_LIST_LOCK:
        URL_LISTS[L["id"]] = out
    return out


# ---------- a list another app sends here (Reminders Sync in the Mac app, an iPhone Shortcut, a script) ----------
PUSHED_FILE = WORK / "pushed_lists.json"
PUSHED_LOCK = threading.Lock()


def pushed_list():
    """The first list in Setup kept in another app (sent here, or read from a web address), if it comes before any Reminders list."""
    try:
        for L in sources_load().get("lists") or []:
            if L.get("kind") == PUSHED or (L.get("kind") == FROM_URL and (L.get("url") or "").strip()):
                return L
            if L.get("kind") == "Apple Reminders" and (L.get("remName") or "").strip():
                return None
    except Exception:
        pass
    return None


def pushed_load():
    try:
        d = json.loads(PUSHED_FILE.read_text())
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def list_push(body):
    """POST /lists/push {key, items:[text | {id,text}] or text:"one per line", via?}. Replaces the whole list."""
    key = str(body.get("key") or "").strip()
    target = None
    for L in sources_load().get("lists") or []:
        if L.get("kind") == PUSHED and key and L.get("pushKey") == key:
            target = L
    if not target:
        return 403, {"error": "unknown sync key. Copy it from Controls > Setup > Lists"}
    raw = body.get("items")
    if raw is None:
        raw = body.get("text") if body.get("text") is not None else body.get("raw", "")
    if isinstance(raw, str):
        raw = raw.splitlines()
    if not isinstance(raw, list):
        return 400, {"error": "send items as a list, or text with one item per line"}
    with PUSHED_LOCK:
        all_ = pushed_load()
        prev = {i["text"].lower(): i["id"] for i in (all_.get(target["id"]) or {}).get("items", [])}
        items, seen = [], set()
        for x in raw[:300]:
            rid = ""
            if isinstance(x, dict):
                rid, x = str(x.get("id") or "")[:120], x.get("text") or x.get("title") or ""
            t = " ".join(str(x).split())[:80]
            if not t or t.lower() in seen:
                continue
            seen.add(t.lower())
            items.append({"id": rid or prev.get(t.lower()) or uuid.uuid4().hex[:10], "text": t, "done": False})
        all_[target["id"]] = {"items": items, "at": time.time(), "via": str(body.get("via") or "")[:40]}
        PUSHED_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = PUSHED_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(all_, ensure_ascii=False, indent=1))
        tmp.chmod(0o600)
        tmp.replace(PUSHED_FILE)
    try:
        purchases_log_list(items)
    except Exception:
        pass
    return 200, {"ok": True, "list": target.get("name"), "count": len(items)}


def notes_view():
    d = notes_load()
    pl = pushed_list()
    if pl and pl.get("kind") == FROM_URL:
        got = url_list(pl)
        return dict(d, items=got.get("items", []), source="url", list=pl.get("name") or "List", via=got.get("host") or "",
                    pushedAt=got.get("at") or 0, readonly=True, error=got.get("error"))
    if pl:
        got = pushed_load().get(pl["id"]) or {}
        return dict(d, items=got.get("items", []), source="pushed", list=pl.get("name") or "List", via=got.get("via") or "",
                    pushedAt=got.get("at") or 0, readonly=True,
                    error=None if got else "Nothing sent yet. Turn on Reminders Sync in the Mac app or set up a Shortcut with this list's sync key.")
    name = reminders_list_name()
    if not name:
        # no list from another app: the phone page at /list (which sends no list id) edits the
        # first list kept on this dashboard, as it always did with the shared grocery list
        for L in sources_load().get("lists") or []:
            if (L.get("kind") or LOCAL_LIST) == LOCAL_LIST:
                return local_list_view(L["id"])
        return d
    with REM_LOCK:
        cutoff = time.time() - 3 * 3600
        REM["done"] = {k: v for k, v in REM["done"].items() if v[1] > cutoff}
        open_ids = {i["id"] for i in REM["items"]}
        done = [{"id": k, "text": v[0], "done": True} for k, v in REM["done"].items() if k not in open_ids]
        d = dict(d, items=[dict(i) for i in REM["items"]] + done, source="reminders", list=name,
                 error=REM["error"], took=REM.get("took"))
    return d


def reminders_apply(body):
    name, op, rid = reminders_list_name(), body.get("op"), str(body.get("id") or "")
    try:
        if op == "add":
            for text in [" ".join(str(body.get("text") or "").split())[:80]]:
                if text:
                    _osa(REM_ADD, name, text)
        elif op == "toggle":
            with REM_LOCK:
                was_done = rid in REM["done"]
                text = next((i["text"] for i in REM["items"] if i["id"] == rid), None)
            _osa(REM_SET, name, rid, "false" if was_done else "true")
            with REM_LOCK:
                if was_done:
                    REM["done"].pop(rid, None)
                elif text is not None:
                    REM["done"][rid] = (text, time.time())
        elif op == "remove":
            _osa(REM_DEL, name, rid)
            with REM_LOCK:
                REM["done"].pop(rid, None)
        elif op == "clear_done":
            with REM_LOCK:
                REM["done"].clear()
    except Exception as e:
        with REM_LOCK:
            REM["error"] = str(e)
    reminders_refresh()
    return notes_view()


def notes_apply(body):
    # no list id (the phone page at /list): edit the first list kept on this dashboard
    for L in sources_load().get("lists") or []:
        if (L.get("kind") or LOCAL_LIST) == LOCAL_LIST:
            return local_list_apply(L["id"], body)
    op = str(body.get("op") or "")
    with NOTES_LOCK:
        d = notes_load()
        items = d["items"]
        if op == "add":
            text = " ".join(str(body.get("text") or "").split())[:80]
            if text and len(items) < 80 and not any(
                    i["text"].lower() == text.lower() and not i.get("done") for i in items):
                items.append({"id": uuid.uuid4().hex[:8], "text": text, "done": False})
        elif op == "toggle":
            for i in items:
                if i["id"] == body.get("id"):
                    i["done"] = not i.get("done")
        elif op == "remove":
            d["items"] = [i for i in items if i["id"] != body.get("id")]
        elif op == "clear_done":
            d["items"] = [i for i in items if not i.get("done")]
        elif op == "note":
            d["note"] = str(body.get("text") or "").strip()[:240]
        else:
            return d
        d["updated"] = int(time.time())
        NOTES.parent.mkdir(parents=True, exist_ok=True)
        tmp = NOTES.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1))
        tmp.replace(NOTES)
        return d


# ---------- lists kept on this dashboard, one entry per list (work/lists.json) ----------
# A list set up in Sources as "This dashboard" is edited right on the List tile. Its ticks can be
# cleared automatically when the day changes (the items stay), so it works as a daily checklist.
LISTS_FILE = WORK / "lists.json"
LISTS_LOCK = threading.Lock()
LOCAL_LIST = "This dashboard"


def _lists_load():
    try:
        d = json.loads(LISTS_FILE.read_text())
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _lists_save(d):
    LISTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = LISTS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1))
    tmp.chmod(0o600)
    tmp.replace(LISTS_FILE)


def local_list_source(list_id):
    """The list set up in Sources as kept on this dashboard, if list_id names one."""
    for L in sources_load().get("lists") or []:
        if L.get("id") == list_id and (L.get("kind") or LOCAL_LIST) == LOCAL_LIST:
            return L
    return None


def _today():
    return datetime.now().strftime("%Y-%m-%d")


def _local_list(rec, daily):
    """The 00:00 reset: on a new calendar day the ticks are cleared, the items stay."""
    today = _today()
    rec.setdefault("items", [])
    rec.setdefault("date", today)
    if daily and rec.get("date") != today:
        for i in rec["items"]:
            i["done"] = False
        rec["date"] = today
    return rec


def _local_record(all_, list_id):
    """A list's saved items. Before lists had their own entries here, every list kept on this dashboard showed
    the items in work/notes.json, so a list with no entry yet starts from those (notes.json is left as it was)."""
    rec = all_.get(list_id)
    if isinstance(rec, dict):
        return rec
    old = notes_load()
    return {"items": [dict(i) for i in old.get("items") or [] if isinstance(i, dict)],
            "note": old.get("note") or "", "updated": old.get("updated") or 0}


def _local_view(L, rec):
    return {"list": L.get("name") or "List", "source": "local", "date": rec.get("date"),
            "items": rec["items"], "updated": rec.get("updated", 0), "note": rec.get("note", ""),
            "daily": bool(L.get("daily")), "readonly": False}


def local_list_view(list_id):
    L = local_list_source(list_id) or {"id": list_id, "name": "List"}
    with LISTS_LOCK:
        all_ = _lists_load()
        rec = _local_record(all_, list_id)
        was = rec.get("date")
        rec = _local_list(rec, bool(L.get("daily")))
        if list_id not in all_ or was != rec.get("date"):
            all_[list_id] = rec
            _lists_save(all_)
    return _local_view(L, rec)


def local_list_apply(list_id, body):
    op = str(body.get("op") or "")
    L = local_list_source(list_id) or {"id": list_id, "name": "List"}
    with LISTS_LOCK:
        all_ = _lists_load()
        rec = _local_list(_local_record(all_, list_id), bool(L.get("daily")))
        items = rec["items"]
        if op == "add":
            text = " ".join(str(body.get("text") or "").split())[:80]
            if text and len(items) < 80 and not any(i["text"].lower() == text.lower() and not i.get("done") for i in items):
                items.append({"id": uuid.uuid4().hex[:8], "text": text, "done": False})
        elif op == "toggle":
            for i in items:
                if i["id"] == body.get("id"):
                    i["done"] = not i.get("done")
        elif op == "remove":
            rec["items"] = [i for i in items if i["id"] != body.get("id")]
        elif op == "reset":                     # clear every tick now (same as the midnight reset)
            for i in items:
                i["done"] = False
        elif op == "clear_done":
            rec["items"] = [i for i in items if not i.get("done")]
        elif op == "clear":                     # empty the whole list
            rec["items"] = []
        elif op == "note":
            rec["note"] = str(body.get("text") or "").strip()[:240]
        rec["updated"] = int(time.time())
        all_[list_id] = rec
        _lists_save(all_)
    return _local_view(L, rec)


# names used only inside functions: imported last, so these modules can use each other
from server.core import NOTES, NOTES_LOCK, REPO, VERSION  # noqa: E402
from server.feeds.calendar import _field, _unfold  # noqa: E402
from server.feeds.sales import purchases_log_list  # noqa: E402
from server.sources import FROM_URL, PUSHED, sources_load  # noqa: E402
