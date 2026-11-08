#!/usr/bin/env python3
"""Serve the marketing site with a strict CSP. --api proxies /api and /identity."""
import argparse
import http.server
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
API = None
HOP = {
    "content-type", "accept", "authorization", "device-type",
    "bitwarden-client-name", "bitwarden-client-version",
}


def policy():
    path = ROOT / "csp.txt"
    base = path.read_text().strip() if path.is_file() else (
        "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self'; "
        "img-src 'self'; font-src 'self'; connect-src 'self'; form-action 'self'; "
        "base-uri 'self'; object-src 'none'"
    )
    if "frame-ancestors" not in base:
        base += "; frame-ancestors 'none'"
    return base


def proxied(path):
    return path.startswith("/api/") or path.startswith("/identity/") or path in ("/api", "/identity", "/alive")


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header("Content-Security-Policy", policy())
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("X-Frame-Options", "DENY")
        super().end_headers()

    def log_message(self, fmt, *args):
        # Path only. Request bodies are never written here.
        super().log_message("%s", args[0] if args else fmt)

    def do_GET(self):
        if API and proxied(self.path.split("?", 1)[0]):
            self._proxy("GET")
            return
        super().do_GET()

    def do_POST(self):
        if API and proxied(self.path.split("?", 1)[0]):
            self._proxy("POST")
            return
        self._drop(405)

    def do_PUT(self):
        if API and proxied(self.path.split("?", 1)[0]):
            self._proxy("PUT")
            return
        self._drop(405)

    def _drop(self, status):
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        self.send_error(status)

    def _proxy(self, method):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        headers = {k: v for k, v in self.headers.items() if k.lower() in HOP}
        request = urllib.request.Request(API + self.path, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request) as response:
                payload = response.read()
                status = response.status
                ctype = response.headers.get("Content-Type")
        except urllib.error.HTTPError as error:
            payload = error.read()
            status = error.code
            ctype = error.headers.get("Content-Type")
        self.send_response(status)
        if ctype:
            self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main():
    global API
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4173)
    parser.add_argument("--api", default="")
    args = parser.parse_args()
    API = args.api.rstrip("/") or None
    http.server.ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
