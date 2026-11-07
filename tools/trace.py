"""Diagnostic: percentiles of every stage for one photo (where do shadows/colours go?)."""
import sys
from pathlib import Path

import colour
import numpy as np

from dyeroom import capture, exposure, film as film_model, pipeline, process as reversal, spectra, viewing as views

path = Path(sys.argv[1])
shoot = pipeline.Shoot(view=sys.argv[2] if len(sys.argv) > 2 else "lightbox",
                       exposure=sys.argv[3] if len(sys.argv) > 3 else "camera")
film = film_model.load()
cap = capture.read(path, 800)
pct = [1, 5, 25, 50, 75, 95, 99]
y = cap.rgb @ np.array([0.2627, 0.678, 0.0593])
print("scene Y (0.18 = grey)", np.percentile(y, pct).round(4))
print("negative-channel pixels %", round(100 * (cap.rgb.min(-1) < 0).mean(), 2))
stops = exposure.choose(cap, shoot.exposure, shoot.view)
print(f"film exposure {stops:+.2f} stops from the camera's metering ({shoot.exposure})")
log_h = (reversal.layer_exposure(cap.rgb * 2.0 ** stops, film, pipeline.taking_light(cap, shoot))
         + reversal.metered_grey_log_h(film) + reversal.grey_balance(film))
print("log H green", np.percentile(log_h[..., 1], pct).round(3))
dev = reversal.first_developer(log_h, film, shoot.process, cap.um_per_px)
dyes = reversal.reversal_and_dyes(dev, film, reversal.Process(grain=False), cap.um_per_px, 1.0)
print("magenta dye", np.percentile(dyes[..., 1], pct).round(3))
view = views.VIEWINGS[shoot.view]
xyz, white = views.slide_to_xyz(dyes, film, view)  # as measured, before the eye adapts
lab = colour.XYZ_to_Lab(xyz / 100, colour.XYZ_to_xy(white / 100))
print("slide L*", np.percentile(lab[..., 0], pct).round(1))
rgb = views.to_display(views.adapted_to_slide(xyz, exposure.eye_gain(shoot.view)), white, view, spectra.P3)
lab2 = colour.XYZ_to_Lab(rgb @ spectra.P3.matrix_RGB_to_XYZ.T, spectra.P3.whitepoint)
print("display L*", np.percentile(lab2[..., 0], pct).round(1))
c = np.hypot(lab2[..., 1], lab2[..., 2]); print("display C*", np.percentile(c, pct).round(1))
dark = lab2[..., 0] < 20
print("dark pixels: mean a* b*", lab2[dark][:, 1].mean().round(2), lab2[dark][:, 2].mean().round(2))
