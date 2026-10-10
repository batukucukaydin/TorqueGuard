import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from torqueguard.server import Handler


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def post(self, path, data, origin=None):
        headers = {"Content-Type":"application/json"}
        if origin:
            headers["Origin"] = origin
        return urlopen(Request(self.base + path, json.dumps(data).encode(), headers), timeout=15)

    def test_assets_and_replay(self):
        for path in ("/", "/style.css", "/app.js", "/api/health"):
            with urlopen(self.base + path) as response:
                self.assertEqual(response.status, 200)
        with self.post("/api/replay", {}) as response:
            result = json.load(response)
            self.assertFalse(result["runs"]["faulty"]["passed"])
            self.assertTrue(result["runs"]["corrected"]["passed"])

    def test_bad_payloads_have_stable_error_response(self):
        for path, data in (("/api/replay", {"soc":2}), ("/api/replay", []),
                           ("/api/replay", {"soc":None}), ("/api/campaign", {"cases":10001})):
            with self.assertRaises(HTTPError) as caught:
                self.post(path, data)
            self.assertEqual(caught.exception.code, 400)
            self.assertIn("error", json.load(caught.exception))

    def test_cross_origin_and_unknown_paths(self):
        with self.assertRaises(HTTPError) as caught:
            self.post("/api/replay", {}, "https://example.com")
        self.assertEqual(caught.exception.code, 403)
        with self.assertRaises(HTTPError) as caught:
            urlopen(self.base + "/../model.py")
        self.assertEqual(caught.exception.code, 404)
