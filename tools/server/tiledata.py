"""Tile data: what a tile on the dashboard writes for itself while it runs (a to-do list, a tally, a chore rota).

Each tile on the dashboard has its own small store, kept in <data folder>/tiles/<tile id>.json. Adding a second
tile of the same kind starts a new, empty store, so tiles never share or overwrite each other's data.

Tile data is not a setting: Controls doesn't save it, it never goes into a shared layout, and it lives as long as
the tile is on the dashboard. When a tile is removed its data moves to tiles/.trash and is kept for 30 days, so
undoing the removal or restoring a settings backup brings it back.

A tile changes its data with small operations the server applies one at a time (see apply_ops), so a screen and a
phone writing at the same moment can't undo each other's changes.
"""
import json
import re
import threading
import time
import uuid
from pathlib import Path

ID_RE = re.compile(r"[A-Za-z0-9_-]{1,48}")
KEY_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,39}")
MAX_BYTES = 256 * 1024       # per tile, as stored
MAX_ITEMS = 500              # per list inside a tile's data
MAX_OPS = 50                 # per request
TRASH_DAYS = 30
BACKUP_KEEP = 12
BACKUP_EVERY = 15 * 60

LOCK = threading.Lock()
STATE = {"dir": None, "backups": None, "rev": 0, "revs": {}, "backup_at": 0.0}


class TileDataError(ValueError):
    def __init__(self, msg, code=400):
        super().__init__(msg)
        self.code = code


def init(work: Path, backups: Path):
    """Point the store at the data folder and pick up where the last run left off."""
    with LOCK:
        STATE["dir"] = Path(work) / "tiles"
        STATE["backups"] = Path(backups)
        STATE["revs"] = {}
        STATE["rev"] = 0
        d = STATE["dir"]
        if d.exists():
            for f in d.glob("*.json"):
                rec = _read(f)
                if rec is not None:
                    STATE["revs"][f.stem] = rec.get("rev", 0)
                    STATE["rev"] = max(STATE["rev"], rec.get("rev", 0))


def _path(tid):
    return STATE["dir"] / (tid + ".json")


def _read(f):
    try:
        rec = json.loads(Path(f).read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(rec, dict) or not isinstance(rec.get("data"), dict):
        return None
    return rec


def _write(tid, rec):
    STATE["dir"].mkdir(parents=True, exist_ok=True)
    f = _path(tid)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(rec, ensure_ascii=False, separators=(",", ":")))
    tmp.replace(f)


def check_id(tid):
    if not isinstance(tid, str) or not ID_RE.fullmatch(tid):
        raise TileDataError("bad tile id")
    return tid


# ---------- reading ----------

def changed(since, live):
    """Data of every tile in `live` (tile id -> type) that changed after revision `since`; all of them for since=0."""
    out = {}
    with LOCK:
        rev = STATE["rev"]
        for tid in live:
            r = STATE["revs"].get(tid)
            if r is None or r <= since:
                continue
            rec = _read(_path(tid))
            if rec is not None:
                out[tid] = rec["data"]
    return {"rev": rev, "tiles": out}


def get(tid):
    with LOCK:
        rec = _read(_path(check_id(tid)))
    return (rec or {}).get("data", {})


# ---------- writing ----------

def _item_id():
    return uuid.uuid4().hex[:10]


def _list(data, key):
    v = data.get(key)
    if v is None:
        v = data[key] = []
    if not isinstance(v, list):
        raise TileDataError("%s isn't a list" % key)
    return v


def _plain(v, depth=0):
    """Only JSON values go into a store: no NaN, nothing nested deeper than 6 levels."""
    if depth > 6:
        raise TileDataError("data is nested too deeply")
    if v is None or isinstance(v, (bool, str)):
        return v
    if isinstance(v, (int, float)):
        if v != v or v in (float("inf"), float("-inf")):
            raise TileDataError("not a number")
        return v
    if isinstance(v, list):
        return [_plain(x, depth + 1) for x in v]
    if isinstance(v, dict):
        return {str(k)[:40]: _plain(x, depth + 1) for k, x in v.items()}
    raise TileDataError("unsupported value")


