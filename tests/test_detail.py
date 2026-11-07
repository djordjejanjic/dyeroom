"""The camera's sharpening found and taken out, and the photographer's sharpness and clarity."""
import unittest

import cv2
import numpy as np

from dyeroom import detail


def scene(size=1024, seed=3):
    """Flat patches of many brightnesses with clean edges, as a lens draws them (a slight blur)."""
    rng = np.random.default_rng(seed)
    img = np.full((size, size), 0.45, np.float32)
    for _ in range(160):
        y, x = rng.integers(0, size - 40, 2)
        h, w = rng.integers(40, 160, 2)
        img[y:y + h, x:x + w] = rng.uniform(0.1, 0.8)
    img = cv2.GaussianBlur(img, (0, 0), 1.0)
    return img + rng.normal(0, 0.002, img.shape).astype(np.float32)


def sharpen(img, radius=1.5, amount=1.5):
    """An unsharp mask, as a phone applies it to what it saves."""
    return np.clip(img + amount * (img - cv2.GaussianBlur(img, (0, 0), radius)), 0, 1).astype(np.float32)


class Measure(unittest.TestCase):
    def test_plain_picture(self):
        self.assertEqual(detail.measure(np.full((300, 400), 0.5, np.float32)), (0.0, 0.0))

    def test_unsharpened_is_left_alone(self):
        self.assertEqual(detail.measure(scene()), (0.0, 0.0))

    def test_sharpening_is_found(self):
        """Roughly: the blend and radius are what takes the halos out, not the mask's own numbers."""
        for radius, amount in ((1.0, 1.0), (1.5, 1.5), (2.0, 1.0)):
            strength, found = detail.measure(sharpen(scene(), radius, amount))
            self.assertTrue(0.3 <= strength <= 0.7, (radius, amount, strength))
            self.assertTrue(radius / 2 <= found <= radius * 2, (radius, amount, found))

    def test_taken_out(self):
        """Undone on the linear picture, the halos are gone."""
        sharp = sharpen(scene())
        linear = np.repeat((sharp ** 2.2)[..., None], 3, axis=2)
        out = detail.apply(linear, detail.measure(sharp))
        encoded = np.clip(out[..., 1], 0, None) ** (1 / 2.2)
        self.assertEqual(detail.measure(encoded), (0.0, 0.0))


class Apply(unittest.TestCase):
    def setUp(self):
        self.rgb = np.repeat((scene(512) ** 2.2)[..., None], 3, axis=2)

    def edges(self, rgb):
        y = rgb[..., 1] ** (1 / 2.2)
        return float(np.abs(cv2.Laplacian(y, cv2.CV_32F)).mean())

    def test_nothing_to_do(self):
        self.assertIs(detail.apply(self.rgb), self.rgb)

    def test_sharpness_both_ways(self):
        self.assertLess(self.edges(detail.apply(self.rgb, sharpness=-100)), self.edges(self.rgb))
        self.assertGreater(self.edges(detail.apply(self.rgb, sharpness=100)), self.edges(self.rgb))

    def test_clarity_keeps_the_light(self):
        for clarity in (-100, 100):
            out = detail.apply(self.rgb, clarity=clarity)
            self.assertFalse(np.allclose(out, self.rgb))
            self.assertLess(abs(np.log(out.mean() / self.rgb.mean())), 0.1)

    def test_colour_is_kept(self):
        tinted = self.rgb * np.array([1.0, 0.8, 0.5], np.float32)
        out = detail.apply(tinted, sharpness=-60, clarity=50)
        ratio = out[..., 2] / np.maximum(out[..., 0], 1e-6)
        bright = tinted[..., 0] > 0.05
        self.assertLess(np.abs(ratio[bright] - 0.5).max(), 0.05)


if __name__ == "__main__":
    unittest.main()
