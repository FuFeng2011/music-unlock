# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Music Unlock contributors. Licensed under AGPL-3.0-or-later.
# 算法参考实现及来源见 THIRD-PARTY-NOTICES.md。
"""
音乐解锁核心库：网易云 .ncm / 酷狗 .kgm(旧) .kgm .kgma .vpr(新 v2/v3) 解密。
算法参考:
  - 酷狗新格式: davidxuang/MusicDecrypto (C#, Vendor/Kugou T2/T3Cipher)
  - 酷狗旧格式: 0x77fe/AudioDecrypt (C++, MaskV2PreDef 方案)
  - 网易云 NCM: 经典 ncmdump 布局 (CTENFDAM / AES-ECB / keybox)
仅支持解密本地已授权缓存文件，供个人格式转换使用。
"""
import base64
import hashlib
import json
import os
import struct

from Crypto.Cipher import AES

# ---------------------------------------------------------------- NCM (网易云)
NCM_MAGIC = b"CTENFDAM"
CORE_KEY = bytes.fromhex("687A4852416D736F356B496E62617857")
META_KEY = bytes.fromhex("2331346C6A6B5F215C5D2630553C2728")
META_MARKER = b"163 key(Don't modify):"  # 22 字节


def _unpad(s: bytes) -> bytes:
    if not s:
        return s
    return s[:-s[-1]]


def _ncm_keybox(key: bytes) -> bytes:
    """由解密出的 fileKey 构建 256 字节掩码盒。"""
    key = bytearray(key)
    box = bytearray(range(256))
    c = 0
    last = 0
    ki = 0
    kl = len(key)
    for i in range(256):
        swap = box[i]
        c = (swap + last + key[ki]) & 0xFF
        ki += 1
        if ki >= kl:
            ki = 0
        box[i] = box[c]
        box[c] = swap
        last = c
    mask = bytearray(256)
    for i in range(256):
        j = (i + 1) & 0xFF
        mask[i] = box[(box[j] + box[(box[j] + j) & 0xFF]) & 0xFF]
    return bytes(mask)


def ncm_decrypt(data: bytes):
    """返回 (音频bytes, 扩展名, meta dict, 封面bytes或None)。"""
    if data[:8] != NCM_MAGIC:
        raise ValueError("不是有效的 NCM 文件（头部魔数不符）")
    pos = 10  # 8 魔数 + 2 保留
    key_len = struct.unpack_from("<I", data, pos)[0]
    pos += 4
    key_chunk = bytearray(data[pos:pos + key_len])
    pos += key_len
    for i in range(len(key_chunk)):
        key_chunk[i] ^= 0x64
    key_data = _unpad(AES.new(CORE_KEY, AES.MODE_ECB).decrypt(bytes(key_chunk)))[17:]
    mask = _ncm_keybox(key_data)

    meta = {}
    cover = None
    try:
        meta_len = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        meta_chunk = bytearray(data[pos:pos + meta_len])
        pos += meta_len
        for i in range(len(meta_chunk)):
            meta_chunk[i] ^= 0x63
        b64 = bytes(meta_chunk).split(b":", 1)
        if len(b64) == 2:
            raw = _unpad(AES.new(META_KEY, AES.MODE_ECB).decrypt(base64.b64decode(b64[1])))
            text = raw.decode("utf-8", errors="replace")
            if text.startswith("music:"):
                text = text[6:]
            try:
                meta = json.loads(text)
            except Exception:
                pass
    except Exception:
        meta = {}

    # 封面区: 4 字节 CRC32 + 5 字节 + 4 字节长度 + 封面数据
    if pos + 13 <= len(data):
        try:
            _crc = struct.unpack_from("<I", data, pos)[0]
            pos += 4
            pos += 5  # 图片格式标记
            cover_len = struct.unpack_from("<I", data, pos)[0]
            pos += 4
            if 0 < cover_len <= len(data) - pos:
                cover = data[pos:pos + cover_len]
                pos += cover_len
        except Exception:
            cover = None

    audio = data[pos:]
    out = bytearray(len(audio))
    for i in range(len(audio)):
        j = (i + 1) & 0xFF
        out[i] = audio[i] ^ mask[j]
    return bytes(out), _sniff_ext(bytes(out[:16])), meta, cover


# ------------------------------------------------- KGM 新格式 (.kgm/.kgma/.vpr)
KGM_MAGIC = bytes.fromhex("7cd532eb86027f4ba8afa68e0fff9914")
VPR_MAGIC = bytes.fromhex("0528bc96e9e45a4391aabdd07af53631")
KGM_SIGNATURE = bytes.fromhex("3885ed92795ff84cb303614116a01d47")
VPR_SIGNATURE = bytes.fromhex("1d5a05340c418d429c83926cae16fe56")
SLOT_KEY = b"l,/'"  # 0x6C 0x2C 0x2F 0x27


