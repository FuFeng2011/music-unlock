# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
"""音乐解锁桌面版：内嵌 WebView2 窗口加载动效界面，双击 exe 即用。
无外部浏览器依赖；Win10/11 自带 WebView2，旧系统自动回退其他引擎。"""
import http.server
import json
import os
import subprocess
import sys
import threading
import urllib.parse

import webview

ROOT = os.path.dirname(os.path.abspath(__file__))
# PyInstaller onefile 运行时资源目录
if getattr(sys, "frozen", False):
    ROOT = sys._MEIPASS
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
if getattr(sys, "frozen", False):
    OUT = os.path.join(os.path.dirname(sys.executable), "output")
os.makedirs(OUT, exist_ok=True)

sys.path.insert(0, ROOT)
import core

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
    # 随机空闲端口，避免与任何残留服务/多开实例冲突
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    url = "http://127.0.0.1:%d" % port
    try:
        webview.create_window("音乐解锁", url, width=960, height=780, min_size=(720, 620))
        webview.start()
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
