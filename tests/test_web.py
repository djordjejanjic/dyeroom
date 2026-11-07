"""The web app around the developer: fair queue, limits, the roll ZIP, legal pages, security
headers, statistics, and the film format.

Run:  .venv/bin/python -m unittest discover -s tests      (needs httpx: pip install -e ".[test]")
"""
import collections
import io
import json
import os
import tempfile
import time
import unittest
from unittest import mock
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

_DIR = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)  # Windows: the app's databases are open
os.environ.update(DYEROOM_DATA=_DIR.name, DYEROOM_WORK=str(Path(_DIR.name) / "work"), DYEROOM_ACCOUNTS="0")
for _name in ("DYEROOM_LEGAL_NAME", "DYEROOM_LEGAL_ADDRESS", "DYEROOM_CONTACT_EMAIL", "DYEROOM_LEGAL_COUNTRY",
              "DYEROOM_HOSTING", "DYEROOM_USER", "DYEROOM_PASSWORD"):
    os.environ.pop(_name, None)

from fastapi.testclient import TestClient  # noqa: E402

from dyeroom import capture  # noqa: E402
from dyeroom.web import app as web, limits, pages, stats  # noqa: E402

client = TestClient(web.app)


def fake_job(name="DSCF0001.RAF", film="sunday64", shape=(40, 60)):
    """A finished development as the worker leaves it, without running the developer."""
    job_id = os.urandom(16).hex()
    job_dir = web.JOBS / job_id
    job_dir.mkdir()
    rng = np.random.default_rng(1)
    (job_dir / "params.json").write_text(json.dumps({"source": f"/nowhere/{name}", "name": name, "film": film,
                                                     "display": "srgb", "upload_id": None}), encoding="utf-8")
    np.save(job_dir / "slide16.npy", rng.integers(0, 65535, (*shape, 3), dtype=np.uint16))
    (job_dir / "status.json").write_text(json.dumps({"state": "done", "info": {}}), encoding="utf-8")
    return job_id


class FairQueue(unittest.TestCase):
    def tearDown(self):
        web._queues.clear()

    def test_one_from_each_person_in_turn(self):
        web._queues.update({"a": collections.deque(["a1", "a2", "a3"]), "b": collections.deque(["b1"]),
                            "c": collections.deque(["c1", "c2"])})
        self.assertEqual(web._order(), ["a1", "b1", "c1", "a2", "c2", "a3"])

    def test_one_full_size_at_a_time(self):
        """With two workers, a full-size development waits for another full-size one; drafts do not."""
        web._jobs.update({"big": {"person": "x", "size": "full", "queued": 0, "started": 1},
                          "full2": {"person": "a", "size": "full", "queued": 0},
                          "draft": {"person": "b", "size": "draft", "queued": 0}})
        try:
            self.assertFalse(web._may_start("full2"))
            self.assertTrue(web._may_start("draft"))
            web._jobs.pop("big")
            self.assertTrue(web._may_start("full2"))
        finally:
            for job_id in ("big", "full2", "draft"):
                web._jobs.pop(job_id, None)

    def test_wait_counts_work_ahead(self):
        web._queues.update({"a": collections.deque(["a1", "a2"]), "b": collections.deque(["b1"])})
        for job_id in ("a1", "a2", "b1"):
            web._jobs[job_id] = {"person": job_id[0], "size": "draft", "queued": time.time()}
        web._jobs["run"] = {"person": "x", "size": "draft", "queued": time.time(), "started": time.time()}
        try:
            ahead, wait = web._waiting_for("a2")
            self.assertEqual(ahead, 2)  # a1, then b1, then a2
            self.assertGreater(wait, 0)
        finally:
            for job_id in ("a1", "a2", "b1", "run"):
                web._jobs.pop(job_id, None)


