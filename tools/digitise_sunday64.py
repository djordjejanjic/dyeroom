"""Digitise Sunday 64's film data from the vector drawings of its maker's data sheet, page 4.

Run with PyMuPDF installed:  python tools/digitise_sunday64.py DATA_SHEET.pdf dyeroom/data/sunday64.json
(the data sheet and where to find it: SOURCES.md.) The chart frames, gridlines and drawing numbers
below were read off that edition; another edition needs them checked.
"""
import json
import sys

import numpy as np
import pymupdf

page = pymupdf.open(sys.argv[1])[3]
drawings = page.get_drawings()


def points(index):
    pts = []
    for it in drawings[index]["items"]:
        if it[0] == "l":
            pts += [(it[1].x, it[1].y), (it[2].x, it[2].y)]
        elif it[0] == "c":  # sample the Bezier
            p0, c1, c2, p1 = [np.array([q.x, q.y]) for q in it[1:5]]
            for t in np.linspace(0, 1, 9):
                pts.append(tuple((1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * c1 + 3 * (1 - t) * t ** 2 * c2 + t ** 3 * p1))
    return np.array(pts)


def curve(index, x_of, y_of):
    """A drawn curve as sorted, de-duplicated (x, y) pairs in chart units."""
    p = points(index)
    x, y = x_of(p[:, 0]), y_of(p[:, 1])
    order = np.argsort(x, kind="stable")
    x, y = x[order], y[order]
    ux = np.unique(np.round(x, 4))
    return [[float(v), float(y[np.round(x, 4) == v].mean())] for v in ux]


def linear_axis(pixels, values):
    a, b = np.polyfit(pixels, values, 1)
    return lambda p: a * np.asarray(p) + b


out = {"source": "The maker's data sheet for the slide film Sunday 64 is modelled on (SOURCES.md), page 4; "
                 "digitised from the PDF's vector drawings by tools/digitise_sunday64.py"}

# Characteristic curves. Frame (71.3, 136.5)-(255.8, 321.0): log H -3 .. +1, density 4 .. 0.
log_h = linear_axis([71.3, 117.4, 163.5, 209.7, 255.8], [-3, -2, -1, 0, 1])
density = linear_axis([321.0, 274.9, 228.7, 182.6, 136.5], [0, 1, 2, 3, 4])
out["characteristic_curves"] = {
    "axis": "log10 exposure, lux-seconds (daylight, 1/50 s); the film's reversal process; Status A density",
    **{name: curve(i, log_h, density) for name, i in (("red", 4), ("green", 2), ("blue", 3))}}

# Spectral sensitivity. Frame (74.7, 399.0)-(275.2, 550.5): 250 .. 750 nm, log sensitivity 2 .. -2.
wavelength = linear_axis([74.7, 94.7, 114.8, 134.9, 155.0, 175.1, 195.2, 215.3, 235.4, 255.5, 275.2],
                         [250, 300, 350, 400, 450, 500, 550, 600, 650, 700, 750])
log_s = linear_axis([399.0, 436.9, 474.8, 512.6, 550.5], [2, 1, 0, -1, -2])
out["log_sensitivity"] = {
    "definition": "log10 of the reciprocal of the exposure (erg/cm2) giving E.N.D. density 1.00; "
                  "effective exposure 1.4 s, the film's reversal process",
    **{name: curve(i, wavelength, log_s) for name, i in
       (("yellow_forming", 16), ("magenta_forming", 17), ("cyan_forming", 18))}}

# Spectral dye density. Frame (352.0, 390.2)-(536.3, 574.6): 400 .. 700 nm; gridlines at 0.5 and 1.0.
wavelength = linear_axis([352.0, 413.4, 474.9, 536.3], [400, 500, 600, 700])
dye = linear_axis([574.6, 511.1, 447.6], [0.0, 0.5, 1.0])
out["dye_density"] = {
    "normalisation": "diffuse spectral density of dyes forming a visual neutral density of 1.0 "
                     "for a 3200 K viewing illuminant",
    **{name: curve(i, wavelength, dye) for name, i in
       (("cyan", 97), ("magenta", 94), ("yellow", 96), ("neutral", 95))}}

# Modulation transfer, log-log. Frame (348.2, 144.1)-(550.7, 297.1).
log_f = linear_axis([348.2, 369.9, 382.6, 391.9, 398.5, 419.9, 442.5, 471.5, 493.2, 514.6],
                    np.log10([1, 2, 3, 4, 5, 10, 20, 50, 100, 200]))
log_r = linear_axis([297.1, 264.9, 250.7, 240.5, 230.3, 210.1, 198.3, 183.6, 173.9, 163.4],
                    np.log10([1, 2, 3, 4, 10, 20, 30, 50, 70, 100]))
mtf = curve(46, log_f, log_r)
out["mtf"] = {"densitometry": "diffuse visual", "cycles_per_mm_and_response":
              [[round(10 ** f, 3), round(10 ** r / 100, 4)] for f, r in mtf]}

# Sanity checks against values read off the printed charts.
dmax = [max(y for _, y in out["characteristic_curves"][c]) for c in ("red", "green", "blue")]
assert np.allclose(dmax, [3.68, 3.45, 3.32], atol=0.03), dmax
peaks = {k: max(v, key=lambda p: p[1])[0] for k, v in out["dye_density"].items() if k != "normalisation"}
assert abs(peaks["magenta"] - 537) < 5 and abs(peaks["yellow"] - 442) < 5, peaks
with open(sys.argv[2], "w") as f:
    json.dump(out, f, indent=1)
print("Dmax R G B", np.round(dmax, 3), "dye peaks", {k: round(v) for k, v in peaks.items()})
