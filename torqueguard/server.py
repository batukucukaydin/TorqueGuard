"""Loopback-only laboratory API. No dependencies, network data, or persistent user storage."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
from urllib.parse import urlparse
from .model import Scenario, PRESETS
from .validation import compare, campaign

WEB = Path(__file__).parent / "web"


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, body, content_type="application/json; charset=utf-8"):
        if not isinstance(body, bytes):
            body = json.dumps(body, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/presets":
            self.respond(200, {k: v.to_dict() for k, v in PRESETS.items()})
        elif path == "/api/health":
            self.respond(200, {"status": "ok"})
        elif path in ("/", "/app.js", "/style.css"):
            filename = "index.html" if path == "/" else path[1:]
            mime = {"index.html": "text/html", "app.js": "text/javascript", "style.css": "text/css"}[filename]
            self.respond(200, (WEB / filename).read_bytes(), mime + "; charset=utf-8")
        else:
            self.respond(404, {"error": "Not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in ("/api/replay", "/api/campaign"):
            self.respond(404, {"error": "Not found"})
            return
        # Reject cross-origin POSTs; the UI uses same-origin JSON requests.
        origin = self.headers.get("Origin")
        allowed = {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}
        if origin and origin not in allowed:
            self.respond(403, {"error": "Cross-origin requests are not accepted"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 8192:
                raise ValueError("Request body must contain 1–8192 bytes")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("Request body must be an object")
            if path == "/api/replay":
                result = compare(Scenario(**payload))
            else:
                if type(payload.get("cases", 100)) is not int or not 1 <= payload.get("cases", 100) <= 10000:
                    raise ValueError("Browser campaigns support 1–10000 cases; use CLI for larger runs")
                result = campaign(**payload)
            self.respond(200, result)
        except (ValueError, TypeError) as exc:
            self.respond(400, {"error": str(exc)})


def serve(port=8765):
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"TorqueGuard → http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