def _md5_swapped(data: bytes) -> bytes:
    """MD5 后按 2 字节对逆序交换（T3 密钥派生）。"""
    d = bytearray(hashlib.md5(data).digest())
    for i in range(0, 8, 2):
        d[i], d[14 - i] = d[14 - i], d[i]
        d[i + 1], d[15 - i] = d[15 - i], d[i + 1]
    return bytes(d)


def _t2_decrypt(data: bytes, offset: int = 0) -> bytes:
    """老 KGM v2: v ^ (v<<4) ^ slotKey。"""
    key = SLOT_KEY
    kl = len(key)
    out = bytearray(len(data))
    for i in range(len(data)):
        v = data[i]
        v = (v ^ ((v << 4) & 0xFF)) & 0xFF
        v ^= key[(offset + i) % kl]
        out[i] = v
    return bytes(out)


def _t3_decrypt(data: bytes, file_key16: bytes, offset: int = 0) -> bytes:
    """新 KGMA v3: x = v ^ fileKey; out = x ^ (x<<4) ^ slotKey ^ 偏移掩码。"""
    slot = _md5_swapped(SLOT_KEY)          # 16 字节
    fk = _md5_swapped(file_key16) + b"\x6b"  # 17 字节
    out = bytearray(len(data))
    for i in range(len(data)):
        j = offset + i
        m = (j ^ (j >> 8) ^ (j >> 16) ^ (j >> 24)) & 0xFF
        x = data[i] ^ fk[j % 17]
        x = (x ^ ((x << 4) & 0xFF)) & 0xFF
        x ^= slot[j % 16]
        x ^= m
        out[i] = x
    return bytes(out)


def kgm_new_decrypt(data: bytes):
    """新格式 .kgm/.kgma/.vpr（头部 16 字节魔数）。返回 (音频, 扩展名)。"""
    magic = data[:16]
    if magic not in (KGM_MAGIC, VPR_MAGIC):
        raise ValueError("不是酷狗新格式文件（头部魔数不符）")
    off = struct.unpack_from("<I", data, 0x10)[0]
    enc_type = struct.unpack_from("<I", data, 0x14)[0]
    sig = bytearray(data[0x1C:0x2C])
    file_key = data[0x2C:0x3C]
    if enc_type == 2:
        sig = _t2_decrypt(sig)
    elif enc_type == 3:
        sig = _t3_decrypt(sig, file_key)
    else:
        raise ValueError("不支持的酷狗加密类型 %d" % enc_type)
    expected = KGM_SIGNATURE if magic == KGM_MAGIC else VPR_SIGNATURE
    if bytes(sig) != expected:
        raise ValueError("文件签名校验失败：可能已损坏或不是酷狗音乐文件")
    if enc_type == 2:
        audio = _t2_decrypt(data[off:])
    else:
        audio = _t3_decrypt(data[off:], file_key)
    return audio, _sniff_ext(audio[:16])


# ----------------------------------------------- KGM 旧格式 (.kgm 历史版本)
TABLE1 = bytes.fromhex(
    "00000000000000000000000000000000"
    "0001210161012101e101210161012101"
    "d223020242420202c2c2020242420202"
    "d3d3020363436303e3c3e30363436303"
    "94b49465040404048484848404040404"
    "9595959504052505e585a585e5052505"
    "d6b696b6d6270606c6c68686c6c60606"
    "d7d79797d7d70607e7c7e787e7c7e707"
    "18381878183818e90808080808080808"
    "19191919191919190809290969092909"
    "da3a1a3a5a3a1a3ada2b0a0a4a4a0a0a"
    "dbdb1b1b5b5b1b1bdbdb0a0b6b4b6b0b"
    "9cbc9c7c1c3c1c7c9cbc9c6d0c0c0c0c"
    "9d9d9d9d1d1d1d1d9d9d9d9d0c0d2d0d"
    "debe9ebede3e1e3edebe9ebede2f0e0e"
    "dfdf9f9fdfdf1f1fdfdf9f9fdfdf0e0f"
    "00200060002000e000200060002000f1"
)
TABLE2 = bytes.fromhex(
    "00000000000000000000000000000000"
    "0001230167012301ef01230167012301"
    "df21020246460202cece020246460202"
    "dede020365476503edcfed0365476503"
    "9dbf9d63040404048c8c8c8c04040404"
    "9c9c9c9c04052705eb8daf8deb052705"
    "dbbd9fbddb250606caca8e8ecaca0606"
    "dada9e9edada0607e9cbe98fe9cbe907"
    "193b197f193b19e70808080808080808"
    "181818181818181808092b096f092b09"
    "d7391b395f391b39d7290a0a4e4e0a0a"
    "d6d61a1a5e5e1a1ad6d60a0b6d4f6d0b"
    "95b7957b1d3f1d7b95b7956b0c0c0c0c"
    "949494941c1c1c1c949494940c0d2f0d"
    "d3b597b5d33d1f3dd3b597b5d32d0e0e"
    "d2d29696d2d21e1ed2d29696d2d20e0f"
    "00220066002200ee00220066002200fe"
)
MASK_V2_PREDEF = bytes.fromhex(
    "b8d53db2e9af788c8333715176a0cd37"
    "2f3e358da9be98b7e78c22ce5a61df68"
    "6989fea5b6dea977fcc8bdbde56d3e5a"
    "36ef694ebee1e9661cf3d902b6f2129b"
    "44d06fb93589b6466d73820669c1edd7"
    "85c230dfa262be792d62623d0d7ebe48"
    "892302a0e4d57551320253fd163a213b"
    "160fc3b2bbb3e2ba3a3d13ecf6014584"
    "a5700f93490c64cd31d5cc4c07019e00"
    "1a2390bf881e3baba63ec47347107e3b"
    "5ebce30084ff09d4e0890f5b58704ffb"
    "65d85c531bd3c8c6bfef98b0504f0fea"
    "e583588c282c8467cdd09e47db2750ca"
    "f46363e8977f1b4b0cc2c1214ccc58f5"
    "9452a3f3d3e068f40023f35e0a7b93dd"
    "ab12b213e884d7a79f0f324c551d0436"
    "52dc03f3f94e42e93d61ef7cb6b39350"
)


