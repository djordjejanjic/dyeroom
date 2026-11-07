"""Spectral foundations: wavelength grid, CIE observer, light sources, spectral upsampling.

Everything in the simulator is computed on one 380-780 nm grid at 5 nm steps,
the same grid Sunday 64's data-sheet curves were digitised on.
"""
from functools import lru_cache
from pathlib import Path

import colour
import numpy as np

WL = np.arange(380.0, 781.0, 5.0)
SHAPE = colour.SpectralShape(380, 780, 5)
CMFS = colour.MSDS_CMFS["CIE 1931 2 Degree Standard Observer"].copy().align(SHAPE).values
YBAR = CMFS[:, 1]

REC2020 = colour.RGB_COLOURSPACES["ITU-R BT.2020"]
P3 = colour.RGB_COLOURSPACES["Display P3"]
SRGB = colour.RGB_COLOURSPACES["sRGB"]


def normalise(spd):
    """Scale a spectral power distribution so a perfect white under it has Y = 1."""
    return spd / (spd @ YBAR)


def planck(temperature):
    """Relative spectral radiance of a black body (Planck's law)."""
    lam = WL * 1e-9
    c2 = 1.438776877e-2  # second radiation constant, m*K
    return normalise(1.0 / (lam ** 5 * np.expm1(c2 / (lam * temperature))))


def daylight(cct):
    """CIE D-series daylight at a correlated colour temperature."""
    xy = colour.temperature.CCT_to_xy_CIE_D(cct * 1.4388 / 1.4380)
    sd = colour.sd_CIE_illuminant_D_series(xy).align(SHAPE)
    return normalise(sd.values)


def scene_light(cct):
    """Tungsten-like sources below 4000 K are black bodies, above that daylight."""
    return planck(cct) if cct < 4000 else daylight(cct)


def xyz_of(spd):
    return spd @ CMFS / (spd @ YBAR)


# Schott KG3 heat-absorbing glass (2 mm), sampled from the Schott/Newport data sheet.
_KG3_WL = np.arange(380, 781, 20)
_KG3_T = np.array([0.862, 0.845, 0.821, 0.824, 0.825, 0.833, 0.844, 0.838, 0.837, 0.848, 0.836,
                   0.809, 0.766, 0.709, 0.640, 0.558, 0.471, 0.382, 0.290, 0.221, 0.158])


def lens_transmission(cutoff=400.0, width=8.0):
    """Generic multi-coated glass lens: transparent in the visible, absorbing near-UV."""
    return 0.5 * (1 + np.tanh((WL - cutoff) / width))


def projector_lamp(temperature=3350.0):
    """Quartz-halogen slide-projector lamp (ELH/EXR class) behind a KG3 heat filter and lens."""
    kg3 = np.interp(WL, _KG3_WL, _KG3_T)
    return normalise(planck(temperature) * kg3 * lens_transmission())


def conversion_filter(mired_shift):
    """Ideal colour-conversion filter (80A = -131, 80B = -112, 80C = -81, 85B = +131 mired).

    Transmission follows the ratio of two Planck curves, which is what a conversion
    filter is designed to approximate; normalised to peak 1.
    """
    if mired_shift == 0:
        return np.ones_like(WL)
    t1 = 3400.0
    t2 = 1e6 / (1e6 / t1 + mired_shift)
    lam = WL * 1e-9
    c2 = 1.438776877e-2
    ratio = np.expm1(c2 / (lam * t1)) / np.expm1(c2 / (lam * t2))
    return ratio / ratio.max()


# Colour-conversion filters by their standard designations, as mired shifts.
FILTERS = {"none": 0, "80A": -131, "80B": -112, "80C": -81, "80D": -56, "82C": -45, "82B": -32,
           "82A": -21, "81A": +18, "81B": +27, "81C": +35, "81EF": +53, "85B": +131}
_DAYLIGHT_FILTERS = [name for name in FILTERS if name[:2] in ("80", "81", "82")]


