# -*- coding: utf-8 -*-
"""批量测试样本生成：12 个不同格式、不同内容的加密文件 + 原始音频对照。"""
import base64
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core
import test_roundtrip as T
from Crypto.Cipher import AES

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "batch_test")
os.makedirs(OUT, exist_ok=True)


def kgm_new_header(magic, sig_const, enc_type, file_key, audio):
    off = 0x40
    head = bytearray(off)
    head[:16] = magic
    struct.pack_into("<I", head, 0x10, off)
    struct.pack_into("<I", head, 0x14, enc_type)
    struct.pack_into("<I", head, 0x18, 1)
    if enc_type == 2:
        head[0x1C:0x2C] = T.t2_enc(sig_const)
        body = T.t2_enc(audio)
    else:
        head[0x1C:0x2C] = T.t3_enc(sig_const, file_key)
        body = T.t3_enc(audio, file_key)
    head[0x2C:0x3C] = file_key
    return bytes(head) + body


def ncm_with_meta(audio, file_key, title, artist):
    def pad(s):
        return s + bytes([16 - len(s) % 16] * (16 - len(s) % 16))

    keychunk = AES.new(core.CORE_KEY, AES.MODE_ECB).encrypt(pad(b"neteasecloudmusic" + file_key))
    keychunk = bytes(b ^ 0x64 for b in keychunk)
    meta_json = json.dumps({"musicName": title, "artist": [[artist, 0]], "album": "test"}, ensure_ascii=False)
    b64 = base64.b64encode(("music:" + meta_json).encode("utf-8"))
    meta_chunk = bytearray(core.META_MARKER + b64)
    for i in range(len(meta_chunk)):
        meta_chunk[i] ^= 0x63
    head = b"CTENFDAM" + b"\x0a\x0a"
    head += struct.pack("<I", len(keychunk)) + keychunk
    head += struct.pack("<I", len(meta_chunk)) + bytes(meta_chunk)
    head += struct.pack("<I", 0) + b"\x00" * 5 + struct.pack("<I", 0)
    key = file_key
    box = bytearray(range(256))
    c = 0
    last = 0
    ki = 0
    for i in range(256):
        swap = box[i]
        c = (swap + last + key[ki % len(key)]) & 0xFF
        ki += 1
        box[i] = box[c]
        box[c] = swap
        last = c
    mask = bytearray(256)
    for i in range(256):
        j = (i + 1) & 0xFF
        mask[i] = box[(box[j] + box[(box[j] + j) & 0xFF]) & 0xFF]
    enc = bytearray(len(audio))
    for i in range(len(audio)):
        enc[i] = audio[i] ^ mask[(i + 1) & 0xFF]
    return head + bytes(enc)


for i in range(12):
    audio = b"fLaC" + bytes([i]) * 5000 + ("SONG%d" % i).encode()
    if i in (0, 1, 2):
        f = "ncm_song%d.ncm" % i
        open(os.path.join(OUT, f), "wb").write(ncm_with_meta(audio, bytes([1 + i]) * 4, "NCM曲目%d" % i, "歌手甲"))
    elif i in (3, 4, 5):
        f = "kgma_song%d.kgma" % i
        open(os.path.join(OUT, f), "wb").write(kgm_new_header(core.KGM_MAGIC, core.KGM_SIGNATURE, 3, bytes(range(16)), audio))
    elif i in (6, 7):
        f = "kgm_song%d.kgm" % i
        open(os.path.join(OUT, f), "wb").write(kgm_new_header(core.KGM_MAGIC, core.KGM_SIGNATURE, 2, bytes(range(16)), audio))
    elif i in (8, 9):
        f = "vpr_song%d.vpr" % i
        open(os.path.join(OUT, f), "wb").write(kgm_new_header(core.VPR_MAGIC, core.VPR_SIGNATURE, 3, bytes(range(16)), audio))
    else:
        f = "legacy_song%d.kgm" % i
        open(os.path.join(OUT, f), "wb").write(T.legacy_enc(audio, bytes(range(17))))
    open(os.path.join(OUT, "orig_%d.bin" % i), "wb").write(audio)

print("generated 12 encrypted + 12 originals in", OUT)
