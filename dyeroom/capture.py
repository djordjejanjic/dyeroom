"""Reading the photograph: camera raw or an ordinary image file.

Raws are decoded with LibRaw. A linear DNG that LibRaw cannot read (Apple ProRAW compressed
with JPEG XL, from recent iPhones) is read by dng.py, the same everywhere. On macOS, Apple's RAW
engine (Core Image) takes over for other cameras LibRaw cannot read, or whose colour data in
LibRaw disagrees with Apple's.
Output is scene-linear, white-balanced Rec.2020 with 0.18 = grey card at the
photographer's intended exposure, plus what the scene light was. An image file is turned back
into scene light by undoing a camera's tone curve, so the film does not add its contrast to the
camera's (neutral.unrender). It is also checked for the camera's own sharpening (detail.py),
measured on the file as the camera wrote it, for the film to be exposed without it.
"""
import io
import json
import logging
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import colour
import cv2
import numpy as np
import pi_heif
import rawpy
import tifffile
from PIL import Image, ImageCms, ImageOps

from . import detail, dng, neutral, spectra

RAW_SUFFIXES = {".raf", ".nef", ".cr2", ".cr3", ".arw", ".dng", ".orf", ".rw2", ".pef", ".srw",
                ".nrw", ".raw", ".rwl", ".3fr", ".iiq", ".erf", ".mos", ".x3f", ".srf", ".sr2"}
# Film formats the picture can be laid onto, long side x short side of the frame in mm.
# The picture fills as much of the frame as its shape allows, as if it had been framed that
# way in the camera: a 4:3 photograph on 35 mm uses 32 x 24 mm of the 36 x 24 mm frame.
FORMATS = {"35mm": (36.0, 24.0), "645": (56.0, 41.5), "6x6": (56.0, 56.0), "6x7": (69.5, 56.0)}
# A small file can claim an enormous picture. Larger than this is refused before it can take
# all the memory (Pillow raises its error at twice MAX_IMAGE_PIXELS).
MAX_PIXELS = 160_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS // 2
pi_heif.register_heif_opener()  # iPhone photographs (HEIC), decoded upright
MACRAW_SOURCE = Path(__file__).with_name("macraw.swift")
MACRAW_BINARY = Path(__file__).parent / "data" / "cache" / "macraw"


@dataclass
class Capture:
    rgb: np.ndarray                 # (H, W, 3) float32 linear Rec.2020, 0.18 = grey
    scene_cct: float | None         # colour temperature of the light the camera balanced for
    exposure_time: float | None
    um_per_px: float                # size of one pixel on the film (35 mm unless laid on another format)
    notes: dict = field(default_factory=dict)
    preview: np.ndarray | None = None  # the camera's own rendering (sRGB 0-1), upright
    flash: bool | None = None          # the camera's flash fired (None: not recorded)
    raw_scale: float | None = None     # rgb / raw_scale = raw data with sensor clipping at 1
    monochrome: bool = False           # a black-and-white (or evenly toned) picture
    sharpened: tuple = (0.0, 0.0)      # the camera's sharpening to take out: strength, radius in px of rgb


def _luminance(rgb):
    return rgb @ np.array([0.2627, 0.6780, 0.0593], dtype=np.float32)


def _resize(img, long_edge):
    h, w = img.shape[:2]
    if not long_edge or max(h, w) <= long_edge:
        return img
    s = long_edge / max(h, w)
    return cv2.resize(img, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA)


def um_per_px(shape, film_format="35mm"):
    """Size of one pixel, in micrometres, of a picture of this shape laid onto the film format."""
    long_mm, short_mm = FORMATS[film_format]
    return 1000.0 * min(long_mm / max(shape[:2]), short_mm / min(shape[:2]))


def _as_shot_cct(raw):
    """Colour temperature implied by the camera's white balance multipliers."""
    wb = np.array(raw.camera_whitebalance[:3], float)
    cam_from_xyz = np.array(raw.rgb_xyz_matrix[:3], float)
    if wb.min() <= 0 or not np.isfinite(cam_from_xyz).all() or np.abs(cam_from_xyz).sum() == 0:
        return None
    xyz = np.linalg.solve(cam_from_xyz, 1.0 / wb)
    return float(colour.temperature.xy_to_CCT(colour.XYZ_to_xy(xyz), method="Hernandez 1999"))


