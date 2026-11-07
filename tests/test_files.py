"""Image files (JPEG, HEIC, TIFF, PNG) on the film: the camera's tone curve undone first."""
import tempfile
import unittest
from pathlib import Path

import colour
import numpy as np
from PIL import Image

from dyeroom import capture, exposure, neutral, output, pipeline, spectra


class Unrender(unittest.TestCase):
    def test_grey_card_and_order(self):
        """A grey card as cameras show it comes back as 0.18, and lighter stays lighter."""
        grey_lightness = np.interp(0.0, *neutral.TYPICAL_CAMERA)
        y = ((grey_lightness + 16) / 116) ** 3
        self.assertAlmostEqual(float(neutral.unrender(np.full((1, 3), y, np.float32))[0, 0]), 0.18, delta=0.005)
        ramp = np.linspace(0, 1, 256, dtype=np.float32)[:, None].repeat(3, 1)
        scene = neutral.unrender(ramp)[:, 0]
        self.assertEqual(scene[0], 0)
        self.assertTrue(np.all(np.diff(scene) > 0))

    def test_colour_kept(self):
        """Only the brightness changes: each pixel's channels keep their ratios."""
        colours = np.array([[0.8, 0.4, 0.1], [0.1, 0.5, 0.3]], np.float32)
        scene = neutral.unrender(colours)
        np.testing.assert_allclose(scene / scene[:, :1], colours / colours[:, :1], rtol=1e-5)


class Contrast(unittest.TestCase):
    def test_a_jpeg_keeps_its_contrast(self):
        """Grey steps from a JPEG come off the slide about as far apart as they went in."""
        steps = np.repeat(np.repeat(np.linspace(0.12, 0.85, 8), 48)[None], 256, axis=0)  # encoded greys
        rng = np.random.default_rng(2)
        picture = np.clip(steps[..., None] + rng.normal(0, 0.01, steps.shape + (3,)), 0, 1)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "steps.png"
            Image.fromarray(np.round(picture * 255).astype(np.uint8)).save(path)
            rgb, _, _ = pipeline.develop(path, pipeline.Shoot(display="srgb", process=pipeline.Process(grain=False)),
                                         log=lambda *_: None)
        lstar = lambda enc: exposure.lightness(spectra.SRGB.cctf_decoding(np.clip(enc, 0, 1))
                                               @ spectra.SRGB.matrix_RGB_to_XYZ[1])
        centres = slice(12, 36)
        was = [lstar(steps[:, 48 * i:48 * (i + 1)][..., None].repeat(3, -1))[:, centres].mean() for i in range(8)]
        slide = output.encode(rgb)
        now = [lstar(slide[:, 48 * i:48 * (i + 1)])[:, centres].mean() for i in range(8)]
        slope = np.polyfit(was[2:6], now[2:6], 1)[0]  # the mid-tones
        self.assertTrue(0.85 < slope < 1.3, slope)

    def test_a_jpeg_keeps_its_colour(self):
        """Coloured patches come off the slide at least as colourful as they went in."""
        patch = np.zeros((128, 256, 3), np.float32) + np.array([0.75, 0.45, 0.3], np.float32)  # encoded
        patch[:, 128:] = [0.3, 0.5, 0.6]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "patch.png"
            Image.fromarray(np.round(patch * 255).astype(np.uint8)).save(path)
            rgb, _, _ = pipeline.develop(path, pipeline.Shoot(display="srgb", process=pipeline.Process(grain=False)),
                                         log=lambda *_: None)
        chroma = lambda enc: np.hypot(*colour.XYZ_to_Lab(spectra.SRGB.cctf_decoding(np.clip(enc, 0, 1))
                                                         @ spectra.SRGB.matrix_RGB_to_XYZ.T)[..., 1:].reshape(-1, 2).T)
        self.assertGreater(np.median(chroma(output.encode(rgb))), 0.9 * np.median(chroma(patch)))


class Phones(unittest.TestCase):
    def test_heic_upright_in_display_p3(self):
        """An iPhone-style HEIC, stored sideways with Apple's Display P3 profile (made with macOS sips):
        it comes in upright, turned once, and read as Display P3."""
        cap = capture.read(Path(__file__).with_name("data") / "sideways-p3.heic")
        self.assertEqual(cap.rgb.shape, (120, 80, 3))
        self.assertGreater(cap.preview[4, -5].min(), 0.9)  # the white corner, top left as stored, is top right
        self.assertEqual(cap.notes["source space"], spectra.P3.name)

    def test_colour_space_from_heif_primaries(self):
        self.assertIs(capture._space({"nclx_profile": {"color_primaries": 12}}), spectra.P3)
        self.assertIs(capture._space({"nclx_profile": {"color_primaries": 1}}), spectra.SRGB)
        self.assertIs(capture._space({"icc_profile": b"not a profile"}), spectra.SRGB)


if __name__ == "__main__":
    unittest.main()