def pick_filter(cct, target=5500.0):
    """The filter a daylight-film photographer would screw on: blue 80/82 series for warm
    light, amber 81 series for cold light, nothing when the light is close enough
    (within 20 mired). Picks the one leaving the light closest to 5500 K."""
    want = 1e6 / target - 1e6 / cct
    if abs(want) < 20:
        return "none"
    return min(_DAYLIGHT_FILTERS, key=lambda name: abs(FILTERS[name] - want))


# --- Spectral upsampling (Jakob & Hanika 2019, "A Low-Dimensional Function Space for
# Efficient Spectral Upsampling"). Reflectance is a sigmoid of a quadratic in wavelength,
# which always gives smooth, physically bounded spectra. Solved here with a vectorised
# Gauss-Newton continuation over a whole RGB lattice at once.

_X = (WL - WL[0]) / (WL[-1] - WL[0])
_BASIS = np.stack([_X ** 2, _X, np.ones_like(_X)], axis=1)


def _sigmoid(z):
    return 0.5 + z / (2.0 * np.sqrt(1.0 + z * z))


def _dsigmoid(z):
    return 0.5 * (1.0 + z * z) ** -1.5


D65 = normalise(colour.SDS_ILLUMINANTS["D65"].copy().align(SHAPE).values)


def _rec2020_weights(light=None, wavelengths=WL):
    """Matrix W such that white-balanced linear Rec.2020 RGB = reflectance @ W.

    Under D65 by default. Under another light it is the colour a surface shows in that light
    after white balance, which carries the light's white to D65 (CAT16, as a camera's white
    balance and our raw conversion do): a surface is recovered as what it is under the
    scene's own light, not under daylight and then lit again.
    """
    cmfs = np.stack([np.interp(wavelengths, WL, CMFS[:, k]) for k in range(3)], axis=1)
    xyz = np.interp(wavelengths, WL, D65 if light is None else light)[:, None] * cmfs
    if light is not None:
        cat = colour.adaptation.matrix_chromatic_adaptation_VonKries(xyz_of(light), xyz_of(D65), transform="CAT16")
        xyz = xyz @ cat.T
    w = xyz @ REC2020.matrix_XYZ_to_RGB.T
    return w / w.sum(axis=0)  # a perfect white reflector maps exactly to (1, 1, 1)


# Violet below 430 nm: the eye barely sees it, the slide film's blue layer does. A reflectance
# has no reason to rise there above its own level at 440 nm unless the colour needs it, so
# a rise costs the fit a little; otherwise saturated reds grow violet tails (the quadratic
# opens upward) and turn pink on film. (Rising deep reds are real: red pigments do that.)
EDGE_PENALTY = 0.005
_EDGE_IDX = np.flatnonzero(WL < 430)
_EDGE_W = (430 - WL[_EDGE_IDX]) / 50
_EDGE_REF = np.full(len(_EDGE_IDX), int(np.flatnonzero(WL == 440)[0]))


def fit_reflectances(rgb, steps=16, iterations=6, edge_penalty=EDGE_PENALTY, light=None):
    """Find smooth reflectance spectra (N, 81) reproducing white-balanced linear Rec.2020 RGB
    targets (N, 3) seen under light (default D65)."""
    w = _rec2020_weights(light)
    pen = np.sqrt(edge_penalty) * _EDGE_W
    target = np.clip(rgb, 0.002, 0.998)
    grey = target.mean(axis=1, keepdims=True)
    s0 = 2 * grey - 1
    c = np.zeros((len(target), 3))
    c[:, 2:3] = s0 / np.sqrt(1 - s0 ** 2)
    for step in range(1, steps + 1):
        goal = grey + (target - grey) * step / steps
        for _ in range(iterations):
            z = c @ _BASIS.T
            s, ds = _sigmoid(z), _dsigmoid(z)
            rise = s[:, _EDGE_IDX] - s[:, _EDGE_REF]
            active = rise > 0
            residual = np.concatenate([s @ w - goal, np.where(active, rise, 0) * pen], axis=1)
            d_rise = (ds[:, _EDGE_IDX, None] * _BASIS[_EDGE_IDX] - ds[:, _EDGE_REF, None] * _BASIS[_EDGE_REF])
            jac = np.concatenate([np.einsum("nl,li,lm->nim", ds, w, _BASIS),
                                  np.where(active[..., None], d_rise, 0) * pen[:, None]], axis=1)
            jtj = np.einsum("nim,nik->nmk", jac, jac) + 1e-9 * np.eye(3)
            delta = np.linalg.solve(jtj, -np.einsum("nim,ni->nm", jac, residual)[..., None])[..., 0]
            norm = np.linalg.norm(delta, axis=1, keepdims=True)
            c += delta * np.minimum(1.0, 50.0 / np.maximum(norm, 1e-12))
    spectra = _sigmoid(c @ _BASIS.T)
    error = np.abs(spectra @ w - target).max(axis=1)
    return spectra, error


