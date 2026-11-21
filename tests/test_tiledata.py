"""Tile data: every tile keeps its own store, changes are applied one operation at a time, removed tiles' data goes to
the trash and comes back with the tile, and tiles that aren't saved can't write.

Run with: python3 tests/test_tiledata.py
"""

import importlib.util
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
TMP = TemporaryDirectory()
os.environ["COUNTERTOP_DATA"] = TMP.name
spec = importlib.util.spec_from_file_location("countertop", ROOT / "tools" / "countertop.py")
ct = importlib.util.module_from_spec(spec)
sys.argv = ["countertop.py"]
spec.loader.exec_module(ct)
td = ct.tiledata


def save_tiles(*tiles):
    mods = json.loads(json.dumps(ct.config_load()["modules"]))
    mods["tiles"]["settings"]["items"] = [{"id": i, "type": t, "settings": {}} for i, t in tiles]
    ct.config_save({"modules": mods}, quiet=True)


class TileDataTest(unittest.TestCase):
    def setUp(self):
        import shutil
        td.init(ct.WORK, ct.BACKUP_DIR)          # other test files load the server too, with their own data folder
        shutil.rmtree(td.STATE["dir"], ignore_errors=True)
        td.STATE["revs"].clear()
        save_tiles(("daily_a", "daily"), ("daily_b", "daily"), ("note_1", "note"))

    def test_each_tile_has_its_own_store(self):
        td.apply("daily_a", {"op": "push", "key": "items", "item": {"text": "Walk the dog"}}, ct.live_tiles())
        self.assertEqual([i["text"] for i in td.get("daily_a")["items"]], ["Walk the dog"])
        self.assertEqual(td.get("daily_b"), {})                  # a second tile of the same kind starts empty
        self.assertFalse((Path(TMP.name) / "notes.json").exists())   # and nothing touches the lists' file

    def test_operations(self):
        live = ct.live_tiles()
        out = td.apply("daily_b", {"ops": [
            {"op": "push", "key": "items", "item": {"id": "x1", "text": "One", "done": False}},
            {"op": "push", "key": "items", "item": {"id": "x1", "text": "Two", "done": False}},   # duplicate id: gets a new one
            {"op": "set", "key": "day", "value": "2026-11-21"}]}, live)
        items = out["data"]["items"]
        self.assertEqual(items[0]["id"], "x1")
        self.assertNotEqual(items[1]["id"], "x1")
        td.apply("daily_b", {"op": "update", "key": "items", "id": "x1", "fields": {"done": True, "id": "hijack"}}, live)
        self.assertEqual(td.get("daily_b")["items"][0], {"id": "x1", "text": "One", "done": True})
        td.apply("daily_b", {"op": "updateAll", "key": "items", "fields": {"done": True}}, live)
        td.apply("daily_b", {"op": "removeWhere", "key": "items", "fields": {"done": True}}, live)
        self.assertEqual(td.get("daily_b")["items"], [])
        td.apply("daily_b", {"op": "set", "key": "day", "value": None}, live)
        self.assertNotIn("day", td.get("daily_b"))

    def test_all_or_nothing_and_unless(self):
        live = ct.live_tiles()
        td.apply("note_1", {"op": "set", "key": "n", "value": 1}, live)
        with self.assertRaises(td.TileDataError):
            td.apply("note_1", {"ops": [{"op": "set", "key": "n", "value": 2}, {"op": "explode", "key": "n"}]}, live)
        self.assertEqual(td.get("note_1")["n"], 1)
        first = td.apply("note_1", {"ops": [{"op": "set", "key": "day", "value": "d1"}], "unless": {"day": "d1"}}, live)
        again = td.apply("note_1", {"ops": [{"op": "set", "key": "n", "value": 99}], "unless": {"day": "d1"}}, live)
        self.assertTrue(again.get("skipped"))
        self.assertEqual(td.get("note_1")["n"], 1)
        self.assertEqual(again["rev"], first["rev"])

    def test_refuses_bad_input(self):
        live = ct.live_tiles()
        for tid, body in [("../etc", {"op": "set", "key": "a", "value": 1}),
                          ("daily_a", {"op": "set", "key": "__proto__", "value": 1}),
                          ("daily_a", {"op": "set", "key": "a", "value": float("nan")}),
                          ("daily_a", {"op": "push", "key": "a", "item": "not an object"}),
                          ("daily_a", {"ops": []})]:
            with self.assertRaises(td.TileDataError):
                td.apply(tid, body, live)
        with self.assertRaises(td.TileDataError) as e:
            td.apply("preview_tile", {"op": "set", "key": "a", "value": 1}, live)   # not on the saved dashboard
        self.assertEqual(e.exception.code, 404)
        with self.assertRaises(td.TileDataError) as e:
            td.apply("daily_a", {"op": "set", "key": "big", "value": "x" * (td.MAX_BYTES + 1)}, live)
        self.assertEqual(e.exception.code, 413)

    def test_changed_since(self):
        live = ct.live_tiles()
        start = td.changed(0, live)["rev"]
        td.apply("daily_a", {"op": "set", "key": "k", "value": "v"}, live)
        out = td.changed(start, live)
        self.assertEqual(list(out["tiles"]), ["daily_a"])
        self.assertEqual(td.changed(out["rev"], live)["tiles"], {})

    def test_removed_tile_goes_to_trash_and_comes_back(self):
        td.apply("daily_a", {"op": "set", "key": "keep", "value": "me"}, ct.live_tiles())
        save_tiles(("daily_b", "daily"))                         # daily_a removed
        self.assertFalse((td.STATE["dir"] / "daily_a.json").exists())
        self.assertNotIn("daily_a", td.changed(0, ct.live_tiles())["tiles"])
        save_tiles(("daily_a", "daily"), ("daily_b", "daily"))    # undo
        self.assertEqual(td.get("daily_a"), {"keep": "me"})
        save_tiles(("daily_b", "daily"))
        later = ct.time.time() + (td.TRASH_DAYS + 1) * 86400
        with mock.patch.object(td.time, "time", return_value=later):
            save_tiles(("daily_b", "daily"))
        self.assertEqual(list((td.STATE["dir"] / ".trash").glob("daily_a~*.json")), [])

    def test_backup(self):
        td.apply("daily_a", {"op": "set", "key": "b", "value": 1}, ct.live_tiles())
        with td.LOCK:
            td._backup_locked(force=True)
        files = sorted(ct.BACKUP_DIR.glob("tiledata-*.json"))
        self.assertTrue(files)
        self.assertEqual(json.loads(files[-1].read_text())["daily_a"]["data"]["b"], 1)

    def test_http(self):
        import http.client
        import threading
        srv = ct.ThreadingHTTPServer(("127.0.0.1", 0), ct.Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            port = srv.server_address[1]
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            c.request("POST", "/tile-data/daily_a", json.dumps({"op": "set", "key": "h", "value": 2}), {"Content-Type": "application/json"})
            r = c.getresponse()
            self.assertEqual(r.status, 200)
            self.assertEqual(json.loads(r.read())["data"]["h"], 2)
            c.request("POST", "/tile-data/daily_a", json.dumps({"op": "set", "key": "h", "value": 3}), {"Origin": "null"})
            self.assertEqual(c.getresponse().status, 403)                        # a sandboxed frame can't write
            c.request("GET", "/tile-data?since=0")
            self.assertEqual(json.loads(c.getresponse().read())["tiles"]["daily_a"]["h"], 2)
            c.request("POST", "/tile-data/nope", json.dumps({"op": "set", "key": "h", "value": 2}))
            self.assertEqual(c.getresponse().status, 404)
        finally:
            c.close()
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    unittest.main()
