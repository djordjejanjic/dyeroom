"""Sunday 64's film as a physical object: its layers, grains, dyes, and how its grains develop.

Measured data, the maker's data sheet for the film (SOURCES.md), digitised from its vector
drawings (tools/digitise_sunday64.py): spectral sensitivity of the three layers, the reversal
characteristic curves (Status A densities of the whole film) and the spectral density of
the three dyes. The curves are split into the amount of each dye by solving, at every
exposure, for the cyan, magenta and yellow that give the data sheet's three Status A readings through
the measured dye spectra: each reading sees all three dyes, so this is done on the spectra,
not with a fixed 3 x 3 matrix. The processed base is a smooth density meeting the data
sheet's minimum densities.

Physical model fitted to that data, per layer:

* Latent image (quantum "hit" theory, Silberstein): a grain that catches photons at a
  mean rate lambda = a * H absorbs n photons with Poisson probability
  P(n) = lambda^n e^-lambda / n!. Each layer is a blend of two emulsions whose grain
  cross-sections a are log-normally distributed (fast and slow grains).
* First-developer kinetics: a grain carrying n absorbed photons develops at a
  first-order rate k(n), so the chance it has developed after time t is 1 - e^(-k(n) t).
  Grains with a full latent image develop fast, sub-latent grains slowly, and unexposed
  grains only as chemical fog. Longer first development (push processing) therefore
  develops weaker latent images: that is where push speed and weaker blacks come from.
* Development inhibitors (iodide released by developing silver) diffuse within and
  between layers and slow development where neighbouring silver is forming. These are
  the film's interimage and edge (adjacency) effects.

The data-sheet curves are measured on grey scales, where inhibition is already acting,
so the intrinsic (uninhibited) curves are recovered first and the grain model is
fitted to those.
"""
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import optimize, special, stats

from . import spectra

DATA = Path(__file__).parent / "data" / "sunday64.json"
STATUS_A = Path(__file__).parent / "data" / "status_a.json"
LOG_H = np.round(np.arange(-3.5, 1.5001, 0.01), 4)  # log10 lux-seconds, the data sheet's axis
CACHE = Path(__file__).parent / "data" / "cache"

QUANTUM_REQUIREMENT = 4  # absorbed photons for a stable, fast-developing latent image
K_LATENT = 8.0           # first-order development rate of a full latent image (per standard time)
K_FOG = 0.004            # chemical fog rate of an unexposed grain (with an induction period)
_GH_X, _GH_W = np.polynomial.hermite_e.hermegauss(28)
_GH_W = _GH_W / _GH_W.sum()

# Development-inhibitor transfer in the first developer, log10 exposure units per unit
# developed fraction. Rows: donor layer (R, G, B); columns: receiving layer. The film's
# layer order, top to bottom: blue, yellow filter, green, red. Neighbours exchange more.
INHIBITION = np.array([
    [0.35, 0.21, 0.05],
    [0.21, 0.35, 0.12],
    [0.05, 0.12, 0.28],
])
# The maker never published the film's interimage strength. Without it the dyes alone render
# most colours below the scene's chroma; at this strength reds, greens and oranges come out
# above it while denser, which is how the film was designed to look (tools/chart.py sweeps it).


@dataclass
class Film:
    sensitivity: np.ndarray   # (81, 3) linear spectral sensitivity of R, G, B layers
    dyes: np.ndarray          # (81, 3) spectral density per unit amount of cyan, magenta, yellow
    base: np.ndarray          # (81,) density of processed base + minimum stain
    log_h: np.ndarray         # (N,) log10 exposure axis, 0 = 18 % grey under D55
    curves: np.ndarray        # (N, 3) data-sheet reversal curves: dye amount vs log exposure
    dmax: np.ndarray          # (3,) maximum dye amount per layer
    developed: np.ndarray     # (N, 3) data-sheet developed fraction (inhibition included)
    grain_params: np.ndarray  # (3, 6) fitted emulsion parameters per layer
    rms_granularity: float = 10.0  # the data sheet's diffuse RMS x1000 at D = 1.0, 48 um aperture

    def developed_fraction(self, log_h, development_time=1.0):
        """Fraction of silver halide developed in the first developer, per layer (..., 3)."""
        out = np.empty(np.shape(log_h))
        for k in range(3):
            axis, table = _development_table(self.grain_params[k], development_time)
            out[..., k] = np.interp(log_h[..., k], axis, table)
        return out

    def datasheet_developed(self, log_h):
        out = np.empty(np.shape(log_h))
        for k in range(3):
            out[..., k] = np.interp(log_h[..., k], self.log_h, self.developed[:, k])
        return out