def kgm_legacy_decrypt(data: bytes):
    """旧版 .kgm：header_len@16，key@28(17字节)，音频按 MaskV2PreDef 方案。"""
    if len(data) < 45:
        raise ValueError("文件太小，不是有效的旧版 kgm")
    header_len = struct.unpack_from("<I", data, 16)[0]
    if not (45 <= header_len < len(data)):
        raise ValueError("旧版 kgm 头部长度异常")
    key = data[28:45]  # 17 字节（末字节 0）
    audio = data[header_len:]
    out = bytearray(len(audio))
    t1, t2, pre = TABLE1, TABLE2, MASK_V2_PREDEF
    for i in range(len(audio)):
        med8 = key[i % 17] ^ audio[i]
        med8 = (med8 ^ ((med8 & 0x0F) << 4)) & 0xFF
        msk8 = 0
        offset = i >> 4
        while offset >= 0x11:
            msk8 ^= t1[offset % 272]
            offset >>= 4
            msk8 ^= t2[offset % 272]
            offset >>= 4
        msk8 = (pre[i % 272] ^ msk8) & 0xFF
        msk8 = (msk8 ^ ((msk8 & 0x0F) << 4)) & 0xFF
        out[i] = med8 ^ msk8
    return bytes(out), _sniff_ext(bytes(out[:16]))


# ---------------------------------------------------------------- 通用入口
def _sniff_ext(head: bytes) -> str:
    return "flac" if head[:4] == b"fLaC" else "mp3"


def detect(data: bytes) -> str:
    """识别容器类型。"""
    if data[:8] == NCM_MAGIC:
        return "ncm"
    if data[:16] in (KGM_MAGIC, VPR_MAGIC):
        return "kgm_new"
    return "kgm_legacy"


def decrypt(data: bytes):
    """自动识别并解密，返回 (音频bytes, 扩展名, meta, 封面)。"""
    kind = detect(data)
    if kind == "ncm":
        audio, ext, meta, cover = ncm_decrypt(data)
        return audio, ext, meta, cover
    if kind == "kgm_new":
        audio, ext = kgm_new_decrypt(data)
        return audio, ext, {}, None
    audio, ext = kgm_legacy_decrypt(data)
    return audio, ext, {}, None


def safe_filename(title: str) -> str:
    bad = '\\/:*?"<>|'
    for ch in bad:
        title = title.replace(ch, " ")
    title = " ".join(title.split())
    return title.strip() or "未命名"


def _unique_path(path: str) -> str:
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    n = 2
    while os.path.exists("%s (%d)%s" % (base, n, ext)):
        n += 1
    return "%s (%d)%s" % (base, n, ext)


def convert_bytes(data: bytes, src_name: str, outdir: str, save_cover: bool = True):
    """解密并落盘。返回 dict(out/ext/name/cover/kind)。"""
    audio, ext, meta, cover = decrypt(data)
    stem = os.path.splitext(os.path.basename(src_name))[0]
    title = ""
    artist_str = ""
    if meta:
        title = (meta.get("musicName") or meta.get("MusicName") or "").strip()
        artists = meta.get("artist") or meta.get("artists") or []
        parts = []
        if isinstance(artists, list):
            for a in artists:
                if isinstance(a, list) and a:
                    parts.append(str(a[0]))
                elif a:
                    parts.append(str(a))
        artist_str = "、".join(p for p in parts if p)
    name = safe_filename((title + " - " + artist_str) if title else stem)
    out = _unique_path(os.path.join(outdir, name + "." + ext))
    with open(out, "wb") as f:
        f.write(audio)
    cover_path = None
    if save_cover and cover and cover[:8]:
        cext = "jpg" if cover[:3] == b"\xff\xd8\xff" else "png"
        cover_path = _unique_path(os.path.join(outdir, name + ".cover." + cext))
        with open(cover_path, "wb") as f:
            f.write(cover)
    return {
        "out": out,
        "ext": ext,
        "name": os.path.basename(out),
        "cover": os.path.basename(cover_path) if cover_path else None,
        "kind": detect(data),
    }