class Limits(unittest.TestCase):
    def test_sliding_window(self):
        window = limits.Window(2, 60)
        self.assertEqual(window.wait("k", now=100), 0)
        self.assertEqual(window.wait("k", now=110), 0)
        self.assertAlmostEqual(window.wait("k", now=120), 40)
        self.assertEqual(window.wait("other", now=120), 0)
        self.assertEqual(window.wait("k", now=161), 0)
        window.prune(now=1000)
        self.assertFalse(window.events)

    def test_unlimited(self):
        keys = limits._unlimited(" 192.0.2.7, 2001:db8:1:2::5,acct1 ,")
        self.assertEqual(keys, {"ip:192.0.2.7", "sample:192.0.2.7", "ip:2001:db8:1:2::/64",
                                "sample:2001:db8:1:2::/64", "u:acct1"})
        old, limits.UNLIMITED = limits.UNLIMITED, keys
        try:
            window = limits.Window(1, 60)
            for now in (100, 101, 102):
                self.assertEqual(window.wait("ip:192.0.2.7", now=now), 0)
            self.assertEqual(window.wait("ip:192.0.2.8", now=100), 0)
            self.assertGreater(window.wait("ip:192.0.2.8", now=101), 0)
            self.assertTrue(limits.unlimited("u:acct1"))
        finally:
            limits.UNLIMITED = old

    def test_ipv6_counts_by_household(self):
        class Request:
            def __init__(self, host):
                self.client = type("C", (), {"host": host})
        self.assertEqual(limits.address(Request("2001:db8:1:2::5")), limits.address(Request("2001:db8:1:2:aa::9")))
        self.assertNotEqual(limits.address(Request("2001:db8:1:2::5")), limits.address(Request("2001:db8:1:3::5")))
        self.assertEqual(limits.address(Request("::ffff:192.0.2.7")), "192.0.2.7")
        self.assertEqual(limits.address(Request("192.0.2.7")), "192.0.2.7")
        self.assertEqual(limits.address(Request("testclient")), "testclient")

    def test_address_from_cloudflare(self):
        class Request:
            client = type("C", (), {"host": "172.18.0.3"})  # the tunnel, as the app sees it
            headers = {"cf-connecting-ip": "2001:db8:1:2::5", "x-forwarded-for": "6.6.6.6, 2001:db8:1:2::5"}
        old, limits.CLIENT_IP_HEADER = limits.CLIENT_IP_HEADER, "cf-connecting-ip"
        try:
            self.assertEqual(limits.address(Request()), "2001:db8:1:2::/64")
        finally:
            limits.CLIENT_IP_HEADER = old
        self.assertEqual(limits.address(Request()), "172.18.0.3")  # not believed unless told to

    def test_adding_the_sample_is_not_developing_it(self):
        """Only developing the sample counts against its allowance, not linking it in."""
        key = "sample:testclient"
        before = len(limits.SAMPLES.events.get(key, ()))
        for _ in range(3):
            self.assertEqual(client.post("/api/sample").status_code, 200)
        self.assertEqual(len(limits.SAMPLES.events.get(key, ())), before)

    def test_too_many_waiting(self):
        sample = client.post("/api/sample").json()["upload_id"]
        who = "ip:testclient"
        web._queues[who] = collections.deque(f"{i:032x}" for i in range(limits.WAITING))
        try:
            response = client.post("/api/jobs", json={"upload_id": sample, "ev": 0.1})
            self.assertEqual(response.status_code, 429)
            self.assertIn("Retry-After", response.headers)
        finally:
            web._queues.pop(who, None)


class Detail(unittest.TestCase):
    """Sharpness and clarity are development settings, from -100 to 100, and part of presets."""

    def test_out_of_range_is_refused(self):
        sample = client.post("/api/sample").json()["upload_id"]
        for key in ("sharpness", "clarity"):
            response = client.post("/api/jobs", json={"upload_id": sample, key: 150})
            self.assertEqual(response.status_code, 422)

    def test_in_presets(self):
        kept = web._clean_preset({"sharpness": 40, "clarity": -500, "ev": 0})
        self.assertEqual(kept["sharpness"], 40)
        self.assertNotIn("clarity", kept)


