"""The dyeroom command's lab on this computer: its settings, and the icon it adds."""
import plistlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from dyeroom import local


class Settings(unittest.TestCase):
    def test_a_private_lab(self):
        s = local.settings(8123, "secret")
        self.assertEqual((s["DYEROOM_LOCAL"], s["DYEROOM_LOCAL_KEY"], s["HOST"], s["PORT"]),
                         ("1", "secret", "127.0.0.1", "8123"))
        self.assertIn("127.0.0.1", s["DYEROOM_UNLIMITED"])
        self.assertEqual(s["DYEROOM_ACCOUNTS"], "0")
        data, cache = local.folders()
        self.assertEqual(Path(s["DYEROOM_WORK"]).parent, cache)

    def test_workers_fit_the_computer(self):
        cases = ((12, 24, 3), (8, 16, 2), (4, 8, 1), (2, 4, 1), (32, 128, 4))
        for cores, memory, expected in cases:
            with mock.patch("os.cpu_count", return_value=cores), mock.patch.object(local, "memory_gb", return_value=memory):
                self.assertEqual(local.workers(), expected, (cores, memory))


class Versions(unittest.TestCase):
    def test_newer(self):
        self.assertTrue(local.newer("0.5.1", "0.5.0"))
        self.assertTrue(local.newer("0.10.0", "0.9.9"))
        self.assertFalse(local.newer("0.5.0", "0.5.0"))
        self.assertFalse(local.newer(None, "0.5.0"))


class Starting(unittest.TestCase):
    def test_a_window_at_once(self):
        """The starting page opens before the lab answers, and knows where the lab will be."""
        opened = []
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(local, "folders",
                                                                     return_value=(Path(tmp), Path(tmp))):
            folder = local._starting_window(opened.append, "http://127.0.0.1:8123/app?key=abc")
            page = (folder / "index.html").read_text(encoding="utf-8")
            self.assertEqual(opened, [(folder / "index.html").as_uri()])
            self.assertIn('"http://127.0.0.1:8123/app?key=abc"', page)
            self.assertIn("ready.png", page)
            self.assertFalse((folder / "ready.png").exists())


@unittest.skipUnless(sys.platform == "darwin" or sys.platform.startswith("linux"), "macOS and Linux")
class Shortcut(unittest.TestCase):
    def test_opens_the_lab(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.dict("os.environ", {"XDG_DATA_HOME": ""}):
            if sys.platform.startswith("linux"):
                import os
                os.environ["XDG_DATA_HOME"] = str(Path(home) / ".local" / "share")
            made = local.shortcut(home)
            if sys.platform == "darwin":
                info = plistlib.loads((made / "Contents" / "Info.plist").read_bytes())
                self.assertEqual(info["CFBundleIdentifier"], "com.sysi.dyeroom")
                launcher = (made / "Contents" / "MacOS" / "Dyeroom").read_text(encoding="utf-8")
            else:
                launcher = made.read_text(encoding="utf-8")
            self.assertIn(f'"{sys.executable}" -I -m dyeroom.local open', launcher)


if __name__ == "__main__":
    unittest.main()
