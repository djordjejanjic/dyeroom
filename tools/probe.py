"""Diagnostic: follow chosen pixels of one photo through exposure and development.

python tools/probe.py PHOTO x,y [x,y ...]   (coordinates as fractions of width, height)
"""
import sys
from pathlib import Path

import numpy as np

from dyeroom import capture, film as film_model, pipeline, process as reversal, spectra

path = Path(sys.argv[1])
film = film_model.load()
cap = capture.read(path, 800)
shoot = pipeline.Shoot()
light = pipeline.taking_light(cap, shoot)
h, w = cap.rgb.shape[:2]
neg = (cap.rgb.min(-1) < 0).mean()
print(f"pixels with a negative Rec.2020 component: {100 * neg:.1f} %")
for spec in sys.argv[2:]:
    fx, fy = map(float, spec.split(","))
    y, x = int(fy * h), int(fx * w)
    rgb = cap.rgb[y - 2:y + 3, x - 2:x + 3].reshape(-1, 3).mean(0)
    pos = reversal.gamut_to_positive(rgb[None, None].astype(np.float32))[0, 0]
    log_h = reversal.layer_exposure(rgb[None, None].astype(np.float32), film, light)[0, 0] + reversal.metered_grey_log_h(film)
    peak = max(pos.max(), 1e-7)
    look = np.clip(peak, 0.25, 0.95)
    lattice, err = spectra.reflectance_lattice()
    idx = np.clip(np.round(pos * look / peak * 32).astype(int), 0, 32)
    print(f"({fx},{fy}) rgb {rgb.round(3)} -> positive {pos.round(3)}; logH R,G,B {log_h.round(2)}; "
          f"lattice fit error at lookup {err[tuple(idx)]:.3f}")