class Parts(unittest.TestCase):
    """A large photograph comes in parts small enough for any proxy on the way."""

    def setUp(self):
        self.old, web.PART_BYTES = web.PART_BYTES, 1024

    def tearDown(self):
        web.PART_BYTES = self.old

    def start(self, data, name="DSCF0002.RAF"):
        return client.post("/api/uploads/start", json={"name": name, "bytes": len(data)})

    def test_a_photograph_in_parts(self):
        data = os.urandom(2500)
        reply = self.start(data).json()
        upload_id, size = reply["upload_id"], reply["part_bytes"]
        parts = [data[i:i + size] for i in range(0, len(data), size)]
        self.assertEqual(client.put(f"/api/uploads/{upload_id}/1", content=parts[1]).status_code, 409)
        for i, part in enumerate(parts):
            self.assertEqual(client.put(f"/api/uploads/{upload_id}/{i}", content=part).status_code, 200)
        # a part sent again, its answer lost on the way, is not added twice
        self.assertEqual(client.put(f"/api/uploads/{upload_id}/0", content=parts[0]).json()["received"], len(data))
        done = client.post(f"/api/uploads/{upload_id}/finish")
        self.assertEqual(done.status_code, 200)
        self.assertEqual(done.json(), {"upload_id": upload_id, "name": "DSCF0002.RAF", "bytes": len(data)})
        self.assertEqual(next((web.UPLOADS / upload_id).iterdir()).read_bytes(), data)
        self.assertNotIn(upload_id, web._partial)

    def test_parts_are_checked(self):
        data = os.urandom(3000)
        upload_id = self.start(data).json()["upload_id"]
        self.assertEqual(client.put(f"/api/uploads/{upload_id}/0", content=os.urandom(2000)).status_code, 413)
        self.assertEqual(client.put(f"/api/uploads/{upload_id}/0", content=data[:500]).status_code, 400)
        self.assertEqual(client.post(f"/api/uploads/{upload_id}/finish").status_code, 400)
        self.assertEqual(client.put(f"/api/uploads/{'0' * 32}/0", content=data[:1024]).status_code, 404)
        self.assertEqual(self.start(data, name="notes.txt").status_code, 415)


class Previews(unittest.TestCase):
    """A photograph is shown as it came in until it is developed, and its preview goes with it."""

    def upload(self, data, name):
        return client.post("/api/uploads", files={"file": (name, data, "application/octet-stream")}).json()["upload_id"]

    def wait(self, upload_id, name="preview.jpg"):
        for _ in range(200):
            reply = client.get(f"/api/uploads/{upload_id}/{name}")
            if reply.status_code != 202:
                return reply
            time.sleep(0.05)
        self.fail("no preview")

    def test_made_served_and_deleted(self):
        buf = io.BytesIO()
        Image.new("RGB", (900, 600), (200, 120, 70)).save(buf, "JPEG")
        upload_id = self.upload(buf.getvalue(), "IMG_0001.JPG")
        reply = self.wait(upload_id)
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(Image.open(io.BytesIO(reply.content)).size, (900, 600))
        self.assertEqual(Image.open(io.BytesIO(self.wait(upload_id, "thumb.jpg").content)).size, (360, 240))
        client.post("/api/forget", json={"uploads": [upload_id]})
        web._sweep()
        self.assertFalse((web.PREVIEWS / upload_id).exists())
        self.assertEqual(client.get(f"/api/uploads/{upload_id}/preview.jpg").status_code, 404)

    def test_none_for_what_cannot_be_read(self):
        upload_id = self.upload(os.urandom(4000), "DSCF0003.RAF")
        self.assertEqual(self.wait(upload_id).status_code, 404)
        self.assertEqual(client.get(f"/api/uploads/{upload_id}/other.jpg").status_code, 404)
        self.assertEqual(client.get(f"/api/uploads/{'0' * 32}/preview.jpg").status_code, 404)

    def test_upright_and_greys_kept(self):
        from dyeroom.web import preview
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            preview.write(preview.read(Path(__file__).with_name("data") / "sideways-p3.heic"), out)
            self.assertEqual(Image.open(out / "preview.jpg").size, (80, 120))  # stored 120 x 80, shown turned
            grey = Image.fromarray(np.full((40, 60), 30000, np.uint16))  # 16-bit, a little under half
            grey.save(out / "grey.png")
            preview.write(preview.read(out / "grey.png"), out)
            self.assertAlmostEqual(np.asarray(Image.open(out / "preview.jpg").convert("L")).mean(), 117, delta=3)


