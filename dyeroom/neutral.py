"""A neutral rendering of the raw file, the way Adobe's reference renderer shows it.

Follows the Adobe DNG SDK reference pipeline (dng_render.cpp): white-balanced camera data
in linear ProPhoto RGB, the exposure ramp with the default shadow clip, the ACR3 default
tone curve applied to the largest and smallest channel with the middle one interpolated
(hue is kept), then the output colour space. Colour comes from the camera matrix alone:
no camera picture style or film simulation, and no camera-specific look tables, so it
is close to Adobe Standard without being it.
"""
from functools import lru_cache
from pathlib import Path

import colour
import numpy as np

from . import spectra

SHADOWS = 5.0  # DNG SDK default shadow clip (0.5 % of white)
# Lightness (CIE L*) of camera JPEGs against scene luminance in stops from a metered grey
# card: the median of 28 photographs from 15 camera makers (tools/sample_raws.txt, Fujifilm files).
TYPICAL_CAMERA = np.array([
    [-6.0, 1], [-4.75, 3], [-3.75, 5], [-3.25, 7], [-2.75, 11], [-2.25, 17], [-1.75, 24],
    [-1.25, 32], [-0.75, 40], [-0.25, 49], [0.25, 59], [0.75, 68], [1.25, 76], [1.75, 83],
    [2.25, 88], [2.75, 93], [3.25, 96], [3.75, 98], [4.25, 99], [6.0, 100]]).T
# An image file keeps its own contrast on the film: its scene is that much flatter than the
# typical camera curve says. The slide on the light box is about 1.2 times as steep as a
# camera JPEG around grey (23 against 19 L* per stop); at 0.85, phone JPEGs come out of the
# film with about their own contrast (mid-tone slope 0.94-1.08 against the file) instead of
# half as much again with black shadows.
FLATTER = 0.85
REC2020_Y = np.array([0.2627, 0.6780, 0.0593], dtype=np.float32)
# Lightness at which the camera's metered grey card is shown. Camera Raw renders the owner's
# Fujifilm raws about half a stop lighter than the camera's own JPEG; this matches it.
GREY_LIGHTNESS = 57.5


@lru_cache(maxsize=1)
def _tone_table():
    path = Path(__file__).parent / "data" / "acr3_default_tone_curve.txt"
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if not line.startswith("#")]
    return np.array(" ".join(lines).split(), dtype=np.float32)


def _matrix(src, dst):
    return colour.matrix_RGB_to_RGB(src, dst, chromatic_adaptation_transform="Bradford").astype(np.float32)


def _exposure_ramp(x, exposure):
    """dng_function_exposure_ramp: black clip with a quadratic toe, white at 2^-exposure."""
    white = 1.0 / 2.0 ** max(0.0, exposure)
    black = SHADOWS * 0.001 * white  # of the exposed range (the SDK clips raw units, too much for dark raws)
    slope = 1.0 / (white - black)
    radius = min(0.5 * black, (1.0 / 16.0) / slope)
    q = slope / (4.0 * radius) if radius > 0 else 0.0
    linear = np.minimum((x - black) * slope, 1.0)
    toe = q * np.square(x - (black - radius))
    return np.where(x <= black - radius, 0.0, np.where(x >= black + radius, linear, toe)).astype(np.float32)


def _tone(x, exposure):
    """dng_function_exposure_tone (darkening for negative exposure) then the ACR3 curve."""
    if exposure < 0:
        s = 2.0 ** exposure
        a = 16.0 / 9.0 * (1.0 - s)
        b = s - 0.5 * a
        c = 1.0 - a - b
        x = np.where(x <= 0.25, x * s, (a * x + b) * x + c)
    table = _tone_table()
    return np.interp(np.clip(x, 0.0, 1.0), np.linspace(0.0, 1.0, len(table)), table).astype(np.float32)


