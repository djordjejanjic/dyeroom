"""Diagnostic: the simulated film's MTF against the published curve for Sunday 64's film.

python tools/mtf.py

The data sheets (SOURCES.md) print one diffuse visual MTF; tools/digitise_sunday64.py reads it
off the vector drawing. The model is measured the way the maker measures film: a small sinusoidal
exposure around a metered grey goes through emulsion scatter and the first developer's edge
effects, and the visual density of the slide is turned back into effective exposure through
the large-area characteristic curve.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dyeroom import film as film_model, process as reversal, spectra, viewing as views  # noqa: E402

PX_PER_CYCLE = 40
FREQUENCIES = (2.5, 5, 7.5, 10, 15, 20, 30, 40, 50, 60, 70, 80)


def published_mtf():
    f, response = np.array(json.loads(film_model.DATA.read_text(encoding="utf-8"))["mtf"]["cycles_per_mm_and_response"]).T
    return {freq: float(np.interp(np.log(freq), np.log(f), response)) for freq in FREQUENCIES}


def main():
    film = film_model.load()
    light = spectra.daylight(5000)
    grey = reversal.metered_grey_log_h(film) + reversal.grey_balance(film)
    process = reversal.Process(grain=False)

    def visual_density(dyes):
        y = views.dye_transmittance_xyz(dyes.reshape(-1, 3), film, light)[:, 1]
        return -np.log10(y).reshape(dyes.shape[:-1])

    axis = np.linspace(-1.5, 1.5, 601)
    flat = reversal.first_developer(grey[None, None, :] + axis[:, None, None], film, process, 1e6)
    curve = visual_density(reversal.reversal_and_dyes(flat, film, process, 1e6, 1.0))[:, 0]

    def response(f, m=0.05):
        um = 1000.0 / (f * PX_PER_CYCLE)
        cycles = max(24, int(f * 4))  # at least 4 mm of film
        x = np.arange(PX_PER_CYCLE * cycles) * um / 1000.0
        log_h = grey[None, None, :] + np.log10(1 + m * np.cos(2 * np.pi * f * x))[None, :, None]
        log_h = reversal.irradiation(log_h, um)
        dyes = reversal.reversal_and_dyes(reversal.first_developer(log_h, film, process, um), film, process, um, 1.0)
        effective = 10.0 ** np.interp(-visual_density(dyes)[0], -curve, axis)
        core = slice(PX_PER_CYCLE * (cycles // 4), PX_PER_CYCLE * (cycles - cycles // 4))
        c, s = np.cos(2 * np.pi * f * x[core]), np.sin(2 * np.pi * f * x[core])
        e = effective[core]
        return np.hypot(np.mean(e * c), np.mean(e * s)) * 2 / np.mean(e) / m

    print("cycles/mm   sheet   model")
    for f, sheet in published_mtf().items():
        print(f"{f:9}   {sheet:5.2f}   {response(f):5.2f}")


if __name__ == "__main__":
    main()