def _number(value):
    if isinstance(value, tuple):  # TIFF rational (numerator, denominator)
        return value[0] / value[1] if len(value) == 2 and value[1] else None
    return float(value)


def _shot_facts(exposure_time, flash):
    """Shutter time in seconds, and whether the flash fired (EXIF Flash tag, bit 0)."""
    time = _number(exposure_time) if exposure_time else None
    return time, None if flash is None else bool(int(flash) & 1)


def _exif(source):
    """Shutter time and flash from a file, or from the camera JPEG embedded in a raw."""
    try:
        exif = Image.open(source).getexif().get_ifd(0x8769)
        return _shot_facts(exif.get(0x829A), exif.get(0x9209))
    except Exception:
        return None, None


def _space(info):
    """The colour space a file's pixels are in: Display P3 (iPhones, many Android phones) or sRGB.
    By the name of its ICC profile (Apple's spells it in UTF-16), or a HEIF's colour primaries."""
    try:
        name = ImageCms.getProfileDescription(ImageCms.ImageCmsProfile(io.BytesIO(info["icc_profile"])))
    except (KeyError, TypeError, OSError, ImageCms.PyCMSError):
        name = ""
    nclx = info.get("nclx_profile") or {}
    return spectra.P3 if "P3" in name or nclx.get("color_primaries") == 12 else spectra.SRGB


def _raw_exif(path):
    """Shutter time and flash from the raw's own EXIF (TIFF-based raws: DNG, NEF, ARW, CR2...)."""
    log = logging.getLogger("tifffile")
    level = log.level
    log.setLevel(logging.CRITICAL)  # unsupported raw compressions are irrelevant here
    try:
        with tifffile.TiffFile(path) as tif:
            exif = tif.pages[0].tags.get("ExifTag")
            exif = exif.value if exif else {}
            return _shot_facts(exif.get("ExposureTime"), exif.get("Flash"))
    except Exception:
        return None, None
    finally:
        log.setLevel(level)


def _monochrome(rgb):
    """True when every pixel has the same chromaticity: a black-and-white picture, or one
    toned in a single colour. Near-blacks are left out, where noise has no colour to speak of."""
    small = _resize(rgb, 400).reshape(-1, 3)
    total = small.sum(axis=1)
    keep = total > 0.03
    if keep.sum() < 100:
        return False
    chroma = small[keep] / total[keep, None]
    spread = np.abs(chroma - np.median(chroma, axis=0)).max(axis=1)
    return bool(np.percentile(spread, 99) < 0.004)


