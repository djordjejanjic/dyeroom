"""Exposure in the camera and the film's reversal process, step by step, on a whole image."""
from dataclasses import dataclass

import colour
import numpy as np
from scipy import ndimage

from . import spectra
from .film import INHIBITION

# Light scattering inside the emulsion (irradiation). A turbid layer spreads light with a
# roughly exponential point spread (Frieser), MTF 1 / (1 + (f / f0)^2), drawn here as three
# Gaussians (weight, sigma in micrometres; within 0.006 of that MTF up to 200 cycles/mm).
# f0 and the inhibitor spread in Process are fitted together to the film's published MTF
# (the data sheets, SOURCES.md: 123 % at 7-11 cycles/mm from edge effects, 69 % at 30,
# 31 % at 50, 12 % at 80; tools/mtf.py). The maker publishes one diffuse visual curve, so every
# layer gets the same spread.
SCATTER_F0 = 26.7  # cycles/mm
_SCATTER_GAUSSIANS = ((0.1048, 1.628), (0.4251, 4.857), (0.4701, 10.864))

# The film's reciprocity, from its data sheet: nothing from 1/10,000 to 1/100 s; at 1/10 s
# +1/3 stop with a CC05R filter, i.e. the red layer loses 0.10 log exposure and the green and
# blue layers 0.05. The maker calls 1 s and longer "not recommended" and gives no figures; the
# loss is continued at the same rate per decade, which is a guess. log10 exposure lost per layer.
_RECIPROCITY_T = np.log10([0.01, 0.1])
_RECIPROCITY_LOSS = np.array([[0.0, 0.0, 0.0], [0.10, 0.05, 0.05]])

GRAIN_APERTURE_UM2 = np.pi * 24.0 ** 2  # the data sheet's RMS granularity is read through a 48 um aperture
DYE_CLOUD_UM = 4.5  # blur of the grain pattern: dye clouds plus loupe or scanner optics


@dataclass
class Process:
    first_developer: float = 1.0   # first-developer time relative to the process's standard time
    inhibitor_spread_um: float = 40.0  # lateral diffusion length of iodide in the first developer
    inhibitor_local: float = 0.21  # share of inhibition acting in place (rest diffuses sideways)
    grain: bool = True
    seed: int = 1935               # a fixed seed: the grain is repeatable


def gamut_to_positive(rgb):
    """Pull colours outside Rec.2020 (negative components) toward grey at equal luminance."""
    y = rgb @ np.array([0.2627, 0.6780, 0.0593], dtype=rgb.dtype)
    low = rgb.min(axis=-1)
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.where(low < 0, y / np.maximum(y - low, 1e-9), 1.0)
    t = np.clip(np.nan_to_num(t, nan=0.0), 0.0, 1.0)[..., None]
    return np.clip(y[..., None] + (rgb - y[..., None]) * t, 0.0, None)


def layer_exposure(rgb, film, taking_light, scene_cct=None):
    """Spectral exposure of each layer, H = integral of reflectance * light * sensitivity.

    rgb: scene-linear, white-balanced Rec.2020 (0.18 = grey card), of a scene lit at
    scene_cct K (None: daylight); surfaces are recovered as they look under that light, so
    a lamplit scene is not first turned into daylight colours. Each pixel's colour becomes a smooth
    reflectance spectrum at its own brightness (dark reds get the broad spectra of dark
    pigments, bright ones sharper spectra). Very dark and bright pixels borrow the spectral
    shape of the same colour at the nearest safe brightness and are scaled, since light adds
    linearly. Near a reflectance of 1 the only spectra that still reach a saturated colour are
    steep and lopsided: a bright blue sky would grow a red tail there and turn purple on the
    film, so the shape is never taken from above 0.6. Returns log10 H per layer, 0 = 18 %
    grey exposed to 1 under D55.
    """
    weight = taking_light[:, None] * film.sensitivity
    response = sum(share * (spectra.reflectance_lattice(cct=cct)[0] @ weight)
                   for cct, share in spectra.lattice_lights(scene_cct))
    rgb = gamut_to_positive(rgb)
    peak = np.maximum(rgb.max(axis=-1, keepdims=True), 1e-7)
    lookup = np.clip(peak, 0.25, 0.6)
    h = (peak / lookup) * spectra.trilinear(response.astype(np.float32), rgb * (lookup / peak))
    return np.log10(np.maximum(h, 1e-7))


def metered_grey_log_h(film):
    """Where a metered grey card lands on the film, from the reversal ISO speed method.

    Speed points: exposures giving visual density 0.2 and 2.0 above minimum; H_m is their
    geometric mean and S = 10 / H_m. A reflected-light meter (K = 12.5, q = 0.65) gives a
    metered surface H = 8.1 / S = 0.81 H_m.
    """
    from .viewing import dye_transmittance_xyz
    axis = np.linspace(-3.0, 2.0, 2001)
    remaining = 1.0 - film.datasheet_developed(np.repeat(axis[:, None], 3, 1))
    y = dye_transmittance_xyz(remaining * film.dmax, film, spectra.daylight(5000))[:, 1]
    density = -np.log10(y)
    above_min = density - density.min()
    h_x = np.interp(-0.2, -above_min, axis)
    h_s = np.interp(-2.0, -above_min, axis)
    return 0.5 * (h_x + h_s) + np.log10(8.125 / 10.0)


