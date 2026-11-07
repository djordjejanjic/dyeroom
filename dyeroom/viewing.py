"""Looking at the finished slide: light through the dyes, the room, the eye, and your screen.

The slide is a set of three dye layers. Light passes through them (Beer-Lambert:
transmittance 10^-density at every wavelength), lands on a screen or reaches the eye
from a light box, mixes with stray light, and is seen by an eye adapted to the colour of
the clearest film and to the slide's own mid-tones (adapted_to_slide). To reproduce that
on a monitor, the appearance of each colour
under the slide viewing conditions (CIECAM16: lightness J, chroma C, hue h) is rebuilt
under monitor viewing conditions.
"""
from dataclasses import dataclass
from functools import lru_cache

import colour
import numpy as np

from . import spectra

CAT16 = colour.adaptation.CAT_CAT16
CAT16_INV = np.linalg.inv(CAT16)
D65_XYZ = colour.xy_to_XYZ(colour.CCS_ILLUMINANTS["CIE 1931 2 Degree Standard Observer"]["D65"]) * 100


# CIECAM16 surrounds. "Light box": a slide on a light table is seen in a dim surround, not in
# the room's light: Hunt's appearance model puts large transparencies on light boxes with
# television in a dim room for brightness induction (N_b 25, against 75 for normal scenes), and
# a loupe or a masked viewer shows the slide against dark. Lightness is that of a dim surround
# (c 0.59), which takes the edge off the film's contrast as the eye does (mid-tones 1.05-1.19
# times as steep as a neutral rendering instead of 1.18-1.36, and no shadows crushed to black);
# colour induction stays that of an average one (N_c 1), the colour the slides were judged with.
SURROUNDS = {**colour.VIEWING_CONDITIONS_CAM16,
             "Light box": type(colour.VIEWING_CONDITIONS_CAM16["Dim"])(F=0.9, c=0.59, N_c=1.0)}


@dataclass
class Viewing:
    name: str
    light: np.ndarray       # spectral power of the viewing light
    surround: str           # SURROUNDS: Dark, Dim, Average or Light box
    adaptation: float       # how fully the eye adapts to the light's colour (0-1)
    flare: float            # stray light, as a fraction of the mean image luminance


VIEWINGS = {
    # Carousel-style projector, quartz-halogen lamp, dark room.
    "projector": Viewing("projector", spectra.projector_lamp(3350), "Dark", 0.92, 0.012),
    # 5000 K light table (ANSI/ISO transparency viewer light); the slide lies on the lit
    # glass and is looked at closely with a loupe, so it fills the view against dark.
    "lightbox": Viewing("lightbox", spectra.daylight(5000), "Light box", 1.0, 0.004),
}

# A laptop or monitor in a normally lit room.
DISPLAY = dict(white_cd_m2=160.0, surround="Average")


def dye_transmittance_xyz(dyes, film, light):
    """XYZ (white = Y 1 for an empty light) of light passing through dye amounts (n, 3)."""
    spectrum = dyes @ film.dyes.T  # one (n, wavelengths) array, worked in place: density, then light through it
    spectrum += film.base
    np.negative(spectrum, out=spectrum)
    np.power(10.0, spectrum, out=spectrum)
    spectrum *= light
    return spectrum @ spectra.CMFS / (light @ spectra.YBAR)


def adapted_to_slide(xyz, gain, knee=0.5):
    """What an eye adapted to the slide's mid-tones, not to its clearest film, sees.

    A slide exposed by the meter puts a grey card near density 1: only 10 % of the light
    gets through, yet looking at a slide the eye settles on its mid-tones and that grey reads
    as mid-grey, while clear film glows like a highlight. Light is scaled by gain; whatever
    passes the knee (fraction of white) rolls off smoothly so clear film still meets the
    screen's white. xyz is relative to clear film, Y = 100.
    """
    if gain <= 1.0:
        return xyz
    y = xyz[..., 1:2] / 100.0 * gain
    a = (gain - 1.0) / ((1.0 - knee) * (gain - knee))
    rolled = np.where(y > knee, knee + (y - knee) / (1.0 + a * (y - knee)), y)
    return xyz * (gain * rolled / np.maximum(y, 1e-9))


def slide_to_xyz(dyes, film, viewing, gain=1.0, chunk=1 << 18):
    """Spectral transmission of the whole slide, in chunks to bound memory, as the adapted eye sees it."""
    flat = dyes.reshape(-1, 3)
    out = np.empty((len(flat), 3), np.float32)
    for i in range(0, len(flat), chunk):
        out[i:i + chunk] = dye_transmittance_xyz(flat[i:i + chunk].astype(np.float64), film, viewing.light)
    white = dye_transmittance_xyz(np.zeros((1, 3)), film, viewing.light)[0]
    xyz = out.reshape(dyes.shape)
    xyz = xyz + viewing.flare * xyz.reshape(-1, 3).mean(axis=0)
    return adapted_to_slide(xyz / white[1] * 100.0, gain), white / white[1] * 100.0


