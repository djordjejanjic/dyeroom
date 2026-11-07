"""Minimal ICC v4 display profiles (matrix + sRGB curve) for Display P3 and sRGB.

Generated in code so output files carry the right colour space on any OS, without
depending on profiles installed on the machine.
"""
import struct
from functools import lru_cache

import colour
import numpy as np

D50 = np.array([0.9642, 1.0, 0.8249])
BRADFORD = colour.adaptation.CAT_BRADFORD


def _s15(values):
    return b"".join(struct.pack(">i", int(round(v * 65536))) for v in np.ravel(values))


def _xyz_tag(xyz):
    return b"XYZ " + b"\0" * 4 + _s15(xyz)


def _mluc(text):
    body = text.encode("utf-16-be")
    return (b"mluc" + b"\0" * 4 + struct.pack(">II", 1, 12) + b"enUS"
            + struct.pack(">II", len(body), 28) + body)


def _srgb_curve():
    # Parametric curve type 3: Y = (aX + b)^g for X >= d, Y = cX below.
    g, a, b, c, d = 2.4, 1 / 1.055, 0.055 / 1.055, 1 / 12.92, 0.04045
    return b"para" + b"\0" * 4 + struct.pack(">HH", 3, 0) + _s15([g, a, b, c, d])


def _chad(white_xyz):
    src = BRADFORD @ white_xyz
    dst = BRADFORD @ D50
    return np.linalg.inv(BRADFORD) @ np.diag(dst / src) @ BRADFORD


@lru_cache(maxsize=4)
def profile(name):
    """ICC bytes for 'p3' (Display P3) or 'srgb'."""
    space = colour.RGB_COLOURSPACES["Display P3" if name == "p3" else "sRGB"]
    white = colour.xy_to_XYZ(space.whitepoint)
    chad = _chad(white)
    colorants = chad @ space.matrix_RGB_to_XYZ  # columns: D50-adapted R, G, B
    curve = _srgb_curve()
    tags = [
        (b"desc", _mluc("Display P3" if name == "p3" else "sRGB")),
        (b"cprt", _mluc("No copyright, use freely")),
        (b"wtpt", _xyz_tag(D50)),
        (b"rXYZ", _xyz_tag(colorants[:, 0])),
        (b"gXYZ", _xyz_tag(colorants[:, 1])),
        (b"bXYZ", _xyz_tag(colorants[:, 2])),
        (b"rTRC", curve), (b"gTRC", curve), (b"bTRC", curve),
        (b"chad", b"sf32" + b"\0" * 4 + _s15(chad)),
    ]
    table_size = 4 + 12 * len(tags)
    offset = 128 + table_size
    directory, data = struct.pack(">I", len(tags)), b""
    for sig, body in tags:
        body += b"\0" * (-len(body) % 4)
        directory += sig + struct.pack(">II", offset + len(data), len(body))
        data += body
    size = 128 + table_size + len(data)
    header = (struct.pack(">I", size) + b"\0" * 4 + struct.pack(">I", 0x04300000) + b"mntrRGB XYZ "
              + struct.pack(">6H", 2026, 1, 1, 0, 0, 0) + b"acsp" + b"\0" * 4 + struct.pack(">I", 0)
              + b"\0" * 8 + b"\0" * 8 + struct.pack(">I", 0) + _s15(D50) + b"\0" * 4 + b"\0" * 16 + b"\0" * 28)
    assert len(header) == 128
    return header + directory + data