class Local(unittest.TestCase):
    """The lab on the photographer's own computer: this computer only, with the key of this start."""

    def setUp(self):
        self.old = web.LOCAL, web.LOCAL_KEY
        web.LOCAL, web.LOCAL_KEY = True, "k" * 32
        self.here = TestClient(web.app, base_url="http://127.0.0.1:8123")

    def tearDown(self):
        web.LOCAL, web.LOCAL_KEY = self.old

    def test_only_this_computer(self):
        """A website's name pointed at this computer (DNS rebinding) is turned away, key or not."""
        far = TestClient(web.app, base_url="http://evil.example:8123")
        self.assertEqual(far.get("/api/options", cookies={web.LOCAL_COOKIE: "k" * 32}).status_code, 403)

    def test_the_key_opens_it(self):
        self.assertEqual(self.here.get("/api/options").status_code, 403)
        self.assertEqual(self.here.get("/api/options", cookies={web.LOCAL_COOKIE: "wrong"}).status_code, 403)
        opened = self.here.get("/app?key=" + "k" * 32, follow_redirects=False)
        self.assertEqual(opened.status_code, 303)
        self.assertEqual(opened.headers["location"], "/app")
        self.assertIn("samesite=strict", opened.headers["set-cookie"].lower())
        self.assertIn("httponly", opened.headers["set-cookie"].lower())
        options = self.here.get("/api/options", cookies={web.LOCAL_COOKIE: "k" * 32})
        self.assertEqual(options.status_code, 200)
        self.assertTrue(options.json()["local"])

    def test_home_is_the_lab(self):
        home = self.here.get("/", cookies={web.LOCAL_COOKIE: "k" * 32}, follow_redirects=False)
        self.assertEqual((home.status_code, home.headers["location"]), (303, "/app"))

    def test_full_size_must_fit_this_computer(self):
        """A photograph too large to develop at full size in this computer's memory is refused, with why."""
        buf = io.BytesIO()
        Image.new("RGB", (300, 200), (120, 110, 100)).save(buf, "JPEG")
        upload_id = self.here.post("/api/uploads", files={"file": ("big.jpg", buf.getvalue(), "image/jpeg")},
                                   cookies={web.LOCAL_COOKIE: "k" * 32}).json()["upload_id"]
        for _ in range(200):
            if web._previews.get(upload_id) != "making":
                break
            time.sleep(0.05)
        (web.PREVIEWS / upload_id / "size.json").write_text('{"width": 9504, "height": 6336}', encoding="utf-8")  # 60 MP
        with mock.patch.object(web.local, "memory_gb", return_value=12.0):  # 60 MP needs about 10.5 GB
            refused = self.here.post("/api/jobs", json={"upload_id": upload_id, "size": "full"},
                                     cookies={web.LOCAL_COOKIE: "k" * 32})
        self.assertEqual(refused.status_code, 422)
        self.assertIn("60 megapixels", refused.json()["detail"])
        self.assertIn("draft", refused.json()["detail"])
        with mock.patch.object(web.local, "memory_gb", return_value=64.0):
            self.assertIsNone(web._too_big_for_full_size(upload_id))

    def test_newer_version_is_told(self):
        reply = mock.MagicMock()
        reply.__enter__.return_value.read.return_value = b'{"info": {"version": "9.0.0"}}'
        (web.DATA / "version.json").unlink(missing_ok=True)
        with mock.patch.object(web.urllib.request, "urlopen", return_value=reply), \
                mock.patch.object(web.local, "version", return_value="0.5.0"):
            web._check_for_update()
        try:
            self.assertEqual(web._update, "9.0.0")
            self.assertEqual(self.here.get("/api/options", cookies={web.LOCAL_COOKIE: "k" * 32}).json()["update"], "9.0.0")
        finally:
            web._update = None
            (web.DATA / "version.json").unlink(missing_ok=True)

    def test_installer_is_served(self):
        web.LOCAL = False
        script = client.get("/install.sh")
        self.assertEqual(script.status_code, 200)
        self.assertTrue(script.text.startswith("#!/bin/sh"))
        windows = client.get("/install.ps1")
        self.assertEqual(windows.status_code, 200)
        self.assertIn("uv tool install", windows.text)
        self.assertEqual(client.get("/install.bat").status_code, 404)