def _noise_sigma(channel):
    """Robust noise level: median absolute Laplacian over the flattest 20 % of 32 px blocks."""
    lap = cv2.Laplacian(channel, cv2.CV_32F, ksize=1)
    h, w = (np.array(lap.shape) // 32) * 32
    blocks = np.abs(lap[:h, :w]).reshape(h // 32, 32, w // 32, 32).transpose(0, 2, 1, 3).reshape(-1, 1024)
    mad = np.median(blocks, axis=1)
    return float(np.percentile(mad, 20) / 0.6745 / np.sqrt(20.0))


def denoise(rgb):
    """Remove the digital sensor noise a film would never have seen.

    Works in a square-root (shot-noise stabilised) space so noise is even from shadows
    to highlights. Colour noise is removed strongly with a bilateral filter that also
    respects luminance edges; luminance noise only lightly (film grain replaces it).
    """
    v = np.sqrt(np.maximum(rgb, 0.0)).astype(np.float32)
    y = v.mean(axis=-1)
    sigma = _noise_sigma(y)
    if sigma < 2e-3:
        return rgb, sigma
    c1, c2 = v[..., 0] - v[..., 1], v[..., 2] - v[..., 1]
    guide = np.dstack([c1, c2, y * 0.5]).astype(np.float32)
    smooth = cv2.bilateralFilter(guide, 0, sigmaColor=float(4.0 * sigma), sigmaSpace=4.0)
    smooth = cv2.bilateralFilter(smooth, 0, sigmaColor=float(3.0 * sigma), sigmaSpace=2.0)
    c1, c2 = smooth[..., 0], smooth[..., 1]
    y = cv2.bilateralFilter(y, 0, sigmaColor=float(1.5 * sigma), sigmaSpace=1.2)
    g = y - (c1 + c2) / 3.0
    out = np.dstack([g + c1, g, g + c2])
    return np.square(np.maximum(out, 0.0)), sigma


def _meter_like_camera(preview, rgb):
    """Exposure the photographer chose: match mid-tones to the camera's own rendering.

    Camera renderings place a grey card near display-linear 0.18, so the mid-tone
    luminance of the camera's JPEG (sRGB, 0-1) fixes the scale of the scene-linear data.
    """
    if preview is None:
        return None
    lin = colour.models.eotf_sRGB(preview) @ colour.RGB_COLOURSPACES["sRGB"].matrix_RGB_to_XYZ[1]
    y_raw = _luminance(rgb)
    pct = [35, 42, 50, 58, 65]
    a = np.percentile(lin[lin > 1e-4], pct)
    b = np.percentile(y_raw[y_raw > 1e-6], pct)
    return float(np.exp(np.mean(np.log(a) - np.log(b))))


def _embedded_jpeg(raw):
    try:
        thumb = raw.extract_thumb()
    except Exception:
        return None, (None, None)
    if thumb.format != rawpy.ThumbFormat.JPEG:
        return None, (None, None)
    jpeg = ImageOps.exif_transpose(Image.open(io.BytesIO(thumb.data))).convert("RGB")
    return np.asarray(jpeg, np.float32) / 255.0, _exif(io.BytesIO(thumb.data))


def _read_libraw(path, long_edge):
    with rawpy.imread(str(path)) as raw:
        half = bool(long_edge) and max(raw.sizes.width, raw.sizes.height) >= 2.2 * long_edge
        img = raw.postprocess(output_color=rawpy.ColorSpace.Rec2020, gamma=(1, 1),
                              no_auto_bright=True, output_bps=16, use_camera_wb=True,
                              highlight_mode=rawpy.HighlightMode.Blend, half_size=half)
        preview, (exposure_time, flash) = _embedded_jpeg(raw)
        return dict(rgb=_resize(img.astype(np.float32) / 65535.0, long_edge), preview=preview,
                    cct=_as_shot_cct(raw), exposure_time=exposure_time, flash=flash, decoder="LibRaw")


def _macraw():
    """Compile the small Core Image decoder on first use (macOS with Xcode tools only)."""
    if sys.platform != "darwin":
        return None
    if not MACRAW_BINARY.exists() or MACRAW_BINARY.stat().st_mtime < MACRAW_SOURCE.stat().st_mtime:
        MACRAW_BINARY.parent.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(["swiftc", "-O", str(MACRAW_SOURCE), "-o", str(MACRAW_BINARY)],
                           check=True, capture_output=True, timeout=300)
        except (OSError, subprocess.SubprocessError):
            return None
    return MACRAW_BINARY


def _read_apple(path, long_edge):
    exe = _macraw()
    if exe is None:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        tif, png = Path(tmp) / "linear.tif", Path(tmp) / "preview.png"
        run = subprocess.run([str(exe), str(path), str(tif), str(png), str(long_edge or 0)],
                             capture_output=True, text=True, timeout=600)
        if run.returncode != 0 or not tif.exists():
            return None
        info = json.loads(run.stdout.strip().splitlines()[-1])
        rgb = tifffile.imread(tif)[..., :3].astype(np.float32)
        preview = np.asarray(Image.open(png).convert("RGB"), np.float32) / 255.0
    return dict(rgb=rgb, preview=preview, cct=info["temperature"], exposure_time=None, flash=None,
                decoder="Apple Core Image")


def _colour_balance(rgb):
    """Average colour of the mid-tones relative to luminance (decoder agreement check)."""
    small = _resize(rgb, 400)
    y = _luminance(small)
    mid = (y > np.percentile(y, 30)) & (y < np.percentile(y, 97))
    return (small[mid] / np.maximum(y[mid, None], 1e-6)).mean(axis=0)


def _decode_raw(path, long_edge):
    try:
        lib = _read_libraw(path, long_edge)
    except (rawpy.LibRawError, OSError):
        lib = None
    if lib is None and dng.is_linear(path):
        try:
            return dng.read(path, lambda img: _resize(img, long_edge)), {}
        except Exception as exc:  # a DNG this reader cannot follow either: Apple's engine, or the message below
            logging.getLogger(__name__).info("DNG reader: %s", exc)
    check = _read_apple(path, long_edge if lib is None else 1200)
    if lib is None:
        if check is None:
            raise ValueError("This camera's raw format is too new for the decoder on this server. "
                             "Convert it to DNG with Adobe DNG Converter, or export a 16-bit TIFF, "
                             "and drop that instead.")
        return check, {}
    notes = {}
    if check is not None:
        disagreement = np.abs(np.log(_colour_balance(lib["rgb"]) / _colour_balance(check["rgb"]))).max()
        if disagreement > 0.2:
            apple = _read_apple(path, long_edge) if long_edge != 1200 else check
            if apple is not None:
                apple["exposure_time"], apple["flash"] = lib["exposure_time"], lib["flash"]
                return apple, {"LibRaw colours rejected": round(float(disagreement), 2)}
        if lib["cct"] is None:
            lib["cct"] = check["cct"]
            notes["scene light from"] = "Apple"
    return lib, notes


def read(path, long_edge=None):
    path = Path(path)
    if path.suffix.lower() in RAW_SUFFIXES:
        decoded, notes = _decode_raw(path, long_edge)
        rgb, cct, exposure_time, flash = decoded["rgb"], decoded["cct"], decoded["exposure_time"], decoded["flash"]
        if exposure_time is None or flash is None:
            raw_time, raw_flash = _raw_exif(path)
            exposure_time = raw_time if exposure_time is None else exposure_time
            flash = raw_flash if flash is None else flash
        scale = _meter_like_camera(decoded["preview"], rgb)
        notes.update(decoder=decoded["decoder"], metering="camera rendering" if scale else "averaging meter")
        if scale is None:
            scale = 0.18 / np.exp(np.mean(np.log(np.maximum(_luminance(rgb), 1e-5))))
        rgb = rgb * scale
        raw_scale = scale
        preview = decoded["preview"]
        sharpened = (0.0, 0.0)  # raw data: not sharpened (ProRAW's linear data measures as unsharpened too)
    else:
        try:
            img = ImageOps.exif_transpose(Image.open(path))
        except Image.DecompressionBombError:
            raise ValueError(f"This picture is larger than {MAX_PIXELS // 1_000_000} megapixels: too large to develop")
        if (img.info.get("nclx_profile") or {}).get("transfer_characteristics") in (16, 18):
            raise ValueError("This is an HDR picture (PQ or HLG): save it as an ordinary JPEG to develop it")
        arr = np.asarray(img.convert("RGB"), np.float32) / 255.0
        space = _space(img.info)
        lin = _resize(colour.models.eotf_sRGB(arr).astype(np.float32), long_edge)
        rgb = neutral.unrender(lin @ (spectra.REC2020.matrix_XYZ_to_RGB @ space.matrix_RGB_to_XYZ).T.astype(np.float32))
        del lin
        cct, (exposure_time, flash) = None, _exif(path)
        notes = {"metering": "file as delivered", "source space": space.name}
        strength, radius = detail.measure(arr @ np.array([0.2126, 0.7152, 0.0722], np.float32))
        sharpened = (strength, radius * max(rgb.shape[:2]) / max(arr.shape[:2]))  # radius at rgb's size
        if strength:
            notes["camera sharpening"] = round(strength, 2)
        preview, raw_scale = arr, None
    if rgb.shape[0] * rgb.shape[1] > MAX_PIXELS:
        raise ValueError(f"This picture is larger than {MAX_PIXELS // 1_000_000} megapixels: too large to develop")
    monochrome = _monochrome(rgb)
    rgb, noise = denoise(rgb.astype(np.float32))
    notes["sensor noise"] = round(noise, 4)
    if flash:
        notes["flash"] = "fired"
    return Capture(rgb.astype(np.float32), cct, exposure_time, um_per_px(rgb.shape), notes, preview, flash, raw_scale,
                   monochrome, sharpened)
