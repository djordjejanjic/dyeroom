"""Sunday 64 against its film's data sheet, and the colour fixes from the accuracy audit.

Run:  .venv/bin/python -m unittest discover -s tests
"""
import json
import unittest

import colour
import numpy as np

from dyeroom import film as film_model, process as reversal, spectra


class DataSheet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.film = film_model.load()
        cls.sheet = json.loads(film_model.DATA.read_text(encoding="utf-8"))

    def test_status_a_curves_match_the_data_sheet(self):
        """The dye amounts, seen through the dye spectra and a Status A densitometer, give
        back the data sheet's printed characteristic curves over their whole range."""
        response = film_model.status_a_response()
        density = film_model.status_a(self.film.base + self.film.curves @ self.film.dyes.T, response)
        for k, name in enumerate(("red", "green", "blue")):
            x, y = np.array(self.sheet["characteristic_curves"][name]).T
            ours = np.interp(x, self.film.log_h, density[:, k])
            self.assertLess(np.abs(ours - y).max(), 0.03, name)

    def test_iso_speed_is_64(self):
        """ISO 2240 speed from the curves on the data sheet's lux-second axis."""
        metered = reversal.metered_grey_log_h(self.film)
        speed = 10.0 / 10.0 ** (metered - np.log10(8.125 / 10.0))
        self.assertAlmostEqual(speed, 64.0, delta=3.0)

    def test_deepest_black(self):
        """The maker's IT8 target on this film measures a visual Dmax of about 3.2."""
        light = spectra.daylight(5000)
        t = 10.0 ** -(self.film.base + self.film.dmax @ self.film.dyes.T)
        visual = -np.log10((t * light) @ spectra.YBAR / (light @ spectra.YBAR))
        self.assertGreater(visual, 3.1)


class Colour(unittest.TestCase):
    def test_bright_blue_sky_stays_blue(self):
        """A saturated sky 1.5 stops over grey keeps the red-layer exposure of real sky light
        (it used to borrow a lopsided spectrum near reflectance 1 and turn purple)."""
        film = film_model.load()
        sun = spectra.daylight(5500)
        light = spectra.normalise(sun * spectra.lens_transmission())
        sky = sun * (spectra.WL / 550.0) ** -4 * spectra.lens_transmission()
        sky = sky / (sky @ spectra.YBAR) * 0.5
        true = np.log10(sky @ film.sensitivity)
        balanced = colour.chromatic_adaptation(spectra.xyz_of(sky) * 0.5, spectra.xyz_of(sun), spectra.xyz_of(spectra.D65),
                                               method="Von Kries", transform="CAT16")  # white balance for the sun
        rgb = (balanced @ spectra.REC2020.matrix_XYZ_to_RGB.T).astype(np.float32)[None, None]
        self.assertLess(np.abs(reversal.layer_exposure(rgb, film, light)[0, 0] - true).max(), 0.08)

    def test_scene_lights_blend_in_mired(self):
        self.assertEqual(spectra.lattice_lights(None), [(None, 1.0)])
        self.assertEqual(spectra.lattice_lights(6000), [(None, 1.0)])
        self.assertEqual(spectra.lattice_lights(1800), [(2400, 1.0)])
        (a, wa), (b, wb) = spectra.lattice_lights(3200)
        self.assertEqual((a, b), (3000, 3400))
        self.assertAlmostEqual(wa + wb, 1.0)
        self.assertAlmostEqual(wb, (1e6 / 3000 - 1e6 / 3200) / (1e6 / 3000 - 1e6 / 3400))

    def test_reciprocity_follows_the_data_sheet(self):
        """The data sheet: nothing at 1/100 s; at 1/10 s +1/3 stop with CC05R."""
        zero = np.zeros(3)
        np.testing.assert_allclose(reversal.reciprocity(zero, 0.01), zero)
        np.testing.assert_allclose(reversal.reciprocity(zero, 0.1), [-0.10, -0.05, -0.05], atol=1e-9)


if __name__ == "__main__":
    unittest.main()