class Admin(unittest.TestCase):
    def test_password_when_there_are_no_accounts(self):
        self.assertEqual(client.get("/admin").status_code, 404)  # no way in set: it isn't there
        web.ADMIN_PASSWORD = "a long test password"
        try:
            asked = client.get("/admin")
            self.assertEqual(asked.status_code, 401)
            self.assertIn("Basic", asked.headers["www-authenticate"])
            self.assertEqual(client.get("/admin", auth=("admin", "wrong")).status_code, 401)
            page = client.get("/admin", auth=("admin", "a long test password"))
            self.assertEqual(page.status_code, 200)
            self.assertEqual(page.headers["x-robots-tag"], "noindex")
        finally:
            web.ADMIN_PASSWORD = ""


class Site(unittest.TestCase):
    """The home page at / is for people and search engines; the app at /app is kept out of search."""

    def test_home(self):
        page = client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn("<title>Dyeroom: develop your raw photos on simulated film</title>", page.text)
        self.assertIn('<meta name="description"', page.text)
        self.assertIn('content="index,follow', page.text)
        self.assertIn('"isAccessibleForFree":true', page.text)
        self.assertIn('href="/app?sample=1"', page.text)
        self.assertNotIn("X-Robots-Tag", page.headers)

    def test_app_is_not_for_search(self):
        page = client.get("/app")
        self.assertIn('<meta name="robots" content="noindex">', page.text)
        self.assertEqual(page.headers["x-robots-tag"], "noindex")
        robots = client.get("/robots.txt").text
        self.assertIn("Disallow: /api/", robots)
        self.assertNotIn("Disallow: /app", robots)  # it must be read to see its noindex
        self.assertIn("User-agent: GPTBot", robots)  # AI training: no
        self.assertNotIn("OAI-SearchBot", robots)    # AI search: welcome, under *

    def test_sitemap_lists_finished_pages(self):
        xml = client.get("/sitemap.xml").text
        self.assertIn("/</loc>", xml)
        self.assertNotIn("/terms", xml)  # the legal pages still have gaps here
        self.assertNotIn("/app", xml)

    def test_films_and_guides(self):
        """Every page in content/ is served, finished, with its data for search and nothing left to fill."""
        for path, item in web.CONTENT.items():
            page = client.get(path)
            self.assertEqual(page.status_code, 200, path)
            self.assertIn(f"<h1>{item.h1}</h1>", page.text.replace("&#x27;", "'"))
            self.assertIn('"BreadcrumbList"', page.text)
            self.assertIn('"AboutPage"' if path == "/about" else '"Article"', page.text)
            for left in ("[figure", "[IMAGE", "[CHECK", "OWNER TO FILL", "{subject}", "**", "<!--"):
                self.assertNotIn(left, page.text, path)
        self.assertGreaterEqual(len(web.CONTENT), 10)
        self.assertIn('href="/films/sunday-64"', client.get("/films").text)
        self.assertIn('href="/guides/how-slide-film-was-developed"', client.get("/guides").text)
        self.assertEqual(client.get("/guides/no-such-guide").status_code, 404)

    def test_content_links_and_pictures(self):
        """No page links to a page or heading that does not exist, and every picture is there."""
        from dyeroom.web import content
        self.assertEqual(content.broken_links(web.CONTENT), [])
        for item in web.CONTENT.values():
            for src in [item.image, *(line.split(" | ")[0] for line in item.body.splitlines() if line.startswith("/static/"))]:
                self.assertTrue((Path(web.STATIC) / src.removeprefix("/static/")).exists(), src)
        sunday = client.get("/films/sunday-64").text
        self.assertIn('id="light-box-or-projector"', sunday)  # linked to from the guides
        self.assertIn('href="/app?sample=1&amp;film=sunday64"', sunday)

    def test_sitemap_lists_films_and_guides(self):
        xml = client.get("/sitemap.xml").text
        self.assertIn("/films/sunday-64</loc><lastmod>", xml)
        self.assertIn("/guides</loc>", xml)
        self.assertIn("/about</loc>", xml)

    def test_not_found(self):
        page = client.get("/no-such-page")
        self.assertEqual(page.status_code, 404)
        self.assertIn("Nothing here", page.text)
        self.assertIn('content="noindex"', page.text)
        self.assertEqual(client.get("/api/no-such-thing").headers["content-type"], "application/json")
        self.assertEqual(client.get("/favicon.ico").status_code, 200)