def _adapt(xyz, white, degree):
    """Partial CAT16 adaptation from the slide's white to D65."""
    lms_w = CAT16 @ white
    lms_r = CAT16 @ D65_XYZ
    gain = degree * lms_r / lms_w + (1 - degree)
    return xyz @ (CAT16_INV @ np.diag(gain) @ CAT16).T


def _cam16(viewing_cd_m2, surround):
    return dict(XYZ_w=D65_XYZ, L_A=viewing_cd_m2 * 0.2, Y_b=20.0,
                surround=SURROUNDS[surround], discount_illuminant=True)


def to_display(xyz, white, viewing, display_space, chunk=1 << 20):
    """Appearance match from slide viewing to a monitor; returns linear display RGB."""
    shape = xyz.shape
    flat = _adapt(xyz.reshape(-1, 3).astype(np.float64), white, viewing.adaptation)
    # Lightness and chroma are matched relatively: the surround and the light's colour carry
    # over, the absolute level does not. Matching across 1000 vs 160 cd/m2 would lift the
    # shadows and, through the Hunt effect, add about 16 % colour that no scan or print of a
    # slide shows; a viewer adapts to the light box as to the screen.
    src = _cam16(DISPLAY["white_cd_m2"], viewing.surround)
    dst = _cam16(DISPLAY["white_cd_m2"], DISPLAY["surround"])
    out = np.empty_like(flat)
    for i in range(0, len(flat), chunk):
        block = flat[i:i + chunk]
        with np.errstate(all="ignore"):
            spec = colour.XYZ_to_CAM16(block, **src)
            out[i:i + chunk] = _cam16_to_rgb(spec.J, spec.C, spec.h, dst, display_space)
    return out.reshape(shape)


@lru_cache(maxsize=4)
def _cusps(space_name):
    """Hue, lightness J and chroma C of the display's most colourful colours (CAM16 on the
    monitor): the rim of its gamut, where one channel is 0 and another 1."""
    space = colour.RGB_COLOURSPACES[space_name]
    t = np.linspace(0.0, 1.0, 241)[:, None]
    zero, one = np.zeros_like(t), np.ones_like(t)
    rim = np.concatenate([np.hstack(e) for e in ((one, t, zero), (1 - t, one, zero), (zero, one, t),
                                                  (zero, 1 - t, one), (t, zero, one), (one, zero, 1 - t))])
    spec = colour.XYZ_to_CAM16(rim @ space.matrix_RGB_to_XYZ.T * 100.0,
                               **_cam16(DISPLAY["white_cd_m2"], DISPLAY["surround"]))
    order = np.argsort(spec.h)
    return spec.h[order], spec.J[order], spec.C[order]


def _cam16_to_rgb(j, c, h, dst, space):
    """CAM16 back to display RGB. A colour beyond the display keeps its hue; one darker than
    the display's most colourful colour of that hue loses chroma only, a lighter one gives up
    some lightness too, moving toward that colour, so bright yellows and oranges stay vivid
    instead of washing out toward white."""
    def rgb_for(lightness, chroma, hue):
        spec = colour.CAM_Specification_CAM16(J=lightness, C=chroma, h=hue)
        with np.errstate(all="ignore"):
            xyz = colour.CAM16_to_XYZ(spec, **dst) / 100.0
        return np.nan_to_num(xyz @ space.matrix_XYZ_to_RGB.T, nan=-1.0)

    j = np.nan_to_num(j); c = np.nan_to_num(c); h = np.nan_to_num(h)
    rgb = rgb_for(j, c, h)
    bad = (rgb.min(axis=1) < -1e-4) | (rgb.max(axis=1) > 1.0001)
    bad &= j < 100.0
    if bad.any():
        jb, cb, hb = j[bad], c[bad], h[bad]
        hues, cusp_j, _ = _cusps(space.name)
        anchor = np.minimum(jb, np.interp(hb, hues, cusp_j, period=360.0))
        lo, hi = np.zeros_like(cb), np.ones_like(cb)
        for _ in range(12):
            mid = (lo + hi) / 2
            test = rgb_for(anchor + (jb - anchor) * mid, cb * mid, hb)
            ok = (test.min(axis=1) >= -1e-4) & (test.max(axis=1) <= 1.0001)
            lo = np.where(ok, mid, lo)
            hi = np.where(ok, hi, mid)
        rgb[bad] = rgb_for(anchor + (jb - anchor) * lo, cb * lo, hb)
    return np.clip(rgb, 0.0, 1.0)