def _extrapolate_dyes(dyes):
    """Dye densities are published 425-695 nm; hold the violet end, let the far red decay."""
    out = dyes.copy()
    for k in range(3):
        valid = np.flatnonzero(np.isfinite(dyes[:, k]))
        lo, hi = valid[0], valid[-1]
        out[:lo, k] = dyes[lo, k]
        tail = spectra.WL[hi + 1:] - spectra.WL[hi]
        out[hi + 1:, k] = dyes[hi, k] * np.exp(-tail / 30.0)
    return out


def development_probability(lam, t, sublatent_ratio):
    """Probability that a grain with Poisson photon catch rate lam has developed after time t.

    Development rate grows geometrically with latent-image size up to the full latent
    image (each missing photon slows it by sublatent_ratio); grains that caught no photon
    develop only as fog, after an induction period.
    """
    n = np.arange(QUANTUM_REQUIREMENT + 7)
    rate = K_LATENT * sublatent_ratio ** np.clip(QUANTUM_REQUIREMENT - n, 0, None)
    p_n = -np.expm1(-rate * t)
    p_n[0] = 0.0
    p_n = p_n + (1 - p_n) * -np.expm1(-K_FOG * t * t)
    lam = np.asarray(lam)[..., None]
    pmf = stats.poisson.pmf(n, lam)
    tail = stats.poisson.sf(n[-1], lam[..., 0])
    return pmf @ p_n + tail * p_n[-1]


def _emulsion_curve(params, log_h, t=1.0):
    """Developed fraction for a two-emulsion blend with log-normal grain cross-sections."""
    log_a1, s1, log_a2, s2, w_logit, log_ratio = params
    w = 1.0 / (1.0 + np.exp(-w_logit))
    total = 0.0
    for weight, log_a, s in ((w, log_a1, s1), (1 - w, log_a2, s2)):
        lam = 10.0 ** (log_a + s * _GH_X[None, :] + np.asarray(log_h)[:, None])
        total = total + weight * (development_probability(lam, t, 10.0 ** log_ratio) @ _GH_W)
    return total


_TABLES = {}


def _development_table(params, t):
    key = (tuple(np.round(params, 9)), round(t, 6))
    if key not in _TABLES:
        axis = np.linspace(-5.0, 4.0, 1801)
        _TABLES[key] = (axis, _emulsion_curve(params, axis, t))
    return _TABLES[key]


def _intrinsic_curves(log_h, developed):
    """Undo the grey-scale inhibition: data = F0(logH - sum_j M_jk F_j(logH))."""
    shifted = log_h[:, None] - developed @ INHIBITION
    intrinsic = np.empty_like(developed)
    for k in range(3):
        intrinsic[:, k] = np.interp(log_h, shifted[:, k], developed[:, k])
    return intrinsic


def _fit_layer(log_h, target):
    mid = np.interp(0.5, target, log_h)
    centre = np.log10(QUANTUM_REQUIREMENT) - mid
    start = np.array([centre + 0.25, 0.35, centre - 0.25, 0.35, 0.0, np.log10(0.25)])
    lower = [centre - 3, 0.02, centre - 3, 0.02, -6, np.log10(0.03)]
    upper = [centre + 3, 1.5, centre + 3, 1.5, 6, np.log10(0.7)]
    sel = (target > 0.002) & (target < 0.998) | (np.arange(len(target)) % 8 == 0)
    res = optimize.least_squares(lambda p: _emulsion_curve(p, log_h[sel]) - target[sel],
                                 start, bounds=(lower, upper), x_scale="jac")
    return res.x, np.abs(res.fun).max()


def _on_grid(pairs):
    """A digitised (wavelength, value) curve on the simulator's grid, NaN outside its range."""
    return np.interp(spectra.WL, *np.array(pairs).T, left=np.nan, right=np.nan)


def status_a_response():
    """ISO 5-3 Status A densitometer responsivity, (81, 3) for R, G, B."""
    data = json.loads(STATUS_A.read_text(encoding="utf-8"))
    return np.nan_to_num(np.stack([_on_grid(data[c]) for c in ("red", "green", "blue")], axis=1))


