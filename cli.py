# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
"""音乐解锁 CLI：python cli.py convert <files...> --output-dir DIR --json
               python cli.py capabilities --json"""
import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core

SUPPORTED = {
    "ncm": "网易云音乐 (NCM)",
    "kgm": "酷狗音乐 (KGM 新旧格式)",
    "kgma": "酷狗音乐 (KGMA 新格式)",
    "vpr": "酷狗音乐 (VPR)",
}
SUPPORTED_EXTS = (".ncm", ".kgm", ".kgma", ".vpr")


def expand_files(args):
    """把通配符和目录展开成受支持的文件列表。"""
    out = []
    for a in args:
        if os.path.isdir(a):
            for f in sorted(os.listdir(a)):
                if f.lower().endswith(SUPPORTED_EXTS):
                    out.append(os.path.join(a, f))
        elif any(ch in a for ch in "*?["):
            out.extend(glob.glob(a))
        else:
            out.append(a)
    return out


def main():
    ap = argparse.ArgumentParser(prog="music-unlock")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("convert", help="解密并转换为 flac/mp3")
    c.add_argument("files", nargs="+")
    c.add_argument("--output-dir", default=None, help="输出目录（默认 D:\\Tool-MusicUnlock\\output）")
    c.add_argument("--json", action="store_true")
    sub.add_parser("capabilities", help="查看支持的格式")
    a = ap.parse_args()

    if a.cmd == "capabilities":
        out = {"input_formats": SUPPORTED, "output_formats": ["flac", "mp3"], "engine": "pure-python+aes"}
        if a.json if hasattr(a, "json") else True:
            print(json.dumps(out, ensure_ascii=False))
        return

    outdir = a.output_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    os.makedirs(outdir, exist_ok=True)
    files = expand_files(a.files)
    results = []
    for f in files:
        if not f.lower().endswith(SUPPORTED_EXTS):
            results.append({"file": f, "status": "error", "error": "不支持的文件类型"})
            continue
        try:
            data = open(f, "rb").read()
            r = core.convert_bytes(data, f, outdir)
            results.append({"file": f, "status": "ok", **r})
        except Exception as e:
            results.append({"file": f, "status": "error", "error": str(e)})
    if a.json:
        print(json.dumps({"outputs": results}, ensure_ascii=False))
    else:
        for r in results:
            if r["status"] == "ok":
                print("OK   %s -> %s" % (os.path.basename(r["file"]), r["out"]))
            else:
                print("FAIL %s : %s" % (os.path.basename(r["file"]), r.get("error")))
    sys.exit(0 if all(r["status"] == "ok" for r in results) else 1)


if __name__ == "__main__":
    main()
