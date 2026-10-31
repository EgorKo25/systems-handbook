"""A tiny, dependency-free service used only by the Git laboratory."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlsplit

VERSION = "1.0"


def greet(name="reader"):
    name = name.strip()
    if not name:
        raise ValueError("name must not be empty")
    return f"Hello, {name}!"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlsplit(self.path)
        status = 200
        if path.path == "/health":
            data = {"status": "ok", "version": VERSION}
        elif path.path == "/hello":
            try:
                data = {"message": greet(parse_qs(path.query).get("name", ["reader"])[0])}
            except ValueError as exc:
                status, data = 400, {"error": str(exc)}
        else:
            status, data = 404, {"error": "unknown path"}
        body = json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true", help="start a loopback-only HTTP server")
    parser.add_argument("--port", type=int, default=8087)
    args = parser.parse_args()
    if args.serve:
        HTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
    else:
        print(greet())


if __name__ == "__main__":
    main()
