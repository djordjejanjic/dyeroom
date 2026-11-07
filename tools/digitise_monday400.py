"""Digitise Monday 400's film data from the vector drawings of its maker's data sheet (SOURCES.md).

Run with PyMuPDF installed:  python tools/digitise_monday400.py DATA_SHEET.pdf out.json
The chart frames and gridlines below were read off that edition; another edition needs them checked.
"""
import json, sys
import numpy as np, pymupdf

doc = pymupdf.open(sys.argv[1])

def points(page, index):
    pts = []
    for it in page.get_drawings()[index]["items"]:
        seq = [it[1], it[-1]] if it[0] == "l" else ([it[1], it[2], it[3], it[4]] if it[0] == "c" else [])
        if it[0] == "c":  # sample the Bezier
            p0, c1, c2, p1 = [np.array([q.x, q.y]) for q in seq]
            for t in np.linspace(0, 1, 9):
                pts.append(tuple((1-t)**3*p0 + 3*(1-t)**2*t*c1 + 3*(1-t)*t**2*c2 + t**3*p1))
        else:
            pts += [(q.x, q.y) for q in seq]
    pts = np.array(pts)
    keep = np.r_[True, np.any(np.abs(np.diff(pts, axis=0)) > 1e-6, axis=1)]
    return pts[keep]

def monotone(x, y):
    order = np.argsort(x, kind="stable")
    x, y = x[order], y[order]
    ux, idx = np.unique(np.round(x, 4), return_index=True)
    return ux, np.array([y[x.round(4) == v].mean() for v in ux])

p8, p9 = doc[7], doc[8]
out = {}
# Characteristic curves, 35 mm, the standard developer, large tank, 1-min agitation, 20 C. Frame (93.4,66.5)-(277.8,251.0).
curves = {}
for minutes, idx in ((6, 21), (8, 22), (10, 23), (12, 20)):
    p = points(p9, idx)
    log_h = -4.0 + (p[:, 0] - 93.4) / (277.8 - 93.4) * 5.0
    density = (251.0 - p[:, 1]) / (251.0 - 66.5) * 4.0
    x, y = monotone(log_h, density)
    curves[minutes] = (x, y)
grid = np.round(np.arange(-3.55, 0.351, 0.05), 3)
out["log_exposure_lux_s"] = grid.tolist()
out["d76_large_tank_minutes"] = [6, 8, 10, 12]
out["density"] = [[round(float(np.interp(g, *curves[m], left=np.nan, right=np.nan)), 4) for g in grid] for m in (6, 8, 10, 12)]
for m in (6, 8, 10, 12):
    print(m, "min: logH", round(curves[m][0][0], 3), "..", round(curves[m][0][-1], 3),
          " D", round(curves[m][1][0], 3), "..", round(curves[m][1][-1], 3), " n", len(curves[m][0]))

# Spectral sensitivity: lambda = 300 + (x - 95.0)/0.402, logS = (442.9 - y)/37.8.
for name, idx in (("log_sensitivity_d1", 73), ("log_sensitivity_d03", 74)):
    p = points(p8, idx)
    wl = 300.0 + (p[:, 0] - 95.0) / 0.402
    ls = (442.9 - p[:, 1]) / 37.8
    x, y = monotone(wl, ls)
    out[name + "_raw"] = [[round(a, 2), round(b, 4)] for a, b in zip(x, y)]
    print(name, "wl", round(x[0], 1), "..", round(x[-1], 1), "peak", round(y.max(), 3), "at", round(x[np.argmax(y)], 1))

# MTF: log-log; y = 100.2 + 66.8*(2 - log10 R); x from gridlines.
gx = np.array([94.5, 107.1, 116.5, 123.1, 144.5, 167.1, 196.0, 217.7, 239.1])
gf = np.log10([2, 3, 4, 5, 10, 20, 50, 100, 200])
a, b = np.polyfit(gx, gf, 1)
p = points(p8, 33)
freq = 10 ** (a * p[:, 0] + b)
resp = 10 ** (2 - (p[:, 1] - 100.2) / 66.8)
x, y = monotone(freq, resp)
out["mtf_d76"] = [[round(f, 2), round(r, 2)] for f, r in zip(x, y)]
print("mtf", [(round(f,1), round(r,1)) for f, r in zip(x[::max(1,len(x)//8)], y[::max(1,len(x)//8)])], "last", round(x[-1],1), round(y[-1],1))

# Contrast index vs time, the standard developer, small tank (solid line). Frame x: 0-30 min over 365.9-550.3; y: 0-1.2 over 258.5-74.0.
p = points(p9, 70)
t = (p[:, 0] - 365.9) / (550.3 - 365.9) * 30
ci = (258.5 - p[:, 1]) / (258.5 - 74.0) * 1.2
x, y = monotone(t, ci)
out["ci_d76_small_tank"] = [[round(a, 3), round(b, 4)] for a, b in zip(x, y)]
print("CI small tank:", [(round(a,2), round(b,3)) for a, b in zip(x, y)])
json.dump(out, open(sys.argv[2], "w"), indent=1)
