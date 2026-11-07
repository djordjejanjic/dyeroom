"""Monday 400: a 400-speed black-and-white negative film, developed in a standard
fine-grain developer and enlarged onto silver-gelatin paper.

The film, from its maker's data sheet (SOURCES.md; curves digitised from its vector drawings
into data/monday400.json by tools/digitise_monday400.py):

* Spectral sensitivity. Panchromatic, strongest in violet and blue, cut off near 660 nm:
  reds print darker and blue skies lighter than the eye sees them. Check: per unit of
  luminance, 3200 K tungsten light exposes it 0.78 as much as daylight; the maker rated the
  film 320 under tungsten against 400 in daylight (0.80).
* Development. The data sheet's characteristic curves in the developer (large tank, agitation every minute,
  20 C) after 6, 8, 10 and 12 minutes; other times are interpolated between them. Longer
  development raises the shadows proportionally more than the highlights (x2.0 against
  x1.35 from 8 to 12 minutes), so the curves are used as measured rather than scaled.
  Times are the data sheet's: 7 3/4 min for EI 400 and EI 800 (one stop under, normal
  development, as the maker advises), 10 3/4 min for EI 1600; EI 3200 is given only for the small tank
  (11 min against 9 1/2 for EI 1600), scaled the same way to 12.4 min.
* Reciprocity. +1 stop at 1 s, +2 at 10 s, +3 at 100 s.
* Image structure. The data sheet's MTF is fitted by light spreading in the emulsion
  (Gaussian, about 3.8 um) and the developer's adjacency effect: developer exhausted next
  to dense areas and fresh next to thin ones, D + B (D - blur(D)) after Nelson, with
  B about 0.16 over 46 um. That gives the 110 % response near 8 cycles/mm, the crisp edges
  of negatives from this developer. Grain: diffuse RMS granularity 17 at net density 1.0 through a 48 um
  aperture; the variance of silver density in an area grows with the density (Nutting)
  and falls with the area (Selwyn).
* Contrast filters on the lens: long-pass (8 yellow, 15 deep yellow, 25 red) and band-pass
  (11 yellow-green, 58 green) gels whose edges are set so each filter factor on this film
  matches the data sheet's daylight table. The tungsten factors that follow (1.5, 1.7, 4.6,
  3.4, 5.4) agree with the data sheet's (1.5, 1.5, 5, 3, 6).

The print. The negative is enlarged onto glossy fibre-base paper (reflection density 0.05
to 2.10) with a diffusion enlarger. The paper grade sets the log exposure range the paper
spreads over its tones: the ISO 6846 range mid-points, grade 2 accepting about 1.05. The
shape of the paper curve between those points (long toe, short shoulder) is assumed, not
measured. The printer sets the print exposure the way a darkroom printer reads a test
strip: the print's tones match the brightness of a neutral rendering of the raw file as
closely as the paper allows, so pushing the film changes contrast, shadows and grain, not
the overall brightness.

Selenium toning, after the print is made. Selenium turns silver into silver selenide,
densest silver first: the shadows deepen (Dmax rises) and, as toning reaches the mid-tones,
the image turns purplish brown. The makers' instructions: a weak bath (1+20 and weaker) mainly
raises shadow density with little colour change; a strong one (1+3 to 1+5) gives the
purple-brown. Published sources only describe this; the amounts here are assumed: Dmax
+0.12 when fully toned, and selenide's own tone Lab a* +5, b* +1.
"""
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import colour
import numpy as np
from scipy import ndimage, optimize

from . import exposure as metering, process as reversal, spectra
from .capture import _luminance, _resize

DATA = Path(__file__).parent / "data" / "monday400.json"
NAME = "Monday 400"
STAGES = ["Reading the photograph", "Exposing the film", "Developer", "Stop and fix", "Printing"]

# Exposure index -> minutes in the developer, large tank, 20 C (see above).
RATINGS = {400: 7.75, 800: 7.75, 1600: 10.75, 3200: round(10.75 * 11.0 / 9.5, 2)}

# Paper grade -> log exposure range (ISO 6846 mid-points).
GRADES = {1: 1.275, 2: 1.05, 3: 0.875, 4: 0.725, 5: 0.575}
PAPER_DMIN, PAPER_DMAX = 0.05, 2.10
PAPER_TOE = 0.6         # paper curve shape: (1 + e^-u)^-0.6, a long toe and a short shoulder
VIEWING_FLARE = 0.004   # light reflected off the print's surface, as a fraction of white
PAPER_WHITE_Y = 0.92    # paper white on screen, as a scan of the print shows it
TONE_WHITE = (0.2, 1.2)  # Lab a*, b* of the paper base and of the densest silver: a neutral
TONE_BLACK = (0.4, 0.8)  # fibre paper, barely warm (assumed)
SHOULDER = 3.5          # density the negative's curve rolls towards beyond the data sheet's plots

