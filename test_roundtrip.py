# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
"""往返测试：用解密变换的数学逆函数构造加密样本，再解密比对。"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core
from core import (CORE_KEY, KGM_MAGIC, KGM_SIGNATURE, SLOT_KEY, VPR_MAGIC,
                  VPR_SIGNATURE, _md5_swapped)
from Crypto.Cipher import AES

def h(x):  # x ^ (x<<4) 自反变换（8位）
    return (x ^ ((x << 4) & 0xFF)) & 0xFF

def t2_enc(data):
    out = bytearray(len(data))
    for i in range(len(data)):
        y = data[i] ^ SLOT_KEY[i % len(SLOT_KEY)]
        out[i] = y ^ ((y << 4) & 0xFF)
    return bytes(out)

def t3_enc(data, file_key16):
    slot = _md5_swapped(SLOT_KEY)
    fk = _md5_swapped(file_key16) + b"\x6b"
    out = bytearray(len(data))
    for i in range(len(data)):
        j = i
        m = (j ^ (j >> 8) ^ (j >> 16) ^ (j >> 24)) & 0xFF
        y = data[i] ^ slot[j % 16] ^ m
        x = y ^ ((y << 4) & 0xFF)
        out[i] = x ^ fk[j % 17]
    return bytes(out)

def ncm_enc(audio, file_key):
    def pad(s):
        return s + bytes([16 - len(s) % 16] * (16 - len(s) % 16))
    keychunk = AES.new(CORE_KEY, AES.MODE_ECB).encrypt(pad(b"neteasecloudmusic" + file_key))
    keychunk = bytes(b ^ 0x64 for b in keychunk)
    head = b"CTENFDAM" + b"\x0a\x0a"
    head += struct.pack("<I", len(keychunk)) + keychunk
    head += struct.pack("<I", 0)          # meta 长度 0
    head += struct.pack("<I", 0)          # crc32 占位
    head += b"\x00" * 5 + struct.pack("<I", 0)  # 无封面
    box = bytearray(range(256))
    key = file_key
    c = 0; last = 0; ki = 0
    for i in range(256):
        swap = box[i]
        c = (swap + last + key[ki % len(key)]) & 0xFF
        ki += 1
        box[i] = box[c]; box[c] = swap; last = c
    mask = bytearray(256)
    for i in range(256):
        j = (i + 1) & 0xFF
        mask[i] = box[(box[j] + box[(box[j] + j) & 0xFF]) & 0xFF]
    enc = bytearray(len(audio))
    for i in range(len(audio)):
        enc[i] = audio[i] ^ mask[(i + 1) & 0xFF]
    return head + bytes(enc)

def legacy_enc(audio, key17):
    header_len = 0x50
    head = bytearray(header_len)
    struct.pack_into("<I", head, 16, header_len)
    head[28:45] = key17
    out = bytearray(len(audio))
    t1, t2, pre = core.TABLE1, core.TABLE2, core.MASK_V2_PREDEF
    for i in range(len(audio)):
        msk8 = 0
        offset = i >> 4
        while offset >= 0x11:
            msk8 ^= t1[offset % 272]
            offset >>= 4
            msk8 ^= t2[offset % 272]
            offset >>= 4
        msk8 = (pre[i % 272] ^ msk8) & 0xFF
        msk8 = (msk8 ^ ((msk8 & 0x0F) << 4)) & 0xFF
        out[i] = h(audio[i] ^ msk8) ^ key17[i % 17]
    return bytes(head) + bytes(out)

fails = 0
def check(name, cond):
    global fails
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails += 1

def run():
    rnd = os.urandom
    audio_flac = b"fLaC" + rnd(100000)
    audio_mp3 = b"ID3" + rnd(80000)
    fk4 = b"\x01\x02\x03\x04"
    fk16 = rnd(16)

    # NCM
    enc = ncm_enc(audio_flac, fk4)
    a, ext, meta, cover = core.ncm_decrypt(enc)
    check("ncm/flac roundtrip", a == audio_flac and ext == "flac")
    enc = ncm_enc(audio_mp3, fk4)
    a, ext, _, _ = core.ncm_decrypt(enc)
    check("ncm/mp3 roundtrip", a == audio_mp3 and ext == "mp3")

    # KGM 新格式 v2 (.kgm 新头部)
    def kgm_new_header(magic, sig_const, enc_type, file_key, audio):
        off = 0x40
        head = bytearray(off)
        head[:16] = magic
        struct.pack_into("<I", head, 0x10, off)
        struct.pack_into("<I", head, 0x14, enc_type)
        struct.pack_into("<I", head, 0x18, 1)
        if enc_type == 2:
            head[0x1C:0x2C] = t2_enc(sig_const)
            body = t2_enc(audio)
        else:
            head[0x1C:0x2C] = t3_enc(sig_const, file_key)
            body = t3_enc(audio, file_key)
        head[0x2C:0x3C] = file_key
        return bytes(head) + body

    enc = kgm_new_header(KGM_MAGIC, KGM_SIGNATURE, 2, fk16, audio_flac)
    a, ext = core.kgm_new_decrypt(enc)
    check("kgm v2/flac roundtrip", a == audio_flac and ext == "flac")

    enc = kgm_new_header(KGM_MAGIC, KGM_SIGNATURE, 3, fk16, audio_flac)
    a, ext = core.kgm_new_decrypt(enc)
    check("kgm v3(kgma)/flac roundtrip", a == audio_flac and ext == "flac")

    enc = kgm_new_header(KGM_MAGIC, KGM_SIGNATURE, 3, fk16, audio_mp3)
    a, ext = core.kgm_new_decrypt(enc)
    check("kgm v3(kgma)/mp3 roundtrip", a == audio_mp3 and ext == "mp3")

    enc = kgm_new_header(VPR_MAGIC, VPR_SIGNATURE, 3, fk16, audio_flac)
    a, ext = core.kgm_new_decrypt(enc)
    check("vpr v3 roundtrip", a == audio_flac and ext == "flac")

    # 旧版 kgm
    key17 = rnd(17)
    enc = legacy_enc(audio_flac, key17)
    a, ext = core.kgm_legacy_decrypt(enc)
    check("kgm legacy roundtrip", a == audio_flac and ext == "flac")

    # 识别
    check("detect ncm", core.detect(ncm_enc(audio_mp3, fk4)) == "ncm")
    check("detect kgm_new", core.detect(kgm_new_header(KGM_MAGIC, KGM_SIGNATURE, 3, fk16, audio_mp3)) == "kgm_new")

    print("----")
    print("ALL PASS" if fails == 0 else ("%d FAILURES" % fails))
    sys.exit(1 if fails else 0)

if __name__ == "__main__":
    run()
