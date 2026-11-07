"""How much light the photographer gives the film.

Slide film renders a frame with a steeper tone scale than a camera's JPEG: shadows go
deeper, highlights brighter, so a frame the camera showed as light or dark can come out
lighter or darker overall on the slide. A slide photographer judged exposure by the slides
it gave. Here the exposure on the film is chosen so that the slide, as seen, matches the
brightness of a reference rendering of the same frame as closely as the film allows: least
squares in CIE lightness over the whole frame, through the film's own tone scale and the
chosen viewing. Shadows and highlights still fall where the film puts them.

The reference is a neutral rendering of the raw file (neutral.py: Adobe's reference
renderer, no camera picture style), at the brightness the camera chose ("camera"), or with
"auto" at the brightness the scene itself calls for, whatever the camera was set to: like a
centre-weighted averaging meter it puts the scene's mean log luminance about 0.65 stop
below a grey card (12 % grey, the classic average scene, and where the cameras we tested
put it on average). A JPEG or TIFF file is its own reference (its pixels were turned back into scene light by
neutral.unrender, so the film's tone scale is not laid on top of the camera's).
"""
from functools import lru_cache

import cv2
import numpy as np

from . import film as film_model, neutral, process as reversal, spectra, viewing as views
from .capture import _luminance, _resize

TYPICAL_CAMERA = neutral.TYPICAL_CAMERA
AVERAGE_SCENE = -0.65  # stops from grey of an average scene's centre-weighted mean log luminance
GREY_LIGHTNESS = neutral.GREY_LIGHTNESS  # a metered grey card as the neutral rendering shows it
SAMPLE_EDGE = 512      # the brightness match is made on a small copy of the frame


def lightness(y):
    """CIE L* of relative luminance."""
    y = np.asarray(y, dtype=np.float64)
    return np.where(y > 216 / 24389, 116 * np.cbrt(np.maximum(y, 0)) - 16, y * 24389 / 27)


def _grey_on_slide(view_name, first_developer, stops):
    """Light through greys exposed `stops` from a metered grey card, relative to clear film."""
    film = film_model.load()
    view = views.VIEWINGS[view_name]
    log_h = (np.asarray(stops) * np.log10(2.0) + reversal.metered_grey_log_h(film))[:, None] \
        + reversal.grey_balance(film)
    process = reversal.Process(first_developer=first_developer, grain=False)
    developed = reversal.first_developer(log_h[None], film, process, 1e6)  # no spatial effects
    dyes = reversal.reversal_and_dyes(developed, film, process, 1e6, 1.0)[0]
    white = views.dye_transmittance_xyz(np.zeros((1, 3)), film, view.light)[0]
    xyz = views.dye_transmittance_xyz(dyes, film, view.light) + view.flare * 0.18 * white
    return xyz / white[1] * 100.0, white / white[1] * 100.0


def _seen(xyz, white, view_name, gain):
    view = views.VIEWINGS[view_name]
    rgb = views.to_display(views.adapted_to_slide(xyz, gain)[None], white, view, spectra.P3)[0]
    return lightness(rgb @ spectra.P3.matrix_RGB_to_XYZ[1])


@lru_cache(maxsize=8)
def eye_gain(view_name):
    """How far the eye adapts into the slide: a grey card exposed by the meter on a normally
    processed slide looks as light as a neutral rendering shows a grey card (ISO reversal
    speeds are defined so that such a slide looks right)."""
    xyz, white = _grey_on_slide(view_name, 1.0, [0.0])
    target = GREY_LIGHTNESS
    lo, hi = 1.0, 8.0
    if _seen(xyz, white, view_name, lo)[0] >= target:
        return 1.0
    for _ in range(30):
        mid = np.sqrt(lo * hi)
        lo, hi = (mid, hi) if _seen(xyz, white, view_name, mid)[0] < target else (lo, mid)
    return float(np.sqrt(lo * hi))


@lru_cache(maxsize=16)
def film_lightness(view_name, first_developer=1.0):
    """Lightness on screen of a grey on the slide, against exposure in stops from a metered grey."""
    stops = np.arange(-8.0, 6.001, 0.05)
    xyz, white = _grey_on_slide(view_name, first_developer, stops)
    return stops, _seen(xyz, white, view_name, eye_gain(view_name))


def _camera_lightness(preview, shape):
    """The camera's rendering as L*, at the sample size; None if it is framed differently."""
    h, w = shape
    if preview is None or abs(preview.shape[1] / preview.shape[0] - w / h) > 0.02:
        return None
    small = cv2.resize(preview, (w, h), interpolation=cv2.INTER_AREA)
    srgb = spectra.SRGB
    return lightness(srgb.cctf_decoding(np.clip(small, 0, 1)) @ srgb.matrix_RGB_to_XYZ[1])


def _mean_log_stops(stops):
    """Centre-weighted mean of log luminance, ignoring the darkest and brightest 1 %."""
    h, w = stops.shape
    yy, xx = np.mgrid[0:h, 0:w]
    r2 = ((xx + 0.5) / w - 0.5) ** 2 + ((yy + 0.5) / h - 0.5) ** 2
    weight = (0.5 + 0.5 * np.exp(-r2 / (2 * 0.3 ** 2))).ravel()
    s = cv2.GaussianBlur(stops.astype(np.float32), (0, 0), 1.0).ravel()
    order = np.argsort(s)
    cumulative = np.cumsum(weight[order]) / weight.sum()
    lo, hi = np.interp([0.01, 0.99], cumulative, s[order])
    keep = (s >= lo) & (s <= hi)
    return float(np.sum(s[keep] * weight[keep]) / np.sum(weight[keep]))


def _match(stops, target, curve):
    """Exposure shift in stops that brings the slide's lightness closest to the target."""
    keep = (target > 10) & (target < 97)  # blacks and whites the reference clipped say nothing
    if keep.sum() < 0.05 * keep.size:
        keep = np.ones_like(keep)
    x, t = stops[keep], target[keep]
    axis, light = curve

    def cost(shift):
        return np.mean((np.interp(x + shift, axis, light) - t) ** 2)

    coarse = np.arange(-4.0, 6.001, 0.125)
    best = coarse[np.argmin([cost(s) for s in coarse])]
    fine = np.arange(best - 0.125, best + 0.126, 1 / 64)
    return float(fine[np.argmin([cost(s) for s in fine])])


def _reference(cap, stops, shift):
    """Lightness the slide should match: the neutral raw rendering, or the file itself."""
    if cap.raw_scale is not None:
        encoded = neutral.preview(cap, SAMPLE_EDGE, spectra.SRGB, shift)
        if encoded.shape[:2] == stops.shape:
            return lightness(spectra.SRGB.cctf_decoding(encoded) @ spectra.SRGB.matrix_RGB_to_XYZ[1])
    target = None if shift else _camera_lightness(cap.preview, stops.shape)
    return np.interp(stops + shift, *TYPICAL_CAMERA) if target is None else target


def choose(cap, mode, view_name, first_developer=1.0):
    """Exposure on the film in stops relative to the camera's metering."""
    y = _luminance(_resize(cap.rgb, SAMPLE_EDGE))
    stops = np.log2(np.maximum(y, 1e-6) / 0.18)
    curve = film_lightness(view_name, first_developer)
    shift = 0.0
    if mode == "auto":
        shift = float(np.clip(AVERAGE_SCENE - _mean_log_stops(stops), -6.0, 6.0))
    return shift + _match(stops + shift, _reference(cap, stops, shift), curve)