# Selenium toner: how far toning reaches up from the shadows (the toned share of the
# silver is f^reach, f the print density from base to Dmax), extra density when fully
# toned, and the selenide's tone (assumed, see above).
TONING = {"none": None, "light": 3.0, "strong": 1.2}
SELENIDE_DENSITY = 0.12
SELENIDE_TONE = (5.0, 1.0)

# Lens filters: kind and, for band-pass gels, their centre wavelength.
FILTERS = {"none": None, "8": "long", "15": "long", "25": "long", "11": "band", "58": "band"}
BAND_CENTRE = {"11": 545.0, "58": 535.0}

GRAIN_APERTURE_UM2 = np.pi * 24.0 ** 2  # the data sheet's granularity is read through a 48 um aperture
METERED = 8.125  # lux seconds x EI on the film for a metered grey (K = 12.5, q = 0.65)
SEED = 1954      # a fixed seed: the grain is repeatable
D65 = colour.xy_to_XYZ(colour.CCS_ILLUMINANTS["CIE 1931 2 Degree Standard Observer"]["D65"])


@dataclass
class Film:
    sensitivity: np.ndarray   # (81, 1) spectral sensitivity; 18 % grey under D55 gives 1
    log_h: np.ndarray         # log10 exposure (lux seconds) of the characteristic curves
    minutes: np.ndarray       # development times of the curves
    density: np.ndarray       # (times, points) gross diffuse density
    mtf: np.ndarray           # (n, 2) cycles/mm, response %
    granularity: float        # diffuse RMS granularity x 1000
    reciprocity: np.ndarray   # (2, n) exposure time in s, extra stops needed
    factors: dict             # filter number -> daylight filter factor

    def curve(self, minutes):
        """Density against log exposure after this development time."""
        i = int(np.clip(np.searchsorted(self.minutes, minutes) - 1, 0, len(self.minutes) - 2))
        w = (minutes - self.minutes[i]) / (self.minutes[i + 1] - self.minutes[i])
        return self.density[i] * (1 - w) + self.density[i + 1] * w

    def develop(self, log_h, minutes):
        """Gross density of the developed and fixed negative. Below the data sheet's plots the curve
        has reached fog; above them it carries on at its last slope, rolling towards a shoulder."""
        dens, x = self.curve(minutes), self.log_h
        out = np.interp(log_h, x, dens)
        slope = (dens[-1] - dens[-6]) / (x[-1] - x[-6])
        head = SHOULDER - dens[-1]
        over = np.maximum(log_h - x[-1], 0.0)
        return np.where(log_h > x[-1], dens[-1] + head * -np.expm1(-slope * over / head), out)

    def fog(self, minutes):
        return float(self.curve(minutes)[0])


@lru_cache(maxsize=1)
def load():
    d = json.loads(DATA.read_text())
    wl, log_s = np.array(d["spectral_sensitivity"]["density_1.0"], float).T
    log_s = np.interp(spectra.WL, wl, log_s, right=np.nan)
    last = np.flatnonzero(np.isfinite(log_s))[-1]
    log_s[last + 1:] = log_s[last] - 0.12 * (spectra.WL[last + 1:] - spectra.WL[last])  # keeps falling
    s = 10.0 ** log_s
    d55 = spectra.normalise(spectra.daylight(5500) * spectra.lens_transmission())
    s = s / (0.18 * (d55 @ s))
    c = d["characteristic_curves"]
    r = d["reciprocity"]
    return Film(s[:, None], np.array(c["log_exposure_lux_s"], float), np.array(c["minutes"], float),
                np.array(c["density"], float), np.array(d["mtf_d76_large_tank"]["points"], float),
                float(d["diffuse_rms_granularity"]["value"]), np.array([r["time_s"], r["stops"]], float),
                {k: float(v) for k, v in d["filter_factors"]["daylight"].items()})


# --- filters and light ------------------------------------------------------------------------

def _filter_shape(name, edge):
    if FILTERS[name] == "long":
        return 0.9 / (1 + np.exp(-(spectra.WL - edge) / 12.0))
    centre = BAND_CENTRE[name]
    return (0.7 / (1 + np.exp(-(spectra.WL - (centre - edge)) / 14.0))
            / (1 + np.exp((spectra.WL - (centre + edge)) / 14.0)))


