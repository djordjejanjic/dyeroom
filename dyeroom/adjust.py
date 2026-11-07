"""Small finishing changes after development: hue, saturation and light for eight colours,
and colour wheels for shadows, midtones and highlights.

The browser previews these live (web/static/adjust.js, the same arithmetic in WebGL); the
downloaded file is made here, from the full-resolution 16-bit result. Colour work is done
in Oklab (Björn Ottosson, 2020), where equal steps look roughly equally large, on the
display-encoded Display P3 or sRGB image.

Parameters (all optional), as sent by the page:
    {"bands":  {"red": [hue, saturation, light], ...},        each -100..100
     "wheels": {"shadows": [angle, amount, light], ...}}      angle 0..360 (Oklab hue),
                                                              amount 0..100, light -100..100

Framing, also chosen on the page after development (the crop of a scan, not of the film:
cropping enlarges the grain as it would): quarter turns, a straightening angle and a crop,
    {"turns": 0..3 (clockwise), "angle": -45..45 degrees (clockwise),
     "crop": {"x", "y", "w", "h"} as fractions of the turned picture}
The picture is turned, then rotated by the angle about its centre, and the crop, an upright
rectangle in the turned picture's frame, is cut from it. The page keeps the crop inside the
rotated picture, so no corner is empty.
"""
import math

import cv2
import numpy as np

from . import spectra

BANDS = {"red": 29.0, "orange": 60.0, "yellow": 100.0, "green": 143.0,
         "aqua": 195.0, "blue": 258.0, "purple": 300.0, "magenta": 348.0}  # Oklab hue centres
WHEELS = ("shadows", "midtones", "highlights")
HUE_RANGE = 30.0      # degrees of hue turn at the end of a band's hue slider
LIGHT_RANGE = 0.12    # Oklab L change at the end of a band's light slider
WHEEL_RANGE = 0.05    # Oklab a/b push at full wheel amount
WHEEL_LIGHT = 0.10    # Oklab L change at the end of a wheel's light slider

_LMS_FROM_XYZ = np.array([[0.8189330101, 0.3618667424, -0.1288597137],
                          [0.0329845436, 0.9293118715, 0.0361456387],
                          [0.0482003018, 0.2643662691, 0.6338517070]])
_LAB_FROM_LMS = np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                          [1.9779984951, -2.4285922050, 0.4505937099],
                          [0.0259040371, 0.7827717662, -0.8086757660]])


def _numbers(values):
    """Three finite numbers, or None: anything else from a page is ignored, never an error."""
    if not isinstance(values, (list, tuple)) or len(values) != 3:
        return None
    if not all(isinstance(x, (int, float)) and not isinstance(x, bool) and np.isfinite(x) for x in values):
        return None
    return [float(x) for x in values]


def clean(params):
    """Validated parameters; anything unknown, out of range or not a number is dropped or clipped."""
    params = params if isinstance(params, dict) else {}
    out = {"bands": {}, "wheels": {}}
    bands, wheels = params.get("bands"), params.get("wheels")
    for name, values in (bands.items() if isinstance(bands, dict) else ()):
        values = _numbers(values)
        if name in BANDS and values:
            v = [float(np.clip(x, -100, 100)) for x in values]
            if any(v):
                out["bands"][name] = v
    for name, values in (wheels.items() if isinstance(wheels, dict) else ()):
        values = _numbers(values)
        if name in WHEELS and values:
            v = [values[0] % 360.0, float(np.clip(values[1], 0, 100)), float(np.clip(values[2], -100, 100))]
            if v[1] or v[2]:
                out["wheels"][name] = v
    return out


def is_identity(params):
    p = clean(params)
    return not p["bands"] and not p["wheels"]


