"""Encode/decode Adobe Camera Raw RGB lookup tables (crs:RGBTable / crs:Table_<md5>).

Not used by the simulator; kept for a possible export of the look as a Camera Raw
profile. Verified: decodes Adobe's own profiles and re-encodes them byte for byte.

Format follows dng_big_table.cpp in the Adobe DNG SDK:
little-endian stream -> zlib with uint32 size prefix -> Z85-like text encoding.
"""
import hashlib
import re
import struct
import zlib

import numpy as np

ENCODE = ("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
          ".-:+=^!/*?`'|()[]{}@%$#")
DECODE = {c: i for i, c in enumerate(ENCODE)}

BTT_RGB_TABLE = 1
VERSION = 1
PRIMARIES = {"sRGB": 0, "AdobeRGB": 1, "ProPhoto": 2, "P3": 3, "Rec2020": 4}
GAMMA = {"linear": 0, "sRGB": 1, "1.8": 2, "2.2": 3, "Rec2020": 4}
GAMUT = {"clip": 0, "extend": 1}


def text_to_binary(s):
    out = bytearray()
    phase = value = 0
    for ch in s:
        d = DECODE.get(ch)
        if d is None:
            continue
        value += d * 85 ** phase
        phase += 1
        if phase == 5:
            out += struct.pack("<I", value)
            phase = value = 0
    if phase > 1:
        out += struct.pack("<I", value)[:phase - 1]
    return bytes(out)


def binary_to_text(b):
    n = len(b)
    padded = b + b"\0\0\0"
    out = []
    for i in range(0, n, 4):
        x = struct.unpack_from("<I", padded, i)[0]
        left = n - i
        digits = []
        for _ in range(5):
            digits.append(ENCODE[x % 85])
            x //= 85
        # 4 bytes -> 5 chars, k<4 leftover bytes -> k+1 chars
        out.append("".join(digits[:5 if left >= 4 else left + 1]))
    return "".join(out)


def _nop(divisions):
    idx = np.arange(divisions)
    return ((idx * 0xFFFF + (divisions >> 1)) // (divisions - 1)).astype(np.int64)


def build_stream(table, primaries="ProPhoto", gamma="1.8", gamut="extend",
                 min_amount=0.0, max_amount=2.0):
    """table: float array (N,N,N,3) indexed [r,g,b], values in 0..1."""
    n = table.shape[0]
    assert table.shape == (n, n, n, 3) and 2 <= n <= 32
    q = np.clip(np.round(table * 65535.0), 0, 65535).astype(np.int64)
    nop = _nop(n)
    delta = np.empty_like(q)
    delta[..., 0] = q[..., 0] - nop[:, None, None]
    delta[..., 1] = q[..., 1] - nop[None, :, None]
    delta[..., 2] = q[..., 2] - nop[None, None, :]
    body = (delta & 0xFFFF).astype("<u2").tobytes()
    head = struct.pack("<4I", BTT_RGB_TABLE, VERSION, 3, n)
    tail = struct.pack("<3I2d", PRIMARIES[primaries], GAMMA[gamma], GAMUT[gamut],
                       min_amount, max_amount)
    return head + body + tail


def encode(stream):
    fingerprint = hashlib.md5(stream).hexdigest().upper()
    blob = struct.pack("<I", len(stream)) + zlib.compress(stream, 6)
    return fingerprint, binary_to_text(blob)


def decode(text):
    blob = text_to_binary(text)
    size = struct.unpack_from("<I", blob)[0]
    stream = zlib.decompress(blob[4:])
    assert len(stream) == size
    btt, ver, dims, n = struct.unpack_from("<4I", stream)
    assert btt == BTT_RGB_TABLE and ver == VERSION, (btt, ver)
    off = 16
    if dims == 3:
        count = n * n * n * 3
        raw = np.frombuffer(stream, "<u2", count, off).astype(np.int64).reshape(n, n, n, 3)
        nop = _nop(n)
        vals = np.empty_like(raw)
        vals[..., 0] = (raw[..., 0] + nop[:, None, None]) & 0xFFFF
        vals[..., 1] = (raw[..., 1] + nop[None, :, None]) & 0xFFFF
        vals[..., 2] = (raw[..., 2] + nop[None, None, :]) & 0xFFFF
    else:
        count = n * 3
        raw = np.frombuffer(stream, "<u2", count, off).astype(np.int64).reshape(n, 3)
        vals = (raw + _nop(n)[:, None]) & 0xFFFF
    off += count * 2
    prim, gam, gamut = struct.unpack_from("<3I", stream, off); off += 12
    amin, amax = struct.unpack_from("<2d", stream, off); off += 16
    flags = struct.unpack_from("<I", stream, off)[0] if off + 4 <= len(stream) else 0
    return dict(dims=dims, divisions=n, table=vals / 65535.0, primaries=prim, gamma=gam,
                gamut=gamut, min_amount=amin, max_amount=amax, flags=flags,
                md5=hashlib.md5(stream).hexdigest().upper(), stream=stream)


def read_xmp_table(path):
    txt = open(path, encoding="utf-8").read()
    key = re.search(r'crs:RGBTable="([0-9A-F]+)"', txt).group(1)
    data = re.search(r'crs:Table_%s="([^"]+)"' % key, txt).group(1)
    data = data.replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return key, data
