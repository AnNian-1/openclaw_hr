#!/usr/bin/env python3
"""Canvas 反代：18999 → Gateway 18790，补 Authorization，不依赖 nginx。"""
from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

GATEWAY = os.environ.get("OPENCLAW_GATEWAY_URL", "http://127.0.0.1:18790").rstrip("/")
TOKEN = os.environ.get("OPENCLAW_GATEWAY_TOKEN", "")
HOST = os.environ.get("CANVAS_PROXY_HOST", "127.0.0.1")
PORT = int(os.environ.get("CANVAS_PROXY_PORT", "18999"))


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def do_GET(self) -> None:
        self._proxy()

    def do_HEAD(self) -> None:
        self._proxy(head=True)

    def _proxy(self, head: bool = False) -> None:
        if self.path.split("?", 1)[0] == "/__openclaw__/healthz":
            body = b"canvas-proxy ok\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if not head:
                self.wfile.write(body)
            return
        if not TOKEN:
            self.send_error(500, "OPENCLAW_GATEWAY_TOKEN missing")
            return
        url = GATEWAY + self.path
        req = urllib.request.Request(url, method="GET")
        req.add_header("Authorization", "Bearer " + TOKEN)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read()
                ctype = resp.headers.get("Content-Type") or "application/octet-stream"
                self.send_response(resp.status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if not head:
                    self.wfile.write(body)
        except urllib.error.HTTPError as e:
            body = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", e.headers.get("Content-Type") or "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if not head:
                self.wfile.write(body)
        except urllib.error.URLError as e:
            msg = ("upstream: " + str(e.reason)).encode()
            self.send_response(502)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            if not head:
                self.wfile.write(msg)


def main() -> int:
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"canvas-proxy listening on http://{HOST}:{PORT}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