class Requests(unittest.TestCase):
    def test_security_headers(self):
        headers = client.get("/").headers
        self.assertIn("frame-ancestors 'none'", headers["content-security-policy"])
        self.assertEqual(headers["x-content-type-options"], "nosniff")

    def test_bodies_must_say_their_size(self):
        self.assertEqual(client.post("/api/keep", content=iter([b'{"uploads": []}']),
                                     headers={"Content-Type": "application/json"}).status_code, 411)
        big = b'{"uploads": []}' + b" " * (web.MAX_JSON + 1)
        self.assertEqual(client.post("/api/keep", content=big, headers={"Content-Type": "application/json"}).status_code,
                         413)

    def test_upload_name_cannot_start_with_a_dash(self):
        response = client.post("/api/uploads", files={"file": ("-config.jpg", b"not really a jpeg", "image/jpeg")})
        self.assertEqual(response.status_code, 200)
        stored = next((web.UPLOADS / response.json()["upload_id"]).iterdir()).name
        self.assertFalse(stored.startswith("-"))


class RollExport(unittest.TestCase):
    def test_zip_holds_every_frame_with_its_adjustments(self):
        a, b = fake_job("DSCF0001.RAF"), fake_job("DSCF0001.RAF")  # same name twice
        gone = os.urandom(16).hex()
        response = client.post("/api/rolls", json={"format": "jpg", "frames": [
            {"job_id": a, "adjust": {}}, {"job_id": b, "adjust": {"bands": {"red": [0, 50, 0]}}},
            {"job_id": gone, "adjust": {}}]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["frames"], 2)
        archive = client.get(f"/api/rolls/{response.json()['roll_id']}.zip")
        self.assertEqual(archive.status_code, 200)
        self.assertIn("attachment", archive.headers["content-disposition"])
        with zipfile.ZipFile(io.BytesIO(archive.content)) as z:
            names = z.namelist()
            self.assertEqual(names, ["DSCF0001_sunday64.jpg", "DSCF0001_sunday64 (2).jpg"])
            for name in names:
                self.assertEqual(Image.open(io.BytesIO(z.read(name))).size, (60, 40))

    def test_framing_reaches_the_export(self):
        job = fake_job("frame.raf", shape=(40, 60))
        cropped = client.post(f"/api/jobs/{job}/export", json={"format": "jpg", "geometry": {
            "turns": 1, "angle": 3.0, "crop": {"x": 0.1, "y": 0.2, "w": 0.5, "h": 0.25}}})
        self.assertEqual(cropped.status_code, 200)
        self.assertEqual(Image.open(io.BytesIO(cropped.content)).size, (20, 15))  # turned: 40 wide, 60 high
        roll = client.post("/api/rolls", json={"format": "jpg", "frames": [
            {"job_id": job, "geometry": {"crop": {"x": 0, "y": 0, "w": 0.5, "h": 0.5}}}]}).json()["roll_id"]
        with zipfile.ZipFile(io.BytesIO(client.get(f"/api/rolls/{roll}.zip").content)) as z:
            self.assertEqual(Image.open(io.BytesIO(z.read(z.namelist()[0]))).size, (30, 20))

    def test_tiff_roll(self):
        job = fake_job("frame.dng", film="monday400")
        roll = client.post("/api/rolls", json={"format": "tif", "frames": [{"job_id": job}]}).json()["roll_id"]
        with zipfile.ZipFile(io.BytesIO(client.get(f"/api/rolls/{roll}.zip").content)) as z:
            self.assertEqual(z.namelist(), ["frame_monday400.tif"])

    def test_unknown_roll(self):
        self.assertEqual(client.get(f"/api/rolls/{'0' * 32}.zip").status_code, 404)
        self.assertEqual(client.get("/api/rolls/..%2F..%2Fetc.zip").status_code, 404)


class LegalPages(unittest.TestCase):
    def test_pages_are_public_and_filled(self):
        """The tests run the free lab: no accounts, nothing sold, so no refund policy."""
        for path in ("/terms", "/privacy"):
            page = client.get(path)
            self.assertEqual(page.status_code, 200)
            self.assertNotIn("{{", page.text)
            self.assertNotIn("<!--", page.text)
            self.assertNotIn('href="/refunds"', page.text)
        self.assertEqual(client.get("/refunds").status_code, 404)
        terms, privacy = client.get("/terms").text, client.get("/privacy").text
        self.assertIn("Free to use, and fair", terms)
        self.assertNotIn("Merchant of Record", terms)
        self.assertIn("Dyeroom sets no cookies", privacy)
        self.assertNotIn("dyeroom_session", privacy)

    def test_with_accounts_and_payments(self):
        facts = {"accounts": True, "in_memory": False, "idle_minutes": 30, "keep_hours": 3}
        terms, refunds = pages.legal("terms", facts), pages.legal("refunds", facts)
        self.assertIn("Paddle.com is the Merchant of Record for all our orders", terms)
        self.assertNotIn("Free to use, and fair", terms)
        self.assertIn("within 30 days", refunds)
        self.assertIn('href="/refunds"', terms)
        self.assertIn("dyeroom_session", pages.legal("privacy", facts))

    def test_gaps_are_shown_until_set(self):
        self.assertIn('<mark class="gap">DYEROOM_LEGAL_NAME</mark>', client.get("/terms").text)
        self.assertFalse(client.get("/api/health").json()["legal_pages"])
        os.environ.update(DYEROOM_LEGAL_NAME="Ana Example PR", DYEROOM_LEGAL_ADDRESS="1 Street, Town",
                          DYEROOM_CONTACT_EMAIL="hello@example.com", DYEROOM_LEGAL_COUNTRY="Serbia",
                          DYEROOM_HOSTING="by Example Hosting in Germany")
        try:
            text = client.get("/privacy").text
            self.assertNotIn("<mark", text)
            self.assertIn("Ana Example PR", text)
            self.assertTrue(client.get("/api/health").json()["legal_pages"])
        finally:
            for name in ("DYEROOM_LEGAL_NAME", "DYEROOM_LEGAL_ADDRESS", "DYEROOM_CONTACT_EMAIL",
                         "DYEROOM_LEGAL_COUNTRY", "DYEROOM_HOSTING"):
                os.environ.pop(name)

    def test_admin_is_hidden(self):
        self.assertEqual(client.get("/admin").status_code, 404)


class Statistics(unittest.TestCase):
    def test_summary_and_typical_time(self):
        s = stats.Stats(Path(_DIR.name) / "stats-test.db")
        self.assertEqual(s.typical_seconds("full"), stats.TYPICAL["full"])
        for seconds in (10, 12, 14):
            s.job("sunday64", "draft", "35mm", False, 1, 2.0, seconds, seconds * 3, 900, 5.8, ".raf", None)
        s.job("sunday64", "draft", "35mm", False, 0, 1.0, 3, 1, 300, None, ".cr3", "LibRaw: unsupported")
        self.assertEqual(s.typical_seconds("draft"), 12)
        day = s.summary()[0]
        self.assertEqual((day["jobs"], day["failed"]), (4, 1))
        self.assertEqual(day["sizes"]["draft"]["median_cpu"], 36)
        self.assertEqual(len(s.failures(time.time() - 60)), 1)
        self.assertAlmostEqual(stats.cost_per_frame(36, 4, eur_month=40.0), 40.0 / (4 * 30 * 86400) * 36)
        self.addCleanup(s.close)
        page = pages.admin({"waiting": 0, "oldest_wait": 0, "developing": 0, "workers": 1, "photos_held": 0,
                            "held_gb": 0, "space_free_gb": 1, "space_gb": 2, "in_memory": True, "cores": 4,
                            "last_backup": None, "alerts_to": False, "legal_missing": []},
                           s.summary(), [], s.failures(0), s.recent_alerts())
        self.assertIn("LibRaw: unsupported", page)


class Framing(unittest.TestCase):
    def test_turns_crop_and_rotation(self):
        from dyeroom import adjust
        image = np.arange(4 * 6 * 3, dtype=np.uint16).reshape(4, 6, 3)
        turned = adjust.frame(image, {"turns": 1})
        self.assertEqual(turned.shape, (6, 4, 3))
        np.testing.assert_array_equal(turned[0, :, 0], image[::-1, 0, 0])  # clockwise, as CSS rotates
        np.testing.assert_array_equal(adjust.frame(image, {"crop": {"x": 1 / 6, "y": 0.25, "w": 0.5, "h": 0.5}}),
                                      image[1:3, 1:4])
        ramp = np.tile(np.linspace(0, 60000, 600, dtype=np.float32), (400, 1))[..., None].repeat(3, 2).astype(np.uint16)
        nudged = adjust.frame(ramp, {"angle": 0.01}).astype(float)
        self.assertLess(np.abs(nudged[50:-50, 50:-50] - ramp[50:-50, 50:-50]).max(), 10)  # turns about the centre

    def test_bad_framing_is_ignored(self):
        from dyeroom import adjust
        self.assertTrue(adjust.geometry_is_identity({"turns": True, "angle": float("nan"), "crop": {"x": "a"}}))
        self.assertEqual(adjust.clean_geometry({"turns": 7, "angle": 90, "crop": {"x": 0.5, "y": 0, "w": 0.9, "h": 1}}),
                         {"turns": 3, "angle": 45.0, "crop": {"x": 0.5, "y": 0.0, "w": 0.5, "h": 1.0}})


class FilmFormat(unittest.TestCase):
    def test_picture_fills_the_frame_as_its_shape_allows(self):
        self.assertAlmostEqual(capture.um_per_px((4000, 6000), "35mm"), 6.0)
        self.assertAlmostEqual(capture.um_per_px((3888, 5184), "35mm"), 24000 / 3888)  # 4:3 uses 32 x 24 mm
        self.assertAlmostEqual(capture.um_per_px((4000, 6000), "6x6"), 56000 / 6000)
        self.assertAlmostEqual(capture.um_per_px((6000, 4000), "6x7"), 69500 / 6000)  # upright: the long side limits
        self.assertGreater(capture.um_per_px((4000, 6000), "645"), capture.um_per_px((4000, 6000), "35mm"))


if __name__ == "__main__":
    unittest.main()
