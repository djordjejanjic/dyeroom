"""Diagnostic: grey scale and ColorChecker through the simulated film, numbers and an image.

python tools/chart.py [--view projector] [--out out/chart.png]
"""
import argparse
import sys
from pathlib import Path

import colour
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dyeroom import exposure, film as film_model, process as reversal, spectra, viewing as views  # noqa: E402
from dyeroom.pipeline import Shoot, taking_light  # noqa: E402
from dyeroom.capture import Capture  # noqa: E402


def lab_from_display(rgb, space):
    xyz = colour.models.eotf_sRGB(colour.models.eotf_inverse_sRGB(rgb)) @ space.matrix_RGB_to_XYZ.T
    return colour.XYZ_to_Lab(xyz, space.whitepoint)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--view", default="lightbox", choices=list(views.VIEWINGS))
    ap.add_argument("--out", default="out/chart.png")
    ap.add_argument("--inhibition-scale", type=float, default=1.0)
    ap.add_argument("--ev", type=float, default=0.0)
    args = ap.parse_args()
    film_model.INHIBITION *= args.inhibition_scale  # shared array; set before the emulsion fit
    film = film_model.load(verbose=True)
    view = views.VIEWINGS[args.view]
    space = spectra.P3
    shoot = Shoot(view=args.view)
    cap = Capture(np.zeros((1, 1, 3), np.float32), None, None, 10.0)
    light = taking_light(cap, shoot)

    # Patches as true reflectance spectra (ColorChecker, BabelColor average) and as Rec.2020 RGB.
    cc = colour.SDS_COLOURCHECKERS["BabelColor Average"]
    names = list(cc.keys())
    refl = np.array([cc[n].copy().align(spectra.SHAPE).values for n in names])
    greys = np.geomspace(0.003, 1.2, 25)
    d65 = spectra.normalise(colour.SDS_ILLUMINANTS["D65"].copy().align(spectra.SHAPE).values)
    rgb_cc = (refl * d65) @ spectra.CMFS @ spectra.REC2020.matrix_XYZ_to_RGB.T
    rgb = np.concatenate([rgb_cc, greys[:, None].repeat(3, 1)]).astype(np.float32)[None]

    log_h = reversal.layer_exposure(rgb * 2.0 ** args.ev, film, light) + reversal.metered_grey_log_h(film)
    print("grey balance offsets (log H, R G B)", reversal.grey_balance(film).round(4))
    log_h += reversal.grey_balance(film)
    print("metered grey card lands at log H", round(reversal.metered_grey_log_h(film), 3))
    # Exposure straight from the measured spectra, to check the upsampling path.
    log_h_true = np.log10(np.maximum((refl * light) @ film.sensitivity, 1e-6)) + reversal.metered_grey_log_h(film)
    developed = reversal.first_developer(log_h, film, reversal.Process(grain=False), 1e6)  # no spatial mixing between patches
    dyes = reversal.reversal_and_dyes(developed, film, reversal.Process(grain=False), 10.0, 1.0)
    xyz, white = views.slide_to_xyz(dyes, film, view)
    out = views.to_display(views.adapted_to_slide(xyz, exposure.eye_gain(args.view)), white, view, space)[0]

    src_lab = colour.XYZ_to_Lab(rgb[0] @ spectra.REC2020.matrix_RGB_to_XYZ.T, spectra.REC2020.whitepoint)
    out_lab = colour.XYZ_to_Lab(out @ space.matrix_RGB_to_XYZ.T, space.whitepoint)
    diff = log_h[0, :24] - log_h_true
    worst = np.argsort(-np.abs(diff).max(1))[:4]
    print("\nupsampled minus true-spectrum log exposure (R,G,B), worst patches:")
    for i in worst:
        print(f"  {names[i]:15s} {diff[i].round(3)}")
    slide_lab = colour.XYZ_to_Lab(xyz[0] / 100, colour.XYZ_to_xy(white / 100))
    print("\nGREY SCALE  reflectance -> slide dye C,M,Y -> display L*, a*, b*")
    for i in range(0, 25, 2):
        g = 24 + i
        print(f"  {greys[i]:7.4f}  logH {log_h[0, g].mean():+.2f}  dyes {dyes[0, g].round(2)}  "
              f"slide L* {slide_lab[g, 0]:5.1f}  display L* {out_lab[g, 0]:5.1f}  a* {out_lab[g, 1]:+5.1f}  b* {out_lab[g, 2]:+5.1f}")
    print("\nCOLORCHECKER  source L C h  ->  slide (own white) L C h  ->  display L C h")
    for i, n in enumerate(names[:18]):
        s = colour.Lab_to_LCHab(src_lab[i]); m = colour.Lab_to_LCHab(slide_lab[i]); o = colour.Lab_to_LCHab(out_lab[i])
        print(f"  {n:15s} {s[0]:5.1f} {s[1]:5.1f} {s[2]:4.0f}  ->  {m[0]:5.1f} {m[1]:5.1f} {m[2]:4.0f}"
              f"  ->  {o[0]:5.1f} {o[1]:5.1f} {o[2]:4.0f}")
    # Swatch image: top half original (as P3), bottom half Sunday 64.
    src_disp = np.clip(rgb[0, :24] @ (space.matrix_XYZ_to_RGB @ spectra.REC2020.matrix_RGB_to_XYZ).T, 0, 1)
    tiles = []
    for row in range(4):
        a = np.concatenate([np.full((60, 60, 3), src_disp[row * 6 + c]) for c in range(6)], 1)
        b = np.concatenate([np.full((60, 60, 3), out[row * 6 + c]) for c in range(6)], 1)
        tiles.append(np.concatenate([a[:30], b[30:]], 0))
    ramp = np.concatenate([np.full((30, 15, 3), out[24 + i]) for i in range(24)], 1)
    img = np.concatenate(tiles + [np.zeros((6, 360, 3)), ramp], 0)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.round(colour.models.eotf_inverse_sRGB(np.clip(img, 0, 1)) * 255).astype(np.uint8)).resize(
        (720, img.shape[0] * 2), Image.NEAREST).save(args.out)


if __name__ == "__main__":
    main()