def _smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def apply(encoded, params, space=spectra.P3, chunk=1 << 20):
    """Adjusted copy of display-encoded RGB (..., 3) in [0, 1]."""
    p = clean(params)
    if not p["bands"] and not p["wheels"]:
        return encoded
    centres = np.array(list(BANDS.values()), np.float32)
    band = np.array([p["bands"].get(n, [0, 0, 0]) for n in BANDS], np.float32) / 100.0
    wheel = np.array([p["wheels"].get(n, [0, 0, 0]) for n in WHEELS], np.float32)
    push = np.stack([np.cos(np.radians(wheel[:, 0])), np.sin(np.radians(wheel[:, 0]))], 1) \
        * (wheel[:, 1:2] / 100.0 * WHEEL_RANGE)
    lift = wheel[:, 2] / 100.0 * WHEEL_LIGHT
    to_lms = (_LMS_FROM_XYZ @ space.matrix_RGB_to_XYZ).astype(np.float32)
    from_lms = np.linalg.inv(to_lms).astype(np.float32)
    to_lab, from_lab = _LAB_FROM_LMS.astype(np.float32), np.linalg.inv(_LAB_FROM_LMS).astype(np.float32)

    flat = encoded.reshape(-1, 3).astype(np.float32)
    out = np.empty_like(flat)
    for i in range(0, len(flat), chunk):
        lin = spectra.SRGB.cctf_decoding(flat[i:i + chunk]).astype(np.float32)
        lab = np.cbrt(lin @ to_lms.T) @ to_lab.T
        light, a, b = lab[:, 0], lab[:, 1], lab[:, 2]
        if p["bands"]:
            chroma = np.hypot(a, b)
            hue = np.degrees(np.arctan2(b, a)) % 360.0
            # Between which two band centres the hue lies, and how far (smooth, sums to 1).
            k = (np.searchsorted(centres, hue, side="right") - 1) % len(centres)
            nxt = (k + 1) % len(centres)
            span = (centres[nxt] - centres[k]) % 360.0
            t = _smoothstep(0.0, 1.0, ((hue - centres[k]) % 360.0) / span)
            mix = band[k] * (1 - t)[:, None] + band[nxt] * t[:, None]
            hue = np.radians(hue + mix[:, 0] * HUE_RANGE)
            chroma = chroma * np.maximum(0.0, 1.0 + mix[:, 1])
            light = light + mix[:, 2] * LIGHT_RANGE * _smoothstep(0.0, 0.05, np.hypot(a, b))
            a, b = chroma * np.cos(hue), chroma * np.sin(hue)
        if p["wheels"]:
            shadows = 1.0 - _smoothstep(0.15, 0.55, light)
            highlights = _smoothstep(0.45, 0.85, light)
            weights = np.stack([shadows, np.maximum(0.0, 1.0 - shadows - highlights), highlights], 1)
            a = a + weights @ push[:, 0]
            b = b + weights @ push[:, 1]
            light = light + weights @ lift
        lms = np.stack([light, a, b], 1) @ from_lab.T
        lin = np.clip((lms ** 3) @ from_lms.T, 0.0, 1.0)
        out[i:i + chunk] = spectra.SRGB.cctf_encoding(lin)
    return out.reshape(encoded.shape)


# --- framing ---------------------------------------------------------------------------------

def _finite(value, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return min(high, max(low, float(value)))


def clean_geometry(params):
    """Validated framing: whole quarter turns, an angle within 45 degrees, a crop inside the picture."""
    params = params if isinstance(params, dict) else {}
    turns = params.get("turns")
    turns = turns % 4 if isinstance(turns, int) and not isinstance(turns, bool) else 0
    angle = _finite(params.get("angle", 0), -45.0, 45.0) or 0.0
    crop, raw = None, params.get("crop")
    if isinstance(raw, dict):
        x, y = _finite(raw.get("x"), 0.0, 1.0), _finite(raw.get("y"), 0.0, 1.0)
        w, h = _finite(raw.get("w"), 0.0, 1.0), _finite(raw.get("h"), 0.0, 1.0)
        if None not in (x, y, w, h) and w >= 0.01 and h >= 0.01:
            w, h = min(w, 1.0 - x), min(h, 1.0 - y)
            if w >= 0.01 and h >= 0.01 and (x, y, w, h) != (0.0, 0.0, 1.0, 1.0):
                crop = {"x": x, "y": y, "w": w, "h": h}
    return {"turns": turns, "angle": angle, "crop": crop}


def geometry_is_identity(params):
    g = clean_geometry(params)
    return g["turns"] == 0 and g["angle"] == 0.0 and g["crop"] is None


def frame(image, params):
    """The picture (H, W, channels) turned, straightened and cropped as the page shows it."""
    g = clean_geometry(params)
    image = np.rot90(image, k=-g["turns"])  # negative: clockwise
    height, width = image.shape[:2]
    c = g["crop"] or {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}
    left, top = c["x"] * width, c["y"] * height
    out_w, out_h = max(1, round(c["w"] * width)), max(1, round(c["h"] * height))
    if g["angle"] == 0.0:
        x0, y0 = min(round(left), width - out_w), min(round(top), height - out_h)
        return np.ascontiguousarray(image[y0:y0 + out_h, x0:x0 + out_w])
    # Continuous coordinates (pixel edges at integers): a point q of the turned picture lands at
    # R (q - centre) + centre - (left, top) in the crop; cv2 counts pixel centres, half a pixel in.
    t = math.radians(g["angle"])
    rotation = np.array([[math.cos(t), -math.sin(t)], [math.sin(t), math.cos(t)]])
    centre = np.array([width / 2.0, height / 2.0])
    shift = rotation @ (0.5 - centre) + centre - np.array([left, top]) - 0.5
    matrix = np.hstack([rotation, shift[:, None]])
    return cv2.warpAffine(np.ascontiguousarray(image), matrix, (out_w, out_h), flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_REPLICATE)
