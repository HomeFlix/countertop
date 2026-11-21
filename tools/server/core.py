"""Paths, shared state and small helpers every part of the server uses."""
import collections
import json
import os
import re
import socket
import threading
import time
from pathlib import Path
from urllib.request import Request, urlopen


VERSION = re.search(r'^VERSION = "([^"]+)"', (Path(__file__).resolve().parent.parent / "countertop.py").read_text(), re.M).group(1)      # the one place it is set is tools/countertop.py
REPO = "kizit/countertop"
HERE = Path(__file__).resolve().parent.parent      # tools/
# Everything the server saves lives here: tools/../work by default, or COUNTERTOP_DATA (the Mac app keeps it in
# ~/Library/Application Support/Countertop, since the app itself is read-only).
WORK = Path(os.environ.get("COUNTERTOP_DATA") or HERE.parent / "work").expanduser()
LOG = WORK / "heartbeat.log"
OLD_LOG = WORK / "silk_collect.log"     # name used before the rename; moved over once at startup
NOTES = WORK / "notes.json"
NOTES_LOCK = threading.Lock()

ICS_CACHE = {}           # url -> (ts, [events])
LOG_LOCK = threading.Lock()
CAL_STATUS = {}          # calendar id -> {name, at, ok, error, count}: the last time each calendar was fetched
SCREEN = {"beat": None, "at": 0, "errors": collections.deque(maxlen=200)}   # last heartbeat from a screen, recent page errors
CONSOLE = collections.deque(maxlen=800)      # recent console output (also what `docker logs` shows), for diagnostics


class _Tee:
    """Keep printing as before, and keep the last lines in memory so Controls can include them in a diagnostics file."""
    def __init__(self, real):
        self.real, self.buf = real, ""

    def write(self, s):
        try:
            self.real.write(s)
        except Exception:
            pass
        self.buf += s
        while "\n" in self.buf:
            line, self.buf = self.buf.split("\n", 1)
            CONSOLE.append(time.strftime("%Y-%m-%d %H:%M:%S ") + line)
        return len(s)

    def flush(self):
        try:
            self.real.flush()
        except Exception:
            pass

    def __getattr__(self, k):
        return getattr(self.real, k)


def lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def log_entry(e):
    """Append one report (heartbeat, page error, frame refresh...) to work/heartbeat.log as a JSON line."""
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG_LOCK, LOG.open("a") as f:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")
    if e.get("task") != "beat":          # heartbeats every minute would drown the console
        print("%s %s from %s: %s" % (e.get("t"), e.get("task"), e.get("client"),
                                     str(e.get("error") or e.get("result") or "")[:300]), flush=True)


def _get_json(url, data=None, timeout=15):
    hdr = {"User-Agent": "Mozilla/5.0 kitchen-dashboard", "Accept": "application/json"}
    if data is not None:
        hdr["Content-Type"] = "text/plain"
    req = Request(url, data=json.dumps(data).encode() if data is not None else None, headers=hdr)
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read(4_000_000).decode("utf-8", "replace"))
