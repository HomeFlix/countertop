"""Tile actions: what a tile on the dashboard may ask the server to do (this.act), checked against that tile's own settings."""
import json
import re
import threading
import time
import uuid


# ---------- tile actions: what a tile on the dashboard may ask the server to do (this.act in tiles) ----------
# POST /tile-act/<tile id> {"action": "ha.call", "args": {...}}. The server looks the tile up in the saved settings
# and the action checks the request against that tile's own settings, so a tile can only do what it's set up to do.
CONFIRM_SECONDS = 6
CONFIRMS = {}           # token -> (what, expires): a second tap must come back with the token
CONFIRM_LOCK = threading.Lock()


def confirm_make(what):
    tok = uuid.uuid4().hex
    with CONFIRM_LOCK:
        now = time.time()
        for k in [k for k, v in CONFIRMS.items() if v[1] < now]:
            del CONFIRMS[k]
        CONFIRMS[tok] = (what, now + CONFIRM_SECONDS)
    return tok


def confirm_take(tok, what):
    with CONFIRM_LOCK:
        hit = CONFIRMS.pop(str(tok or ""), None)
    return bool(hit) and hit[0] == what and hit[1] >= time.time()


def saved_tile(tid):
    """The tile with this id on the saved dashboard (with its settings), or None."""
    try:
        items = json.loads(CONFIG_FILE.read_text())["modules"]["tiles"]["settings"]["items"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return next((t for t in items if isinstance(t, dict) and t.get("id") == tid), None)


TILE_ACTIONS = {}       # action name -> fn(tile, args) -> (http code, answer); each area adds its own


def tile_act(tid, body):
    if not isinstance(tid, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,48}", tid):
        return 400, {"error": "bad tile id"}
    tile = saved_tile(tid)
    if not tile:
        return 404, {"error": "that tile isn't on the saved dashboard"}
    fn = TILE_ACTIONS.get(str((body or {}).get("action") or ""))
    if not fn:
        return 400, {"error": "unknown action"}
    args = body.get("args")
    return fn(tile, args if isinstance(args, dict) else {})


# names used only inside functions: imported last, so these modules can use each other
from server.config import CONFIG_FILE  # noqa: E402
