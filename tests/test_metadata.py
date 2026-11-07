"""The original's metadata carried over to exports, and the AI tag on colourised ones.

Run:  .venv/bin/python -m unittest discover -s tests
"""
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import numpy as np
import tifffile
from PIL import Image

from dyeroom import metadata, output

SAMPLE = Path(__file__).resolve().parents[1] / "samples" / "sample-olympus-e-p7.orf"


def tags(path):
    run = subprocess.run(["exiftool", "-j", "-G1", "-a", str(path)], capture_output=True, text=True, check=True)
    return json.loads(run.stdout)[0]


@unittest.skipUnless(metadata.available() and SAMPLE.exists(), "needs exiftool and the sample raw")
class CarryOver(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.picture = (np.random.default_rng(1).random((60, 90, 3)) * 0.9).astype(np.float32)

    def tearDown(self):
        self.dir.cleanup()

    def export(self, name):
        path = Path(self.dir.name) / name
        if name.endswith(".jpg"):
            path.write_bytes(output.jpeg_bytes(self.picture, "p3"))
        else:
            path.write_bytes(output.tiff_bytes(np.round(self.picture * 65535).astype(np.uint16), "p3"))
        return path

    def test_raw_metadata_copied_pixels_and_original_untouched(self):
        before = hashlib.sha256(SAMPLE.read_bytes()).hexdigest()
        for name in ("a.jpg", "a.tif"):
            path = self.export(name)
            pixels = np.asarray(Image.open(path)) if name.endswith(".jpg") else tifffile.imread(path)
            self.assertTrue(metadata.carry_over(SAMPLE, path))
            after = np.asarray(Image.open(path)) if name.endswith(".jpg") else tifffile.imread(path)
            np.testing.assert_array_equal(after, pixels)
            t = tags(path)
            self.assertEqual(t["IFD0:Model"], "E-P7")
            self.assertEqual(t["ExifIFD:DateTimeOriginal"], "2022:08:16 12:41:10")
            self.assertEqual(t["ICC_Profile:ProfileDescription"], "Display P3")  # our profile, not the camera's
            self.assertNotIn("XMP-iptcExt:DigitalSourceType", t)
        self.assertEqual(hashlib.sha256(SAMPLE.read_bytes()).hexdigest(), before)

    def test_orientation_not_carried_over(self):
        original = Path(self.dir.name) / "turned.jpg"
        exif = Image.Exif()
        exif[0x0112] = 6  # rotate 90 degrees to display
        exif[0x010F] = "TestMake"
        Image.new("RGB", (40, 30)).save(original, exif=exif)
        path = self.export("b.jpg")
        self.assertTrue(metadata.carry_over(original, path))
        t = tags(path)
        self.assertEqual(t["IFD0:Make"], "TestMake")
        self.assertNotIn("IFD0:Orientation", t)  # the export is already upright

    def test_ai_tag_only_when_colours_were_guessed(self):
        path = self.export("c.jpg")
        self.assertTrue(metadata.carry_over(SAMPLE, path, ai_colours=True))
        self.assertEqual(tags(path)["XMP-iptcExt:DigitalSourceType"], metadata.AI_EDITED)

    def test_missing_original_leaves_export_alone(self):
        path = self.export("d.jpg")
        data = path.read_bytes()
        self.assertFalse(metadata.carry_over(Path(self.dir.name) / "gone.raf", path))
        self.assertEqual(path.read_bytes(), data)


if __name__ == "__main__":
    unittest.main()
