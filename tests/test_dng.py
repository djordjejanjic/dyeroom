"""The linear DNG reader: Apple ProRAW compressed with JPEG XL, which LibRaw cannot read."""
import tempfile
import unittest
from pathlib import Path

import numpy as np
import rawpy
import tifffile

from dyeroom import capture, dng

NEUTRAL = (0.45, 1.0, 0.55)  # the camera's response to a grey under the as-shot light
# XYZ to camera under standard light A and D65, roughly an iPhone's
CM_A = (1.227, -0.545, -0.261, -0.455, 1.518, -0.043, -0.041, 0.258, 0.484)
CM_D65 = (0.915, -0.322, -0.126, -0.429, 1.310, 0.095, -0.106, 0.250, 0.592)


def _rational(values):
    out = []
    for v in values:
        out += [round(v * 1_000_000), 1_000_000]
    return tuple(out)


def write_dng(path, height=48, width=64, orientation=1, grain=0.0):
    """A small LinearRaw DNG of a grey, JPEG XL compressed, with ProRAW's colour tags."""
    noise = 1 + grain * np.random.default_rng(1).standard_normal((height, width, 1))
    grey = np.round(np.array(NEUTRAL) * 0.3 * noise * 65535).astype(np.uint16)
    grey[: height // 2, : width // 4] = 0  # a dark corner, to see which way up it comes out
    tags = [(50706, 1, 4, (1, 7, 0, 0), True),          # DNGVersion
            (50721, 10, 9, _rational(CM_A), True),        # ColorMatrix1
            (50722, 10, 9, _rational(CM_D65), True),      # ColorMatrix2
            (50778, 3, 1, 17, True), (50779, 3, 1, 21, True),  # CalibrationIlluminant1, 2
            (50728, 5, 3, _rational(NEUTRAL), True),      # AsShotNeutral
            (274, 3, 1, orientation, True)]
    tifffile.imwrite(path, grey, photometric=34892, compression=52546, planarconfig="contig",
                     tile=(16, 16), extratags=tags)


class LinearDng(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "IMG_0001.dng"

    def tearDown(self):
        self.tmp.cleanup()

    def test_libraw_cannot_but_we_can(self):
        write_dng(self.path)
        with self.assertRaises(rawpy.LibRawError):
            rawpy.imread(str(self.path)).postprocess()
        self.assertTrue(dng.is_linear(self.path))
        out = dng.read(self.path, lambda img: img)
        self.assertEqual(out["rgb"].shape, (48, 64, 3))
        self.assertEqual(out["decoder"], "DNG reader")
        self.assertTrue(2500 < out["cct"] < 7000)

    def test_the_cameras_grey_comes_out_grey(self):
        write_dng(self.path)
        rgb = dng.read(self.path, lambda img: img)["rgb"]
        grey = rgb[-1, -1]
        self.assertGreater(grey.min(), 0)
        self.assertLess(np.abs(np.log(grey / grey.mean())).max(), 0.01)

    def test_upright(self):
        write_dng(self.path, orientation=6)  # turned a quarter clockwise to stand up
        rgb = dng.read(self.path, lambda img: img)["rgb"]
        self.assertEqual(rgb.shape, (64, 48, 3))
        self.assertLess(rgb[:16, -24:].max(), 1e-6)  # the dark corner is now top right

    def test_through_capture(self):
        """capture.read takes it from LibRaw's refusal to a developed-ready picture."""
        write_dng(self.path, height=192, width=256, grain=0.05)  # a photograph has some texture
        shot = capture.read(self.path, long_edge=128)
        self.assertEqual(max(shot.rgb.shape[:2]), 128)
        self.assertEqual(shot.notes["decoder"], "DNG reader")


if __name__ == "__main__":
    unittest.main()
