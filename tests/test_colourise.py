"""Colourising black-and-white originals (with a stand-in for the DDColor model) and the
colour film turning them away.

Run:  .venv/bin/python -m unittest discover -s tests
"""
import unittest
from unittest import mock

import numpy as np

from dyeroom import colourise, pipeline, spectra
from dyeroom.capture import Capture, _luminance


class FixedColour:
    """Stands in for the model: guesses one warm colour everywhere."""
    def run(self, _outputs, feeds):
        _, _, h, w = feeds["input"].shape
        assert feeds["input"].dtype == np.float32 and h == w == colourise.SIZE
        return [np.stack([np.full((h, w), 18.0), np.full((h, w), 30.0)])[None].astype(np.float32)]


def grey_capture():
    ramp = np.linspace(0.01, 0.9, 64, dtype=np.float32)
    rgb = np.repeat(np.repeat(ramp[None, :, None], 40, 0), 3, 2)
    shown = spectra.SRGB.cctf_encoding(rgb).astype(np.float32)
    return Capture(rgb, None, None, 36000 / 64, {}, shown, None, None, True)


class Colourise(unittest.TestCase):
    def test_colour_added_luminance_kept(self):
        cap = grey_capture()
        with mock.patch.object(colourise, "_session", return_value=FixedColour()):
            out = colourise.apply(cap)
        np.testing.assert_allclose(_luminance(out.rgb), _luminance(cap.rgb), rtol=1e-3, atol=1e-5)
        mid = out.rgb[20, 32]
        self.assertGreater(mid[0], mid[2])          # warm: more red than blue
        self.assertFalse(out.monochrome)
        self.assertTrue(cap.monochrome)              # the original is left alone
        self.assertIn("guessed", out.notes["colours"])

    def test_colour_film_turns_black_and_white_away(self):
        cap = grey_capture()
        with mock.patch.object(pipeline.capture, "read", return_value=cap), \
                mock.patch.object(colourise, "available", return_value=False):
            with self.assertRaises(pipeline.MonochromeOriginal) as caught:
                pipeline.develop("grey.jpg", pipeline.Shoot(), log=lambda *_: None)
        self.assertEqual(caught.exception.code, "monochrome")
        self.assertIn("Monday 400", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