def apply_op(data, op):
    """One operation on a tile's data (a dict). Lists hold items that are dicts with an "id".

    set       {key, value}            data[key] = value (value null removes the key)
    push      {key, item}             append an item; it gets an id when it has none
    update    {key, id, fields}       merge fields into the item with that id
    remove    {key, id}               drop the item with that id
    updateAll {key, fields}           merge fields into every item (e.g. untick everything)
    removeWhere {key, fields}         drop every item whose fields all match (e.g. clear the ticked ones)
    """
    if not isinstance(op, dict):
        raise TileDataError("bad operation")
    kind, key = op.get("op"), op.get("key")
    if not isinstance(key, str) or not KEY_RE.fullmatch(key):
        raise TileDataError("bad key")
    if kind == "set":
        v = _plain(op.get("value"))
        if v is None:
            data.pop(key, None)
        else:
            data[key] = v
    elif kind == "push":
        item = _plain(op.get("item"))
        if not isinstance(item, dict):
            raise TileDataError("an item is an object")
        L = _list(data, key)
        if len(L) >= MAX_ITEMS:
            raise TileDataError("that list is full (%d items)" % MAX_ITEMS, 413)
        iid = item.get("id")
        if not (isinstance(iid, str) and ID_RE.fullmatch(iid)) or any(isinstance(x, dict) and x.get("id") == iid for x in L):
            item["id"] = _item_id()
        L.append(item)
    elif kind in ("update", "updateAll", "removeWhere"):
        fields = _plain(op.get("fields"))
        if not isinstance(fields, dict):
            raise TileDataError("fields is an object")
        fields.pop("id", None)
        L = _list(data, key)
        if kind == "removeWhere":
            data[key] = [x for x in L if not (isinstance(x, dict) and all(x.get(k) == v for k, v in fields.items()))]
        else:
            for x in L:
                if isinstance(x, dict) and (kind == "updateAll" or x.get("id") == op.get("id")):
                    x.update(fields)
    elif kind == "remove":
        data[key] = [x for x in _list(data, key) if not (isinstance(x, dict) and x.get("id") == op.get("id"))]
    else:
        raise TileDataError("unknown operation")


def apply(tid, body, live):
    """Apply {"ops": [...], "unless": {...}} (or one bare operation) to a tile's data, all or nothing.

    `unless` skips the whole change when the data already has those values, so several screens can make the same
    once-a-day change (clear yesterday's ticks) and only the first one does it. `live` is the set of tile ids on
    the saved dashboard: a tile that isn't saved (a preview, a layout being tried) can't write.
    """
    check_id(tid)
    if tid not in live:
        raise TileDataError("that tile isn't on the saved dashboard", 404)
    if not isinstance(body, dict):
        raise TileDataError("bad request")
    ops = body.get("ops") if "ops" in body else [body]
    if not isinstance(ops, list) or not ops or len(ops) > MAX_OPS:
        raise TileDataError("bad operations")
    unless = body.get("unless")
    with LOCK:
        rec = _read(_path(tid)) or {"data": {}, "rev": 0}
        data = json.loads(json.dumps(rec["data"]))
        if isinstance(unless, dict) and unless and all(data.get(k) == v for k, v in unless.items()):
            return {"rev": rec.get("rev", 0), "data": rec["data"], "skipped": True}
        for op in ops:
            apply_op(data, op)
        size = len(json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode())
        if size > MAX_BYTES:
            raise TileDataError("this tile's data is full (%d KB)" % (MAX_BYTES // 1024), 413)
        STATE["rev"] += 1
        rec = {"type": live.get(tid) or rec.get("type") or "", "rev": STATE["rev"], "updated": int(time.time()), "data": data}
        _write(tid, rec)
        STATE["revs"][tid] = rec["rev"]
        _backup_locked()
    return {"rev": rec["rev"], "data": data}


# ---------- tiles added and removed ----------

def sync(live):
    """Called after settings are saved. Data of tiles no longer on the dashboard goes to the trash; a tile that comes
    back (undo, a restored backup) gets its data back from the trash. Trash older than 30 days is deleted."""
    d = STATE["dir"]
    if d is None:
        return
    trash = d / ".trash"
    now = time.time()
    with LOCK:
        if d.exists():
            for f in d.glob("*.json"):
                if f.stem not in live:
                    trash.mkdir(parents=True, exist_ok=True)
                    f.replace(trash / ("%s~%d.json" % (f.stem, int(now))))
                    STATE["revs"].pop(f.stem, None)
        if trash.exists():
            back = {}
            for f in trash.glob("*.json"):
                tid, _, stamp = f.stem.rpartition("~")
                if not stamp.isdigit():
                    continue
                if now - int(stamp) > TRASH_DAYS * 86400:
                    try:
                        f.unlink()
                    except OSError:
                        pass
                elif tid in live and not _path(tid).exists() and int(stamp) > back.get(tid, (0, None))[0]:
                    back[tid] = (int(stamp), f)
            for tid, (_, f) in back.items():
                rec = _read(f)
                if rec is None:
                    continue
                STATE["rev"] += 1
                rec["rev"] = STATE["rev"]
                _write(tid, rec)
                STATE["revs"][tid] = rec["rev"]
                f.unlink()


# ---------- backups ----------

def _backup_locked(force=False):
    """At most every 15 minutes, one file in the backups folder with every tile's data; the newest 12 are kept."""
    b = STATE["backups"]
    if b is None or (not force and time.time() - STATE["backup_at"] < BACKUP_EVERY):
        return
    STATE["backup_at"] = time.time()
    try:
        allrec = {}
        for f in STATE["dir"].glob("*.json"):
            rec = _read(f)
            if rec is not None:
                allrec[f.stem] = rec
        b.mkdir(parents=True, exist_ok=True)
        dest = b / ("tiledata-%s.json" % time.strftime("%Y%m%d-%H%M%S"))
        dest.write_text(json.dumps(allrec, ensure_ascii=False))
        for old in sorted(b.glob("tiledata-*.json"))[:-BACKUP_KEEP]:
            old.unlink()
    except OSError as e:
        print("couldn't back up tile data: %s" % e, flush=True)