# --- Natural reflectances (Otsu, Yamamoto & Hachisuka 2018, "Reproducing Spectral
# Reflectances From Tristimulus Colours"). Chromaticity space is split into regions, each
# with three basis spectra and a mean learned from measured reflectances of real objects.
# Real blue materials keep rising into the far red, where the slide film's red layer still
# sees: the smoothest spectrum loses that tail, so blues under-exposed the red layer by up
# to 0.5 log and came out cyan on the film, and reds leaked into the green layer and went
# orange. Natural spectra cut the layer-exposure error about threefold on the ColorChecker
# and on the CIE and NIST CQS test colours (tools/chart.py). Colours beyond what real
# surfaces reflect cannot be met by a clipped natural spectrum; there the smoothest
# spectrum takes over.
#
# A camera cannot tell a blue sky (scattered light with no deep red) from blue paint or
# cloth (which reflect deep red too). Natural spectra turn skies grey-violet on the film,
# smooth ones turn them cyan; blues take a mix, mostly smooth.
BLUE_NATURAL_SHARE = 0.35

def natural_reflectances(rgb, light=None):
    """Reflectance spectra (N, 81) for white-balanced linear Rec.2020 RGB (N, 3) seen under
    light (default D65), clipped to [0, 1]."""
    from colour.recovery.otsu2018 import DATASET_REFERENCE_OTSU2018 as data, SPECTRAL_SHAPE_OTSU2018
    wl = SPECTRAL_SHAPE_OTSU2018.wavelengths
    to_rgb = _rec2020_weights(light, wl)
    basis, means = data.basis_functions, data.means
    inverse = np.linalg.inv(np.einsum("cil,lj->cji", basis, to_rgb))
    rgb = np.asarray(rgb, float)
    xyz = rgb @ REC2020.matrix_RGB_to_XYZ.T  # the region is chosen by the colour's chromaticity
    xy = xyz[:, :2] / np.maximum(xyz.sum(axis=1, keepdims=True), 1e-12)
    cluster = np.array([data.select(p) for p in xy])
    weights = np.einsum("nij,nj->ni", inverse[cluster], rgb - means[cluster] @ to_rgb)
    recovered = np.clip(np.einsum("ni,nil->nl", weights, basis[cluster]) + means[cluster], 0.0, 1.0)
    above = np.searchsorted(wl, WL).clip(1, len(wl) - 1)  # to 5 nm, flat beyond 730 nm
    t = np.clip((WL - wl[above - 1]) / (wl[above] - wl[above - 1]), 0.0, 1.0)
    return recovered[:, above - 1] * (1 - t) + recovered[:, above] * t


# Scene lights (K) the lattice is solved under; a light in between blends the two nearest in
# mired. From 5000 K up, surfaces are solved under D65: daylight of any kind changes the
# result by less than 0.1 dE (tested on 68 measured surfaces), lamplight by up to 3 on average.
LATTICE_LIGHTS = (2400, 2700, 3000, 3400, 3900, 4500)
_D65_MIRED = 1e6 / 5000.0