def _rgb_tone(rgb, exposure):
    """RefBaselineRGBTone: tone the largest and smallest channel, keep the hue."""
    hi = rgb.max(axis=-1, keepdims=True)
    lo = rgb.min(axis=-1, keepdims=True)
    t_hi, t_lo = _tone(hi, exposure), _tone(lo, exposure)
    span = hi - lo
    with np.errstate(invalid="ignore", divide="ignore"):
        out = t_lo + (t_hi - t_lo) * np.where(span > 0, (rgb - lo) / span, 0.0)
    return np.where(span > 0, out, _tone(rgb, exposure)).astype(np.float32)


def render(raw_linear, exposure=0.0, space=spectra.SRGB, chunk=1 << 20):
    """Encoded display RGB (0-1) from white-balanced linear Rec.2020 raw data scaled so the
    sensor's clipping point is 1, with exposure in stops (Adobe's Exposure plus the
    camera's baseline exposure)."""
    to_prophoto = _matrix(spectra.REC2020, colour.RGB_COLOURSPACES["ProPhoto RGB"])
    to_display = _matrix(colour.RGB_COLOURSPACES["ProPhoto RGB"], space)
    flat = raw_linear.reshape(-1, 3)
    out = np.empty_like(flat, dtype=np.float32)
    for i in range(0, len(flat), chunk):
        x = np.clip(flat[i:i + chunk] @ to_prophoto.T, 0.0, None)
        x = _exposure_ramp(x, exposure)
        x = _rgb_tone(x, exposure)
        x = np.clip(x @ to_display.T, 0.0, 1.0)
        out[i:i + chunk] = space.cctf_encoding(x)
    return out.reshape(raw_linear.shape)


@lru_cache(maxsize=1)
def _grey_input():
    """Linear input that the tone curve brings to GREY_LIGHTNESS on screen."""
    table = _tone_table()
    y = ((GREY_LIGHTNESS + 16) / 116) ** 3
    return float(np.interp(y, table, np.linspace(0.0, 1.0, len(table))))


def baseline(cap):
    """Exposure (stops) that shows the camera's metered grey at GREY_LIGHTNESS: the capture's
    scale puts that grey at 0.18, and Adobe's curve lifts mid-tones about a stop."""
    return float(np.log2(cap.raw_scale * _grey_input() / 0.18))


def _scene(display):
    """Scene light (0.18 = metered grey) of display-linear values, through the typical camera
    curve backwards (black two stops below its darkest point), flattened by FLATTER."""
    v = np.clip(display, 0.0, 1.0)
    lstar = np.where(v > 216 / 24389, 116 * np.cbrt(v) - 16, v * 24389 / 27)
    stops = np.interp(lstar, np.r_[0.0, TYPICAL_CAMERA[1]], np.r_[-8.0, TYPICAL_CAMERA[0]])
    return (0.18 * np.exp2(FLATTER * stops)).astype(np.float32)


def unrender(display):
    """Scene-linear Rec.2020 from a camera's rendering (display-linear Rec.2020, 0-1).

    A JPEG already carries the camera's tone curve, an S nearly as steep as a film's. Laid on
    film as it is, the picture gets both: shadows go black and highlights white. So each
    pixel's luminance goes through the typical camera curve backwards (lightness of a grey
    against stops from a metered grey), flattened by the film's extra steepness, and the
    pixel is scaled to it: its colour, the ratios of its channels, stays as the file has it.
    The slide keeps the file's contrast and takes the film's colour, grain and sharpness.
    (Flattening each channel as well took the colour out with the contrast.)"""
    y = np.maximum(display @ REC2020_Y, 0.0)[..., None]
    return (display * (_scene(y) / np.maximum(y, 1e-6))).astype(np.float32)


def preview(cap, long_edge=None, space=spectra.SRGB, shift=0.0):
    """The neutral rendering of a captured raw (encoded RGB), or the file itself for images."""
    from .capture import _resize
    if cap.raw_scale is None:
        return _resize(cap.preview, long_edge)
    return render(_resize(cap.rgb, long_edge) / cap.raw_scale, baseline(cap) + shift, space)