@lru_cache(maxsize=None)
def filter_transmission(name):
    """Gel transmission with its edge (cut-on wavelength, or half-width of the band) set so
    that its daylight filter factor on this film is the data sheet's."""
    if FILTERS.get(name) is None:
        return np.ones_like(spectra.WL)
    film = load()
    s = film.sensitivity[:, 0]
    d55 = spectra.normalise(spectra.daylight(5500) * spectra.lens_transmission())
    factor = lambda edge: (d55 @ s) / (d55 @ (s * _filter_shape(name, edge)))
    lo, hi = (380.0, 700.0) if FILTERS[name] == "long" else (5.0, 200.0)
    edge = optimize.brentq(lambda e: factor(e) - film.factors[name], lo, hi)
    return _filter_shape(name, edge)


def taking_light(cap, film, filter_name):
    """Light reaching the film. Without a filter it is metered by luminance, so light the film
    is less sensitive to (tungsten) exposes it less; with one, the photographer gives the
    filter factor for that light, so a grey card exposes the film as it would unfiltered."""
    light = spectra.scene_light(cap.scene_cct) if cap.scene_cct else spectra.daylight(5500)
    light = spectra.normalise(light * spectra.lens_transmission())
    if FILTERS[filter_name] is None:
        return light
    s = film.sensitivity[:, 0]
    filtered = light * filter_transmission(filter_name)
    return filtered * (light @ s) / (filtered @ s)


def reciprocity_stops(film, exposure_time):
    if not exposure_time or exposure_time <= film.reciprocity[0, 0]:
        return 0.0
    t, stops = np.log10(film.reciprocity[0]), film.reciprocity[1]
    x = np.log10(exposure_time)
    if x > t[-1]:
        return float(stops[-1] + (x - t[-1]) * (stops[-1] - stops[-2]) / (t[-1] - t[-2]))
    return float(np.interp(x, t, stops))


@lru_cache(maxsize=1)
def image_structure():
    """(scatter sigma um, adjacency sigma um, adjacency strength) fitted to the data sheet's MTF."""
    f, response = load().mtf.T
    def mtf(p):
        scatter, spread, strength = p
        k = 2 * np.pi ** 2 * f ** 2 * 1e-6
        return np.exp(-k * scatter ** 2) * (1 + strength * -np.expm1(-k * spread ** 2))
    fit = optimize.least_squares(lambda p: mtf(p) - response / 100, [4.0, 20.0, 0.1],
                                 bounds=([0.5, 2.0, 0.0], [15.0, 200.0, 1.0]))
    return tuple(float(v) for v in fit.x)


# --- the negative ------------------------------------------------------------------------------

def exposure_log_h(rgb, film, light, film_ev, rating, exposure_time, scene_cct=None):
    """log10 exposure on the film in lux seconds: spectral, at the metered exposure for the
    rating, with the reciprocity loss of long exposures."""
    relative = reversal.layer_exposure(rgb, film, light, scene_cct)[..., 0]  # 0 = a grey card under daylight
    stops = film_ev - reciprocity_stops(film, exposure_time)
    return relative + np.log10(METERED / rating) + stops * np.log10(2.0)


def develop_negative(log_h, film, minutes, um_per_px, grain=True, seed=SEED):
    """Light spreads in the emulsion, the developer forms silver, more at edges next to thin
    areas, and the silver comes in grains. Returns gross density of the fixed negative."""
    scatter, spread, strength = image_structure()
    h = 10.0 ** log_h
    if scatter / um_per_px > 0.25:
        h = ndimage.gaussian_filter(h, scatter / um_per_px)
    fog = film.fog(minutes)
    net = film.develop(np.log10(np.maximum(h, 1e-9)), minutes) - fog
    if spread / um_per_px > 0.25:
        net = net + strength * (net - ndimage.gaussian_filter(net, spread / um_per_px))
    if grain:
        per_density = (film.granularity / 1000.0) ** 2 * GRAIN_APERTURE_UM2  # variance x area per unit density
        noise = np.random.default_rng(seed).standard_normal(net.shape, dtype=np.float32)
        net = net + noise * np.sqrt(np.maximum(net, 0.0) * per_density / um_per_px ** 2)
    return (fog + np.maximum(net, 0.0)).astype(np.float32)


# --- the print ---------------------------------------------------------------------------------

def paper_density(log_hp, grade):
    """Print density from the paper's log exposure (0 where the paper starts to darken:
    0.04 above base), for a grade's ISO range."""
    span = PAPER_DMAX - PAPER_DMIN
    u_of = lambda y: -np.log(y ** (-1.0 / PAPER_TOE) - 1.0)
    u_a, u_b = u_of(0.04 / span), u_of((0.9 * PAPER_DMAX - PAPER_DMIN) / span)
    u = u_a + np.asarray(log_hp) * (u_b - u_a) / GRADES[grade]
    return PAPER_DMIN + span * (1.0 + np.exp(-u)) ** -PAPER_TOE


