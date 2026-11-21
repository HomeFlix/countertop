"""Immich photo albums: talks to a stand-in Immich, serves only the album's photos, and keeps the API key on the server.

Run with: python3 tests/test_immich.py
"""

import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen
import zipfile

ROOT = Path(__file__).resolve().parent.parent
KEY = "immich-test-key-5f2c9a7e1b"
ALBUMS = [{"id": "alb1", "albumName": "Kitchen"}, {"id": "alb2", "albumName": "Private"}]
ASSETS = {
    "alb1": [{"id": "a1", "type": "IMAGE", "exifInfo": {"description": "Beach", "dateTimeOriginal": "2026-07-04T10:00:00Z",
                                                        "exifImageWidth": 4000, "exifImageHeight": 3000}},
             {"id": "a2", "type": "VIDEO", "exifInfo": {}},
             {"id": "a3", "type": "IMAGE", "exifInfo": {}}],
    "alb2": [{"id": "p1", "type": "IMAGE", "exifInfo": {}}],
}
STATE = {"v3": False, "seen_keys": set()}
JPEG = b"\xff\xd8\xff\xe0fake-jpeg"


class FakeImmich(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        body = json.dumps(body).encode() if not isinstance(body, bytes) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        STATE["seen_keys"].add(self.headers.get("x-api-key"))
        if self.headers.get("x-api-key") != KEY:
            return self._send(401, {"message": "Invalid API key"})
        u = urlparse(self.path)
        q = parse_qs(u.query)
        parts = u.path.strip("/").split("/")
        if u.path == "/api/albums":
            return self._send(200, ALBUMS)
        if len(parts) == 4 and parts[:2] == ["api", "albums"] and parts[3] == "assets":
            if STATE["v3"]:
                return self._send(404, {"message": "Not found"})
            return self._send(200, ASSETS.get(parts[2], []))
        if u.path == "/api/timeline/buckets":
            return self._send(200, [{"timeBucket": "2026-07-01", "count": 3}])
        if u.path == "/api/timeline/bucket":
            A = ASSETS.get(q["albumId"][0], [])
            return self._send(200, {"id": [a["id"] for a in A], "isImage": [a["type"] == "IMAGE" for a in A],
                                    "fileCreatedAt": ["2026-07-04T10:00:00Z"] * len(A)})
        if len(parts) == 4 and parts[:2] == ["api", "assets"] and parts[3] == "thumbnail":
            return self._send(200, JPEG + parts[2].encode(), "image/jpeg")
        self._send(404, {"message": "Not found"})

    def log_message(self, *a):
        pass


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class ImmichTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.im = ThreadingHTTPServer(("127.0.0.1", 0), FakeImmich)
        threading.Thread(target=cls.im.serve_forever, daemon=True).start()
        cls.im_url = "http://127.0.0.1:%d" % cls.im.server_address[1]
        cls.tmp = TemporaryDirectory()
        port = free_port()
        cls.base = "http://127.0.0.1:%d" % port
        env = dict(os.environ, COUNTERTOP_DATA=cls.tmp.name, COUNTERTOP_NO_UPDATE_CHECK="1")
        cls.proc = subprocess.Popen([sys.executable, str(ROOT / "tools" / "countertop.py"), "--port", str(port)], env=env,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        for _ in range(100):
            try:
                urlopen(cls.base + "/version", timeout=1)
                break
            except Exception:
                time.sleep(0.1)
        else:
            raise RuntimeError("server didn't start")

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        out = cls.proc.communicate(timeout=10)[0]
        cls.im.shutdown()
        cls.tmp.cleanup()
        assert KEY.encode() not in out, "the API key was printed to the console"

    def req(self, path, payload=None):
        r = Request(self.base + path, data=json.dumps(payload).encode() if payload is not None else None,
                    headers={"Content-Type": "application/json"})
        try:
            with urlopen(r, timeout=10) as resp:
                return resp.status, resp.read(), resp.headers.get("Content-Type")
        except HTTPError as e:
            return e.code, e.read(), e.headers.get("Content-Type")

    def json(self, path, payload=None):
        code, raw, _ = self.req(path, payload)
        return code, json.loads(raw)

    def add_album(self, name, album):
        _, j = self.json("/sources", {"kind": "albums", "op": "add",
                                      "item": {"name": name, "kind": "Immich", "server": self.im_url, "apiKey": KEY, "album": album}})
        return [a for a in j["sources"]["albums"] if a["name"] == name][0]

    def test_1_album_and_proxy(self):
        src = self.add_album("Kitchen photos", "kitchen")          # album names match regardless of case
        self.assertNotIn("apiKey", src)
        _, j = self.json("/photos?id=" + src["id"])
        self.assertIsNone(j["error"])
        urls = [p["url"] for p in j["photos"]]
        self.assertEqual(urls, ["/photos/immich/%s/a1.jpg" % src["id"], "/photos/immich/%s/a3.jpg" % src["id"]])   # no videos
        self.assertEqual(j["photos"][0]["caption"], "Beach")
        self.assertEqual((j["photos"][0]["w"], j["photos"][0]["h"]), (4000, 3000))

        # the screen gets the photo through this server
        code, raw, ctype = self.req(urls[0])
        self.assertEqual((code, ctype), (200, "image/jpeg"))
        self.assertEqual(raw, JPEG + b"a1")
        # but nothing outside the album: not a video in it, not a photo from another album, not a made-up id
        for asset in ("a2", "p1", "nope"):
            code, _, _ = self.req("/photos/immich/%s/%s.jpg" % (src["id"], asset))
            self.assertEqual(code, 404, asset)
        code, _, _ = self.req("/photos/immich/no-such-album/a1.jpg")
        self.assertEqual(code, 404)

    def test_2_timeline_api(self):
        STATE["v3"] = True
        try:
            src = self.add_album("Timeline", "Kitchen")
            _, j = self.json("/photos?id=" + src["id"])
            self.assertIsNone(j["error"])
            self.assertEqual([p["url"].rsplit("/", 1)[-1] for p in j["photos"]], ["a1.jpg", "a3.jpg"])
        finally:
            STATE["v3"] = False

    def test_3_errors(self):
        _, j = self.json("/sources", {"kind": "albums", "op": "add",
                                      "item": {"name": "Wrong key", "kind": "Immich", "server": self.im_url, "apiKey": "nope", "album": "Kitchen"}})
        src = [a for a in j["sources"]["albums"] if a["name"] == "Wrong key"][0]
        _, j = self.json("/photos?id=" + src["id"])
        self.assertEqual(j["photos"], [])
        self.assertTrue(j["error"])
        src = self.add_album("Missing", "Holidays")
        _, j = self.json("/photos?id=" + src["id"])
        self.assertIn("Holidays", j["error"])

    def test_4_key_stays_on_server(self):
        self.add_album("Key check", "Kitchen")
        for path in ("/config", "/sources", "/status", "/photos"):
            _, raw, _ = self.req(path)
            self.assertNotIn(KEY.encode(), raw, path)
        _, raw, _ = self.req("/diagnostics")
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            blob = b"".join(z.read(n) for n in z.namelist())
        self.assertNotIn(KEY.encode(), blob)


if __name__ == "__main__":
    unittest.main(verbosity=2)