def lattice_lights(cct):
    """[(lattice light in K or None for D65, share)] for a scene lit at cct (None: daylight)."""
    if cct is None or cct >= 5000:
        return [(None, 1.0)]
    mired = 1e6 / max(cct, LATTICE_LIGHTS[0])
    anchors = [(1e6 / k, k) for k in LATTICE_LIGHTS] + [(_D65_MIRED, None)]
    for (m_hi, k_hi), (m_lo, k_lo) in zip(anchors, anchors[1:]):
        if m_lo <= mired <= m_hi:
            t = (m_hi - mired) / (m_hi - m_lo)
            return [(k, share) for k, share in ((k_hi, 1.0 - t), (k_lo, t)) if share > 0]
    return [(LATTICE_LIGHTS[0], 1.0)]


@lru_cache(maxsize=8)
def reflectance_lattice(size=33, cct=None):
    """Reflectance spectra for every node of a size^3 lattice over white-balanced Rec.2020
    [0, 1]^3, as surfaces seen under a scene light at cct K (None: D65). Cached on disk."""
    light = None if cct is None else scene_light(cct)
    cache = (Path(__file__).parent / "data" / "cache"
             / f"reflectance_lattice_{size}_{'d65' if cct is None else f'{cct:.0f}K'}"
               f"_natural{BLUE_NATURAL_SHARE:g}_p{EDGE_PENALTY:g}_v6.npz")
    if cache.exists():
        data = np.load(cache)
        return data["spectra"], data["error"]
    axis = np.linspace(0.0, 1.0, size)
    grid = np.stack(np.meshgrid(axis, axis, axis, indexing="ij"), axis=-1).reshape(-1, 3)
    w = _rec2020_weights(light)
    smooth, _ = fit_reflectances(grid, light=light)
    xyz = grid @ REC2020.matrix_RGB_to_XYZ.T
    natural = natural_reflectances(grid, light)
    miss = np.abs(natural @ w - grid).max(axis=1)
    lab = colour.XYZ_to_Lab(xyz, REC2020.whitepoint)
    hue_from_blue = np.abs((np.degrees(np.arctan2(lab[:, 2], lab[:, 1])) - 262 + 180) % 360 - 180)
    blueness = (np.clip(1 - (hue_from_blue - 45) / 20, 0, 1)        # hues 217-307, soft edges
                * np.clip((np.hypot(lab[:, 1], lab[:, 2]) - 3) / 7, 0, 1))  # not near-greys
    natural_share = (np.clip(1 - (miss - 0.004) / 0.02, 0.0, 1.0)  # fade over by misfit
                     * (1 - blueness * (1 - BLUE_NATURAL_SHARE)))[:, None]
    spectra = natural * natural_share + smooth * (1 - natural_share)
    error = np.abs(spectra @ w - grid).max(axis=1)
    spectra = spectra.reshape(size, size, size, len(WL)).astype(np.float32)
    error = error.reshape(size, size, size)
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache, spectra=spectra, error=error)
    return spectra, error


def trilinear(lut, rgb):
    """Sample a (n, n, n, k) lattice over [0, 1]^3 at rgb (..., 3) with trilinear interpolation."""
    n = lut.shape[0]
    pos = np.clip(rgb, 0.0, 1.0) * (n - 1)
    i0 = np.minimum(pos.astype(np.int32), n - 2)
    f = (pos - i0).astype(lut.dtype)
    out = 0.0
    for dr in (0, 1):
        wr = f[..., 0] if dr else 1 - f[..., 0]
        for dg in (0, 1):
            wg = f[..., 1] if dg else 1 - f[..., 1]
            for db in (0, 1):
                wb = f[..., 2] if db else 1 - f[..., 2]
                out = out + (wr * wg * wb)[..., None] * lut[i0[..., 0] + dr, i0[..., 1] + dg, i0[..., 2] + db]
    return out