def print_luminance(dp):
    """Relative luminance on screen of print density, paper white at PAPER_WHITE_Y."""
    white = 10.0 ** -PAPER_DMIN + VIEWING_FLARE
    return (10.0 ** -dp + VIEWING_FLARE) / white * PAPER_WHITE_Y


def print_exposure(negative, target, grade):
    """The test strip: print exposure (log units on the paper's scale) bringing the print's
    lightness closest to the target lightness over the frame."""
    keep = (target > 10) & (target < 97)
    if keep.sum() < 0.05 * keep.size:
        keep = np.ones_like(keep)
    d, t = negative[keep].ravel(), target[keep].ravel()
    axis = np.linspace(-4.0, 6.0, 4001)
    light = metering.lightness(print_luminance(paper_density(axis, grade)))
    cost = lambda p: np.mean((np.interp(p - d, axis, light) - t) ** 2)
    coarse = np.arange(-1.0, 6.0, 0.02)
    best = coarse[np.argmin([cost(p) for p in coarse])]
    fine = np.arange(best - 0.02, best + 0.0201, 0.002)
    return float(fine[np.argmin([cost(p) for p in fine])])


def tone(dp, toning):
    """Selenium toning: (print density, toned share of the silver)."""
    reach = TONING.get(toning)
    if reach is None:
        return dp, np.zeros_like(dp)
    toned = np.clip((dp - PAPER_DMIN) / (PAPER_DMAX - PAPER_DMIN), 0.0, 1.0) ** reach
    return dp + SELENIDE_DENSITY * toned, toned


def print_to_display(dp, space, toned=None):
    """The print as it looks: lightness from its density, a barely warm neutral tone (moving
    towards selenide's purple-brown where toned), as linear display RGB."""
    y = print_luminance(dp).astype(np.float32)
    f = np.clip((dp - PAPER_DMIN) / (PAPER_DMAX - PAPER_DMIN), 0.0, 1.0)
    a = TONE_WHITE[0] + (TONE_BLACK[0] - TONE_WHITE[0]) * f
    b = TONE_WHITE[1] + (TONE_BLACK[1] - TONE_WHITE[1]) * f
    if toned is not None:
        a = a + (SELENIDE_TONE[0] - a) * toned
        b = b + (SELENIDE_TONE[1] - b) * toned
    fy = np.where(y > 216 / 24389, np.cbrt(y), (24389 / 27 * y + 16) / 116)
    finv = lambda t: np.where(t ** 3 > 216 / 24389, t ** 3, (116 * t - 16) * 27 / 24389)
    white = D65
    xyz = np.stack([white[0] * finv(fy + a / 500), y, white[2] * finv(fy - b / 200)], axis=-1)
    return np.clip(xyz @ space.matrix_XYZ_to_RGB.T.astype(np.float32), 0.0, 1.0)


# --- the whole process ---------------------------------------------------------------------------

def render(cap, shoot, stage=lambda i: None):
    """Expose, develop and fix the negative, enlarge it onto paper. Linear display RGB."""
    film = load()
    space = spectra.P3 if shoot.display == "p3" else spectra.SRGB
    minutes = RATINGS[shoot.rating]
    stage(1)
    sample = _resize(cap.rgb, metering.SAMPLE_EDGE)
    stops = np.log2(np.maximum(_luminance(sample), 1e-6) / 0.18)
    shift = 0.0
    if shoot.exposure == "auto":
        shift = float(np.clip(metering.AVERAGE_SCENE - metering._mean_log_stops(stops), -6.0, 6.0))
    film_ev = shift + shoot.ev
    light = taking_light(cap, film, shoot.bw_filter)
    exposure_time = None if cap.flash else cap.exposure_time  # a flash burst is short
    log_h = exposure_log_h(cap.rgb, film, light, film_ev, shoot.rating, exposure_time, cap.scene_cct)
    stage(2)
    negative = develop_negative(log_h, film, minutes, cap.um_per_px, shoot.process.grain, shoot.process.seed)
    stage(3)
    # Stop bath and fixer: the curves are of fixed film, so the undeveloped halide is already gone.
    stage(4)
    small = film.develop(exposure_log_h(sample, film, light, film_ev, shoot.rating, exposure_time, cap.scene_cct),
                         minutes)
    target = metering._reference(cap, stops, film_ev)
    p = print_exposure(small, target, shoot.grade)
    print_density, toned = tone(paper_density(p - negative, shoot.grade), shoot.toning)
    cap.notes.update({"filter": shoot.bw_filter, "exposure": shoot.exposure, "film exposure ev": round(film_ev, 2),
                      "developed": f"{minutes:g} min in the developer", "print exposure": round(p, 3)})
    return print_to_display(print_density, space, toned).astype(np.float32)
