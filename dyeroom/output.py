"""Writing developed slides: JPEG and 16-bit TIFF, tagged with their colour space."""
import io

import colour
import numpy as np
import tifffile
from PIL import Image

from . import icc


def encode(rgb_linear):
    """Linear display RGB (0-1) to the sRGB transfer curve, which Display P3 shares."""
    return colour.models.eotf_inverse_sRGB(np.clip(rgb_linear, 0.0, 1.0))


def jpeg_bytes(encoded, display, quality=95, long_edge=None):
    """JPEG with the display's ICC profile from encoded RGB (float 0-1, or uint8 / uint16)."""
    if encoded.dtype == np.uint16:
        encoded = np.round(encoded / 257.0).astype(np.uint8)
    img = Image.fromarray(encoded if encoded.dtype == np.uint8 else np.round(encoded * 255).astype(np.uint8))
    if long_edge and max(img.size) > long_edge:
        img.thumbnail((long_edge, long_edge), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality, subsampling=0, icc_profile=icc.profile(display))
    return buf.getvalue()


def tiff_bytes(encoded16, display):
    """16-bit TIFF with the display's ICC profile from encoded uint16 RGB."""
    profile = icc.profile(display)
    buf = io.BytesIO()
    tifffile.imwrite(buf, encoded16, photometric="rgb", compression="zlib",
                     extratags=[(34675, "B", len(profile), profile, True)])
    return buf.getvalue()


def save(rgb_linear, out, display, tiff=False):
    """Write <out>.jpg (and <out>.tif) from linear display RGB."""
    encoded = encode(rgb_linear)
    out.with_suffix(".jpg").write_bytes(jpeg_bytes(encoded, display))
    if tiff:
        out.with_suffix(".tif").write_bytes(tiff_bytes(np.round(encoded * 65535).astype(np.uint16), display))