def status_a(spectral_density, response):
    """Status A R, G, B densities of a spectral density (..., 81)."""
    return -np.log10((10.0 ** -spectral_density @ response) / response.sum(axis=0))


def _cdfs(params, log_h):
    """A reversal curve: minimum density plus three falling normal CDFs."""
    dmin, steps = params[0], params[1:].reshape(3, 3)
    return dmin + sum(a * special.ndtr(-(log_h - c) / s) for a, c, s in steps)


def _status_curves(sheet):
    """The data sheet's R, G, B curves on LOG_H. They are printed from log H -2.4 to +0.4; a smooth
    fit (three normal CDFs, within 0.02 of the drawing) carries them on to the true maximum
    density and stays flat at the clear end, where the data sheet drew them flat."""
    out = np.empty((len(LOG_H), 3))
    for k, name in enumerate(("red", "green", "blue")):
        x, y = np.array(sheet["characteristic_curves"][name]).T
        start = [y.min() - 0.001, 1.2, -1.6, 0.4, 1.2, -1.0, 0.4, 1.2, -0.4, 0.4]
        fit = optimize.least_squares(lambda p: _cdfs(p, x) - y, start,
                                     bounds=([y.min() - 0.003] + [0, -4, 0.05] * 3, [y.min()] + [4, 2, 2] * 3))
        out[:, k] = _cdfs(fit.x, LOG_H)
    return out


def _unmix(target, base, dyes, response, iterations=30):
    """Dye amounts (N, 3) whose film reads the target Status A densities (N, 3): Newton steps."""
    amounts = np.ones_like(target)
    for _ in range(iterations):
        density = base + amounts @ dyes.T
        light = 10.0 ** -density[:, :, None] * response[None]                       # (N, 81, 3)
        jacobian = np.einsum("nlc,lk->nck", light, dyes) / light.sum(axis=1)[:, :, None]
        error = status_a(density, response) - target
        amounts = np.maximum(amounts - np.linalg.solve(jacobian, error[..., None])[..., 0], 0.0)
    return amounts


def load(verbose=False):
    sheet = json.loads(DATA.read_text(encoding="utf-8"))
    sensitivity = np.nan_to_num(10.0 ** np.stack([_on_grid(sheet["log_sensitivity"][k]) for k in
                                                  ("cyan_forming", "magenta_forming", "yellow_forming")], axis=1))
    dyes = _extrapolate_dyes(np.stack([_on_grid(sheet["dye_density"][k]) for k in ("cyan", "magenta", "yellow")],
                                      axis=1))
    response = status_a_response()
    status = _status_curves(sheet)
    # Base: density a + b u + c u^2 over the visible (u = (wavelength - 560) / 140, held beyond),
    # meeting the minimum densities of the data sheet's curves.
    u = np.clip((spectra.WL - 560.0) / 140.0, -1.0, 1.0)
    basis = np.stack([np.ones_like(u), u, u * u], axis=1)
    base = basis @ optimize.fsolve(lambda c: status_a(basis @ c, response) - status[-1], [0.2, 0.0, 0.0])
    curves = _unmix(status, base, dyes, response)
    log_h = LOG_H
    dmax = curves.max(axis=0)
    developed = 1.0 - curves / dmax

    # Balance: 18 % grey under D55 (the film's reference daylight) exposes every layer to 1.
    d55 = spectra.normalise(spectra.daylight(5500) * spectra.lens_transmission())
    sensitivity = sensitivity / (0.18 * (d55 @ sensitivity))

    intrinsic = _intrinsic_curves(log_h, developed)
    digest = hashlib.sha1(DATA.read_bytes() + STATUS_A.read_bytes() + INHIBITION.tobytes() + b"v4").hexdigest()[:12]
    cache = CACHE / f"emulsion_{digest}.npy"
    if cache.exists():
        grain_params = np.load(cache)
    else:
        grain_params = np.empty((3, 6))
        for k in range(3):
            grain_params[k], err = _fit_layer(log_h, intrinsic[:, k])
            if verbose:
                print(f"layer {'RGB'[k]}: emulsion fit max error {err:.4f}")
        CACHE.mkdir(parents=True, exist_ok=True)
        np.save(cache, grain_params)
    return Film(sensitivity, dyes, base, log_h, curves, dmax, developed, grain_params)
