# -*- coding: utf-8 -*-
"""生成合成加密样本，用于端到端验证。"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_roundtrip as T

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

outdir = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("TEMP", ".")

# 假 FLAC（真实 fLaC 魔数 + 伪数据）
audio = b"fLaC" + bytes(range(256)) * 400 + b"END"

ncm = T.ncm_enc(audio, b"\x01\x02\x03\x04")
open(os.path.join(outdir, "sample_测试歌曲.ncm"), "wb").write(ncm)

kgma = kgm_new_header(T.KGM_MAGIC, T.KGM_SIGNATURE, 3, bytes(range(16)), audio)
open(os.path.join(outdir, "sample_酷狗新歌.kgma"), "wb").write(kgma)

legacy = T.legacy_enc(audio, bytes(range(17)))
open(os.path.join(outdir, "sample_酷狗老歌.kgm"), "wb").write(legacy)

vpr = kgm_new_header(T.VPR_MAGIC, T.VPR_SIGNATURE, 3, bytes(range(16)), audio)
open(os.path.join(outdir, "sample_纯享.vpr"), "wb").write(vpr)

open(os.path.join(outdir, "sample_origin.flac"), "wb").write(audio)
print("samples written to", outdir)