def grey_balance(film):
    """Layer speed offsets that make a metered grey card neutral under 5000 K viewing.

    The maker balanced every emulsion batch this way; it also absorbs small digitisation
    offsets between the three published curves. Green is the reference layer.
    """
    from scipy import optimize
    from .viewing import dye_transmittance_xyz
    light = spectra.daylight(5000)
    grey = metered_grey_log_h(film)
    target = colour.XYZ_to_xy(dye_transmittance_xyz(np.zeros((1, 3)), film, light)[0])

    def chroma_error(offset_rb):
        log_h = grey + np.array([offset_rb[0], 0.0, offset_rb[1]])
        dyes = (1.0 - film.datasheet_developed(log_h[None])) * film.dmax
        return colour.XYZ_to_xy(dye_transmittance_xyz(dyes, film, light)[0]) - target

    offset_rb = optimize.fsolve(chroma_error, [0.0, 0.0])
    return np.array([offset_rb[0], 0.0, offset_rb[1]])


def reciprocity(log_h, exposure_time):
    if not exposure_time or exposure_time <= 0.01:
        return log_h
    t = np.log10(exposure_time)
    loss = np.array([np.interp(t, _RECIPROCITY_T, _RECIPROCITY_LOSS[:, k],
                               right=None) for k in range(3)])
    if t > _RECIPROCITY_T[-1]:
        slope = (_RECIPROCITY_LOSS[-1] - _RECIPROCITY_LOSS[-2]) / (_RECIPROCITY_T[-1] - _RECIPROCITY_T[-2])
        loss = _RECIPROCITY_LOSS[-1] + slope * (t - _RECIPROCITY_T[-1])
    return log_h - loss


def irradiation(log_h, um_per_px):
    """Blur each layer's exposure by light scattering in the emulsion."""
    h = 10.0 ** log_h
    for k in range(3):
        layer, spread = h[..., k], 0.0
        for weight, sigma_um in _SCATTER_GAUSSIANS:
            sigma = sigma_um / um_per_px
            spread = spread + weight * (ndimage.gaussian_filter(layer, sigma) if sigma > 0.25 else layer)
        h[..., k] = spread
    return np.log10(np.maximum(h, 1e-6))


def first_developer(log_h, film, process, um_per_px):
    """Black-and-white development of the negative silver image in all three layers.

    Developing silver releases iodide, which slows development in the same layer and
    the neighbouring layers (interimage effect) and diffuses sideways (adjacency or edge
    effect). The inhibitor field is estimated from the silver that starts forming.
    """
    silver = film.datasheet_developed(log_h)
    sigma = process.inhibitor_spread_um / um_per_px
    if sigma > 0.25:
        spread = np.stack([ndimage.gaussian_filter(silver[..., k], sigma) for k in range(3)], -1)
        silver = process.inhibitor_local * silver + (1 - process.inhibitor_local) * spread
    inhibitor = silver @ INHIBITION
    return film.developed_fraction(log_h - inhibitor, process.first_developer)


def grain_count_per_um2(film, viewing_light):
    """Number of independent dye-forming grains per square micrometre, from the data sheet's RMS 10.

    Selwyn's law: density fluctuation sigma scales as 1/sqrt(area). Remaining grains in a
    layer are binomial, so sigma of the remaining fraction is sqrt(R(1-R)/N).
    """
    from .viewing import dye_transmittance_xyz
    log_h = np.linspace(-2.0, 1.0, 601)
    remaining = 1.0 - film.developed_fraction(np.repeat(log_h[:, None], 3, 1))
    y = dye_transmittance_xyz(remaining * film.dmax, film, viewing_light)[:, 1]
    density = -np.log10(y)
    i = np.argmin(np.abs(density - 1.0))  # gross diffuse visual density 1.0
    r = remaining[i]
    grad = np.empty(3)
    for k in range(3):
        bumped = r.copy(); bumped[k] += 1e-4
        y2 = dye_transmittance_xyz((bumped * film.dmax)[None], film, viewing_light)[0, 1]
        grad[k] = (-np.log10(y2) - density[i]) / 1e-4
    variance_times_n = np.sum(grad ** 2 * r * (1 - r))
    sigma = film.rms_granularity / 1000.0
    return variance_times_n / (sigma ** 2 * GRAIN_APERTURE_UM2)


def reversal_and_dyes(developed, film, process, um_per_px, grains_per_um2):
    """Re-exposure, colour development, bleach and fix: the silver halide that the first
    developer left behind becomes dye, layer by layer.

    1. Red light through the base fogs the remaining halide of the red layer;
       the cyan developer couples it into cyan dye.
    2. Blue light from the emulsion side fogs the remaining halide of the top layer
       (the yellow filter layer shields the green layer); the yellow developer makes yellow dye.
    3. The magenta developer carries a chemical fogging agent and turns all halide still
       left, in the green layer, into magenta dye.
    4. Bleach converts all silver (both images and the yellow filter layer) back to halide;
       fix dissolves it. Only the three dyes remain.
    """
    remaining = 1.0 - developed
    if process.grain:
        n = grains_per_um2 * um_per_px ** 2
        rng = np.random.default_rng(process.seed)
        noise = rng.standard_normal(remaining.shape, dtype=np.float32)
        cloud = DYE_CLOUD_UM / um_per_px
        if cloud > 0.3:  # blurring keeps low-frequency power, so the data sheet's 48 um RMS stays calibrated
            noise = np.stack([ndimage.gaussian_filter(noise[..., k], cloud) for k in range(3)], -1)
        remaining = remaining + noise * np.sqrt(np.clip(remaining * (1 - remaining), 0, None) / n)
        remaining = np.clip(remaining, 0.0, 1.0)
    cyan = remaining[..., 0] * film.dmax[0]      # red layer -> cyan developer
    yellow = remaining[..., 2] * film.dmax[2]    # blue layer -> yellow developer
    magenta = remaining[..., 1] * film.dmax[1]   # green layer -> fogging magenta developer
    return np.stack([cyan, magenta, yellow], axis=-1).astype(np.float32)
