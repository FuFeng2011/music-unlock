# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
"""音乐解锁 GUI：本地 HTTP 服务 + 动效网页界面。浏览器打开 http://127.0.0.1:7867"""
import http.server
import json
import os
import subprocess
import sys
import threading
import urllib.parse
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "output")
os.makedirs(OUT, exist_ok=True)
PORT = 7867

state = {"total": 0, "done": 0, "ok": 0, "fail": 0, "items": []}
lock = threading.Lock()


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = urllib.parse.urlparse(self.path)
        if p.path in ("/", "/index.html"):
            html = open(os.path.join(ROOT, "web", "index.html"), "rb").read()
            self._send(200, html, "text/html; charset=utf-8")
            return
        if p.path == "/api/status":
            with lock:
                self._send(200, json.dumps(state, ensure_ascii=False))
            return
        if p.path == "/api/open":
            subprocess.Popen(["explorer", OUT])
            self._send(200, "{}")
            return
        self._send(404, "{}")

    def do_PUT(self):
        p = urllib.parse.urlparse(self.path)
        if p.path != "/api/convert":
            self._send(404, "{}")
            return
        q = urllib.parse.parse_qs(p.query)
        name = (q.get("name") or ["unknown.bin"])[0]
        length = int(self.headers.get("Content-Length") or 0)
        data = self.rfile.read(length)
        with lock:
            state["total"] += 1
            state["items"].append({"name": name, "status": "working"})
            idx = len(state["items"]) - 1
        try:
            r = core.convert_bytes(data, name, OUT)
            with lock:
                item = {"name": name, "status": "ok", **r}
                state["items"][idx] = item
                state["done"] += 1
                state["ok"] += 1
            self._send(200, json.dumps(item, ensure_ascii=False))
        except Exception as e:
            with lock:
                item = {"name": name, "status": "error", "error": str(e)}
                state["items"][idx] = item
                state["done"] += 1
                state["fail"] += 1
            self._send(200, json.dumps(item, ensure_ascii=False))


def main():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = "http://127.0.0.1:%d" % PORT
    print("音乐解锁已启动: " + url + "  (输出目录: " + OUT + ")")
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
