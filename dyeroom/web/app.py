"""Dyeroom web app: drop photographs in a browser, get Sunday 64 slides back.

Run:  dyeroom-web            (or: uvicorn dyeroom.web.app:app --host 0.0.0.0 --port 8000)

Configuration (environment):
  DYEROOM_DATA        accounts (the only thing kept)        (default ./web-data)
  DYEROOM_WORK        where photographs are held while you work: mount memory (tmpfs)
                         here so they never touch a disk      (default DYEROOM_DATA/work)
  DYEROOM_IDLE_MINUTES  photographs are deleted this long after the page stops using
                         them, or at once when it closes     (default 30)
  DYEROOM_KEEP_HOURS  and at the latest this long after upload (default 3)
  DYEROOM_WORKERS     photos developed at the same time     (default 1; ~3 GB each for
                         drafts, 6-7 GB for a full-size 20 MP raw, so full-size ones go
                         one at a time whatever the number)
  DYEROOM_MAX_MB      largest upload in MB                  (default 400)
  DYEROOM_DRAFT_EDGE  long edge of drafts in pixels         (default 2400)
  DYEROOM_FULL        allow full-resolution developing      (default 1)
  DYEROOM_TIMEOUT     seconds before a job is abandoned     (default 900)
  DYEROOM_USER / DYEROOM_PASSWORD   require HTTP basic auth when both are set
  DYEROOM_SAMPLE      raw file behind "Try a sample"        (default samples/ beside the package)
  DYEROOM_TRUSTED_PROXIES  addresses of the reverse proxy in front, whose X-Forwarded-For
                         is believed (default 127.0.0.1); fair-use limits count per address
  DYEROOM_ACCESS_LOG  1: log every request with its address (default off: no visit logs)
  DYEROOM_ADMIN_EMAILS  accounts that may open /admin, comma-separated
  DYEROOM_ADMIN_PASSWORD  or a password for /admin (user "admin"): the way in when there
                         are no accounts
  Limits: see limits.py. Alerts to your phone: see alerts.py. Legal pages: see pages.py.

Accounts and payments (off unless DYEROOM_ACCOUNTS=1):
  DYEROOM_ACCOUNTS    1: sign in with Apple or Google to develop your own photographs;
                         anyone may try the sample
  DYEROOM_FREE_FRAMES photographs free with a new account   (default 5)
  DYEROOM_PLAN_CAP    photographs per month on a plan       (default 1000)
  Sign-in: see sso.py. Payments: see billing.py. Accounts live in DYEROOM_DATA/accounts.db.
"""
import asyncio
import base64
import collections
import hashlib
import concurrent.futures
import json
import logging
import math
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import zipfile
from pathlib import Path

import numpy as np
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response, \
    StreamingResponse
from fastapi.exception_handlers import http_exception_handler
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from .. import adjust, colourise, metadata, mono, output, pipeline, spectra
from ..capture import FORMATS, RAW_SUFFIXES
from ..spectra import FILTERS
from ..viewing import VIEWINGS
from . import accounts, alerts, billing, content, limits, pages, site, sso, worker
from .stats import Stats

DATA = Path(os.environ.get("DYEROOM_DATA", "web-data")).resolve()
WORKERS = int(os.environ.get("DYEROOM_WORKERS", "1"))
MAX_BYTES = int(float(os.environ.get("DYEROOM_MAX_MB", "400")) * 1024 * 1024)
DRAFT_EDGE = int(os.environ.get("DYEROOM_DRAFT_EDGE", "2400"))
ALLOW_FULL = os.environ.get("DYEROOM_FULL", "1") not in ("0", "false", "no")
WORK = Path(os.environ.get("DYEROOM_WORK", DATA / "work")).resolve()
IDLE_SECONDS = float(os.environ.get("DYEROOM_IDLE_MINUTES", "30")) * 60
KEEP_SECONDS = float(os.environ.get("DYEROOM_KEEP_HOURS", "3")) * 3600
TIMEOUT = int(os.environ.get("DYEROOM_TIMEOUT", "900"))
AUTH = (os.environ.get("DYEROOM_USER"), os.environ.get("DYEROOM_PASSWORD"))
SAMPLE = Path(os.environ.get("DYEROOM_SAMPLE",
                             Path(__file__).resolve().parents[2] / "samples" / "sample-olympus-e-p7.orf"))
ACCOUNTS = os.environ.get("DYEROOM_ACCOUNTS", "0") not in ("0", "false", "no", "")
# Local mode: the lab on the photographer's own computer, started by the dyeroom command
# (dyeroom/local.py). Only this computer, with the key made at this start, gets in, and the lab
# stops once no window has been in touch for LOCAL_STOP_SECONDS and nothing is developing.
LOCAL = os.environ.get("DYEROOM_LOCAL", "0") in ("1", "true", "yes")
LOCAL_KEY = os.environ.get("DYEROOM_LOCAL_KEY", "")
LOCAL_COOKIE = "dyeroom_key"
LOCAL_STOP_SECONDS = 600
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # Windows: no console flashing up for each development
PUBLIC_URL = os.environ.get("DYEROOM_PUBLIC_URL", "").rstrip("/")
ADMINS = {e.strip().lower() for e in os.environ.get("DYEROOM_ADMIN_EMAILS", "").split(",") if e.strip()}
ADMIN_PASSWORD = os.environ.get("DYEROOM_ADMIN_PASSWORD", "")
SESSION_COOKIE, LOGIN_COOKIE = "dyeroom_session", "dyeroom_login"
MAX_JSON = 2 * 1024 * 1024  # largest request that is not a photograph
# A photograph larger than this goes up in parts of this size: each part is one request well
# under the 100 MB a proxy such as Cloudflare's free plan lets through, and a dropped
# connection costs one part, not the whole file.
PART_BYTES = 32 * 1024 * 1024
PART_PATH = re.compile(r"/api/uploads/[0-9a-f]{32}/\d+")
BACKUPS = DATA / "backups"

GONE = ("This photograph has been deleted from the lab: nothing is kept once you leave or stop working on it. "
        "Add it again to develop it.")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".heic", ".heif", ".tif", ".tiff", ".png"}
ACCEPTED = RAW_SUFFIXES | IMAGE_SUFFIXES
ID = re.compile(r"^[0-9a-f]{32}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
FILES = {"view.jpg": "image/jpeg", "before.jpg": "image/jpeg", "thumb.jpg": "image/jpeg", "early.jpg": "image/jpeg",
         "slide.jpg": "image/jpeg", "slide.tif": "image/tiff"}

# Photographs are not kept. Uploads and everything made from them live under PHOTOS only
# while someone works on them, and nothing there outlives the process: it is emptied at start.
PHOTOS = WORK / "dyeroom-photos"
UPLOADS, JOBS, SPILL = PHOTOS / "uploads", PHOTOS / "jobs", PHOTOS / "spill"
PREVIEWS = PHOTOS / "previews"  # a look at each photograph before it is developed (preview.py)
shutil.rmtree(PHOTOS, ignore_errors=True)
for _old in (DATA / "uploads", DATA / "jobs"):  # where earlier versions kept them
    shutil.rmtree(_old, ignore_errors=True)
for _dir in (UPLOADS, JOBS, SPILL, PREVIEWS):
    _dir.mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(SPILL)  # large uploads being received spill here, not to the system's disk

app = FastAPI(title="Dyeroom", docs_url=None, redoc_url=None, openapi_url=None)  # no public API schema
log = logging.getLogger("dyeroom.web")
store = accounts.Store(DATA / "accounts.db") if ACCOUNTS else None
stats = Stats(DATA / "stats.db")
# Photographs wait for the developer in one line per person, and the developer takes one from
# each person in turn: someone who drops a roll of 36 does not hold up the next person's one.
_queues = collections.OrderedDict()  # person -> job ids waiting
_jobs = {}                           # job id -> {person, size, queued, started} while queued or running
_lock = threading.Condition()
_typical = {}                        # size -> (when worked out, seconds a development usually takes)
_sample_jobs = {}  # settings -> job id: the sample developed once per setting, not once per click
_arrived, _used = {}, {}  # upload id -> when it arrived, when the page last used it
_held = {}                # upload id -> (person, bytes)
_partial = {}             # upload id -> an upload arriving in parts, until its last part
_forgotten = set()        # uploads the page has let go of
_sweep_now = threading.Event()
_exporting = threading.BoundedSemaphore(2)  # full-size exports at once: bounded memory
_rolls = {}               # roll id -> what to put in the ZIP, for ten minutes
_previews = {}            # upload id -> "making", "made" or "none"
_previewer = concurrent.futures.ThreadPoolExecutor(2)  # previews made at once: small, but each a decoder


# --- access ------------------------------------------------------------------------------

def _user(request):
    """The signed-in user (a row of accounts.users), or None."""
    token = request.cookies.get(SESSION_COOKIE) if store else None
    return store.user_for(token) if token else None


def _admin_password(request):
    """True when the request carries the admin password (HTTP Basic, user "admin")."""
    header = request.headers.get("authorization", "")
    if not (ADMIN_PASSWORD and header.startswith("Basic ")):
        return False
    try:
        user, _, password = base64.b64decode(header[6:]).decode().partition(":")
    except ValueError:
        return False
    return secrets.compare_digest(user, "admin") & secrets.compare_digest(password, ADMIN_PASSWORD)


def _base(request):
    return PUBLIC_URL or str(request.base_url).rstrip("/")


NOT_FOR_SEARCH = ("/api/", "/auth/", "/admin", "/licences", "/app")


def _secure(request):
    return _base(request).startswith("https:")


def _too_many(wait, message):
    """429 with the seconds to wait, which the page uses to try again by itself."""
    return HTTPException(429, message, headers={"Retry-After": str(max(1, math.ceil(wait)))})


def _held_by(who):
    return (sum(size for owner, size in list(_held.values()) if owner == who)
            + sum(p["size"] for p in list(_partial.values()) if p["who"] == who))


# Paddle's checkout runs in a frame from paddle.com and needs its script from there; nothing
# else on the page comes from anywhere but this server.
SECURITY_HEADERS = {
    # Cloudflare Web Analytics (counted without cookies) adds its script to the pages it carries.
    "Content-Security-Policy": "default-src 'self'; script-src 'self' https://*.paddle.com "
                               "https://static.cloudflareinsights.com; "
                               "style-src 'self' 'unsafe-inline' https://*.paddle.com; "
                               "img-src 'self' data: blob: https://*.paddle.com; "
                               "connect-src 'self' https://*.paddle.com https://cloudflareinsights.com; "
                               "frame-src https://*.paddle.com; "
                               "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin-allow-popups",
}


def _local_gate(request):
    """Local mode: the address must name this computer, not a website's name pointed at it, and
    the request must carry the key the dyeroom command opened the page with: given once in the
    address, then kept in a cookie that other websites' pages never send."""
    host = request.headers.get("host", "").rpartition(":")[0].strip("[]") or request.headers.get("host", "")
    if host not in ("127.0.0.1", "localhost", "::1"):
        return Response("Dyeroom answers only this computer", status_code=403, media_type="text/plain")
    given = request.query_params.get("key")
    if given is not None and LOCAL_KEY and secrets.compare_digest(given, LOCAL_KEY):
        response = RedirectResponse(request.url.path if request.url.path != "/" else "/app", status_code=303)
        response.set_cookie(LOCAL_COOKIE, LOCAL_KEY, httponly=True, samesite="strict", path="/")
        return response
    if not (LOCAL_KEY and secrets.compare_digest(request.cookies.get(LOCAL_COOKIE, ""), LOCAL_KEY)):
        return Response("Open Dyeroom from its icon, or type dyeroom in a terminal.", status_code=403,
                        media_type="text/plain")
    return None


def _refuse(request):
    """Why a request is turned away before its body is read, or None."""
    path, method = request.url.path, request.method
    if LOCAL:
        gate = _local_gate(request)
        if gate is not None:
            return gate
    if all(AUTH) and path not in ("/api/health", "/api/billing/webhook"):
        header = request.headers.get("authorization", "")
        ok = False
        if header.startswith("Basic "):
            try:
                user, _, password = base64.b64decode(header[6:]).decode().partition(":")
                ok = secrets.compare_digest(user, AUTH[0]) and secrets.compare_digest(password, AUTH[1])
            except ValueError:
                ok = False
        if not ok:
            return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="Dyeroom"'})
    if method in ("POST", "PUT", "PATCH", "DELETE"):
        # Every body must say its size up front: a chunked one could fill the memory before
        # anything here sees it.
        if "transfer-encoding" in request.headers and path != "/api/billing/webhook":  # that one reads with a cap
            return JSONResponse({"detail": "Send the length of the request"}, 411)
        size = int(request.headers.get("content-length") or 0)
        limit = (MAX_BYTES + 65536 if path == "/api/uploads" else PART_BYTES if PART_PATH.fullmatch(path)
                 else MAX_JSON)
        if size > limit:
            return JSONResponse({"detail": f"Larger than {MAX_BYTES // (1024 * 1024)} MB"
                                 if path == "/api/uploads" else "Request too large"}, 413)
    return None


@app.middleware("http")
async def access(request: Request, call_next):
    refused = _refuse(request)
    if LOCAL and refused is None:
        global _last_seen
        _last_seen = time.monotonic()  # stands still while the computer sleeps
    if refused is None and request.url.path == "/api/uploads" and request.method == "POST":
        refused = await _upload_checks(request, int(request.headers.get("content-length") or 0),
                                       request.headers.get("x-fingerprint", ""))  # before the file is sent
    response = refused or await call_next(request)
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    if request.url.path.startswith(NOT_FOR_SEARCH):
        response.headers.setdefault("X-Robots-Tag", "noindex")
    if _secure(request):
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    return response


async def _upload_checks(request, size, fingerprint):
    """Why a photograph of this size may not come in now, or None: room, sign-in, film, fair use."""
    if shutil.disk_usage(PHOTOS).free < 2 * size + 256 * 1024 * 1024:
        return JSONResponse({"detail": "The lab is full right now. Try again in a few minutes."}, 503,
                            headers={"Retry-After": "120"})
    user = None
    if store:
        user = await run_in_threadpool(_user, request)
        if user is None:
            return JSONResponse({"detail": "Sign in to develop your own photographs"}, 401)
        if (await run_in_threadpool(store.summary, user["id"]))["available"] <= 0:
            sha = fingerprint.lower()  # a file developed before is free
            if not (SHA256.match(sha) and await run_in_threadpool(store.is_free, user["id"], sha)):
                return JSONResponse({"detail": "Out of film"}, 402)
    who = limits.person(request, user)
    if _held_by(who) + size > limits.HELD_BYTES and not limits.unlimited(who):
        return JSONResponse({"detail": f"You have {limits.HELD_BYTES / 1024 ** 3:.0f} GB of photographs in the lab. "
                                       "More can come in as you remove finished frames."}, 429,
                            headers={"Retry-After": "60"})
    wait = limits.UPLOADS.wait(who)
    if wait:
        stats.event("limit: uploads")
        return JSONResponse({"detail": f"Many photographs added in the last hour: more in {limits.minutes(wait)}."},
                            429, headers={"Retry-After": str(math.ceil(wait))})
    return None


# --- jobs --------------------------------------------------------------------------------

def _status(job_dir):
    try:
        return json.loads((job_dir / "status.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"state": "unknown"}


def _write_status(job_dir, **status):
    tmp = job_dir / "status.json.tmp"
    tmp.write_text(json.dumps(status), encoding="utf-8")
    worker.replace(tmp, job_dir / "status.json")


def _run(job_id):
    job_dir = JOBS / job_id
    try:
        subprocess.run([sys.executable, "-m", "dyeroom.web.worker", str(job_dir)], timeout=TIMEOUT,
                       capture_output=True, env=_worker_env(), creationflags=NO_WINDOW)
    except subprocess.TimeoutExpired:
        _write_status(job_dir, state="failed", error=f"Took longer than {TIMEOUT} s and was stopped", crash=True)
    if _status(job_dir).get("state") not in ("done", "failed"):
        _write_status(job_dir, state="failed", error="The developer stopped unexpectedly (out of memory?)", crash=True)
    params = json.loads((job_dir / "params.json").read_text(encoding="utf-8"))
    if store and params.get("charged"):
        store.settle(params["upload_id"], _status(job_dir).get("state") == "done")
    _sweep_now.set()  # a photograph let go of while it was developing can go now


def _worker_env():
    """The environment for a development: everything but the secrets. A photograph's decoder
    never needs them, so a file made to attack the decoder finds none to steal."""
    hidden = ("SECRET", "PASSWORD", "TOKEN", "KEY", "AWS_", "LITESTREAM")
    return {k: v for k, v in os.environ.items() if not any(word in k.upper() for word in hidden)} | {
        "TMPDIR": str(SPILL)}


def _record(job_id, job):
    """Statistics for the owner, and an alert when developments keep failing."""
    job_dir = JOBS / job_id
    status = _status(job_dir)
    try:
        params = json.loads((job_dir / "params.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    state = status.get("state")
    ok = 1 if state == "done" else 2 if status.get("code") == "monochrome" else 0  # 2: turned away, not failed
    error = status.get("error")
    if error:  # no file names in the statistics
        for name in (params.get("source"), params.get("name"), Path(params.get("name", "")).stem):
            if name:
                error = error.replace(name, "<photo>")
        error = re.sub(r"/\S+", "<path>", error)[:300]
    info, usage = status.get("info") or {}, status.get("usage") or {}
    now = time.time()
    started, queued = job.get("started", now), job.get("queued", now)
    megapixels = info["width"] * info["height"] / 1e6 if "width" in info else None
    stats.job(params.get("film"), params.get("size"), params.get("format", "35mm"), _is_sample(Path(params["source"])),
              ok, round(started - queued, 1), round(now - started, 1), usage.get("cpu"), usage.get("peak_mb"),
              megapixels, Path(params.get("name", "")).suffix.lower(), error if ok != 1 else None)
    if ok == 0:
        if status.get("crash"):
            alerts.send("crash", f"A development was stopped: {error}", stats)
        recent = stats.failures(now - alerts.FAILURE_MINUTES * 60)
        if len(recent) >= alerts.FAILURES:
            alerts.send("failures", f"{len(recent)} photographs failed to develop in the last "
                                    f"{alerts.FAILURE_MINUTES} minutes. Latest: {error}", stats)


def _recover():
    """The queue lives in memory: jobs cut off by a restart are over, and what they cost comes back."""
    cut = 0
    for job_dir in JOBS.iterdir():
        if _status(job_dir).get("state") in ("queued", "running"):
            _write_status(job_dir, state="failed", error="The lab restarted before this photograph was finished. "
                                                         "Develop it again.")
            cut += 1
    if store:
        store.recover()
    return cut


def _expected(size):
    """Seconds a development of this size usually takes on this server."""
    when, seconds = _typical.get(size, (0.0, None))
    if time.time() - when > 300:
        seconds = stats.typical_seconds(size)
        _typical[size] = (time.time(), seconds)
    return seconds


def _order():
    """Job ids waiting, in the order the developer will take them: one from each person in turn."""
    lines = [list(q) for q in _queues.values()]
    return [line[i] for i in range(max(map(len, lines), default=0)) for line in lines if i < len(line)]


def _waiting_for(job_id):
    """(photographs ahead of this one, seconds until it is likely to start)."""
    with _lock:
        order = _order()
        ahead = order.index(job_id) if job_id in order else 0
        now = time.time()
        running = [j for j in _jobs.values() if "started" in j]
        work = sum(max(0.0, _expected(j["size"]) - (now - j["started"])) for j in running)
        work += sum(_expected(_jobs[j]["size"]) for j in order[:ahead] if j in _jobs)
        free = max(0, WORKERS - len(running))
    if free > ahead:
        return ahead, 0
    return ahead, round(work / max(1, WORKERS))


def _enqueue(job_id, who, size):
    with _lock:
        _jobs[job_id] = {"person": who, "size": size, "queued": time.time()}
        _queues.setdefault(who, collections.deque()).append(job_id)
        _lock.notify()


FULL_AT_ONCE = 1  # full-size developments at the same time: one can take most of a small server's memory


def _may_start(job_id):
    """A full-size development waits while another is running, so two never share the memory;
    drafts take any free worker. Called with _lock held."""
    if _jobs.get(job_id, {}).get("size") != "full":
        return True
    return sum(1 for j in _jobs.values() if "started" in j and j["size"] == "full") < FULL_AT_ONCE


def _dispatcher():
    while True:
        with _lock:
            # the first person in turn whose next photograph may start
            while (who := next((w for w, line in _queues.items() if _may_start(line[0])), None)) is None:
                _lock.wait()
            line = _queues.pop(who)
            job_id = line.popleft()
            if line:
                _queues[who] = line  # to the back: everyone waiting gets a turn first
            job = _jobs.setdefault(job_id, {"person": who, "size": "draft", "queued": time.time()})
            job["started"] = time.time()
        try:
            _run(job_id)
            _record(job_id, job)
        except Exception as exc:  # never let one job stop the developer
            log.error("Job %s: %s", job_id, exc)
        finally:
            with _lock:
                _jobs.pop(job_id, None)
                _lock.notify_all()  # a full-size development may have been waiting for this one


# --- photographs are not kept ----------------------------------------------------------------

def _arrive(upload_id):
    _arrived[upload_id] = _used[upload_id] = time.time()


def _use(upload_id):
    if upload_id in _arrived:
        _used[upload_id] = time.time()


def _upload_of(job_dir):
    try:
        return json.loads((job_dir / "params.json").read_text(encoding="utf-8")).get("upload_id")
    except (OSError, ValueError):
        return None


def _busy(job_dir):
    return job_dir.name in _jobs or _status(job_dir).get("state") in ("queued", "running")


def _sweep():
    """Delete every photograph the page has let go of, has not used for IDLE_SECONDS, or that
    arrived more than KEEP_SECONDS ago, with everything made from it; never one being developed."""
    now = time.time()
    jobs = {}
    for job_dir in JOBS.iterdir():
        jobs.setdefault(_upload_of(job_dir), []).append(job_dir)
    for folder in UPLOADS.iterdir():
        upload_id = folder.name
        due = (upload_id in _forgotten or now - _used.get(upload_id, 0) > IDLE_SECONDS
               or now - _arrived.get(upload_id, 0) > KEEP_SECONDS)
        if not due or any(_busy(j) for j in jobs.get(upload_id, [])):
            continue
        for job_dir in jobs.pop(upload_id, []):
            shutil.rmtree(job_dir, ignore_errors=True)
        shutil.rmtree(folder, ignore_errors=True)
        shutil.rmtree(PREVIEWS / upload_id, ignore_errors=True)
        for seen in (_arrived, _used, _held, _partial):
            seen.pop(upload_id, None)
        _forgotten.discard(upload_id)
    for folder in PREVIEWS.iterdir():  # a preview finished after its photograph went
        if not (UPLOADS / folder.name).exists() and _previews.get(folder.name) != "making":
            shutil.rmtree(folder, ignore_errors=True)
            _previews.pop(folder.name, None)
    for upload_id, orphans in jobs.items():  # results whose photograph is already gone
        if not (UPLOADS / str(upload_id)).exists():
            for job_dir in orphans:
                if not _busy(job_dir):
                    shutil.rmtree(job_dir, ignore_errors=True)
    for spilled in SPILL.iterdir():  # an upload abandoned half-way
        if now - spilled.stat().st_mtime > 3600:
            spilled.unlink(missing_ok=True)
    for roll_id, roll in list(_rolls.items()):
        if now - roll["created"] > 600:
            _rolls.pop(roll_id, None)


def _watch():
    """Once a minute: alerts for a long queue or a full lab, the daily backup, old counts."""
    now = time.time()
    with _lock:
        waiting = [j["queued"] for j in _jobs.values() if "started" not in j]
    if waiting and now - min(waiting) > alerts.QUEUE_MINUTES * 60:
        alerts.send("queue", f"{len(waiting)} photographs waiting for the developer, the oldest for "
                             f"{(now - min(waiting)) / 60:.0f} minutes. More workers or a bigger server?", stats)
    disk = shutil.disk_usage(PHOTOS)
    if disk.free < 0.1 * disk.total:
        alerts.send("space", f"The lab's photograph space is {100 * (1 - disk.free / disk.total):.0f} % full "
                             f"({disk.free / 1024 ** 3:.1f} GB free).", stats)
    if store and now - store.last_snapshot(BACKUPS) > 86400:
        try:
            store.snapshot(BACKUPS)
        except Exception as exc:  # sqlite3 errors included: an alert, never a crash
            alerts.send("backup", f"The daily copy of the accounts did not work: {exc}", stats)
    limits.prune()
    global _pruned
    if now - _pruned > 86400:
        stats.prune()
        _pruned = now


_pruned = 0.0


def _cleanup():
    while True:
        for task in (_sweep, _watch):
            try:
                task()
            except Exception as exc:  # the sweeper must keep sweeping
                log.error("%s: %s", task.__name__, exc)
        _sweep_now.wait(60)
        _sweep_now.clear()


def _in_memory(path):
    """True when the path is on a memory file system (Linux tmpfs or ramfs)."""
    try:
        mounts = [line.split()[1:3] for line in Path("/proc/mounts").read_text(encoding="utf-8").splitlines()]
    except OSError:
        return False
    target = str(path)
    owners = [m for m in mounts if target == m[0] or target.startswith(m[0].rstrip("/") + "/")]
    return bool(owners) and max(owners, key=lambda m: len(m[0]))[1] in ("tmpfs", "ramfs")


IN_MEMORY = _in_memory(PHOTOS)
if not IN_MEMORY:  # fine on a small server; the page and the privacy notice then say "only while you work"
    log.info("Photographs are held on disk at %s while they are worked on. With memory to spare, mount "
             "a tmpfs at DYEROOM_WORK and they never touch a disk.", PHOTOS)
if ACCOUNTS and not PUBLIC_URL.startswith("https://"):
    log.warning("DYEROOM_PUBLIC_URL is not an https address: sign-in cookies are marked Secure, and browsers "
                "told to keep to https, only when it is. Set it on a public server.")
if billing.PROVIDER == "paddle" and pages.missing():
    log.warning("The terms, privacy notice and refund policy still need %s: Paddle checks them before "
                "approving the site.", ", ".join(pages.missing()))


_cut = _recover()
if _cut:
    alerts.send("restart", f"The lab restarted with {_cut} photographs in the developer; their frames came back "
                           "and they can be developed again.", stats)
for _ in range(max(1, WORKERS)):
    threading.Thread(target=_dispatcher, daemon=True).start()
threading.Thread(target=_cleanup, daemon=True).start()

_last_seen = time.monotonic()


def _stop_when_unused():
    """Local mode: stop once no window has been in touch for LOCAL_STOP_SECONDS (an open page
    says it is there every minute) and nothing is waiting or developing."""
    while True:
        time.sleep(30)
        with _lock:
            busy = bool(_jobs)
        if not busy and time.monotonic() - _last_seen > LOCAL_STOP_SECONDS:
            log.info("No window for %d minutes: the lab stops", LOCAL_STOP_SECONDS // 60)
            os.kill(os.getpid(), signal.SIGTERM)
            return


if LOCAL:
    threading.Thread(target=_stop_when_unused, daemon=True).start()


# --- API ---------------------------------------------------------------------------------

@app.get("/api/health")
def health():
    with _lock:
        running = sum(1 for j in _jobs.values() if "started" in j)
        waiting = len(_jobs) - running
    return {"ok": True, "queued": waiting, "developing": running, "workers": WORKERS,
            "photos_in_memory": IN_MEMORY, "photos_held": len(_arrived), "legal_pages": not pages.missing()}


@app.get("/api/options")
def options():
    return {"views": list(VIEWINGS), "exposures": ["camera", "auto"], "filters": ["auto", *FILTERS],
            "lights": ["native", "balanced"], "sample": SAMPLE.is_file(),
            "draft_edge": DRAFT_EDGE, "full": ALLOW_FULL, "max_mb": MAX_BYTES // (1024 * 1024), "part_mb": PART_BYTES // (1024 * 1024),
            "accepted": sorted(ACCEPTED), "accounts": ACCOUNTS,
            "films": [{"id": k, "name": v, "kind": "mono" if k == "monday400" else "colour",
                       "note": "Black-and-white negative, ISO 400, printed on paper" if k == "monday400"
                       else "Colour slide film, ISO 64, seen on a light box"}
                      for k, v in pipeline.FILMS.items()],
            "formats": list(FORMATS),
            "ratings": list(mono.RATINGS), "development_minutes": mono.RATINGS,
            "colourise": colourise.available(),
            "privacy": {"in_memory": IN_MEMORY, "idle_minutes": max(1, round(IDLE_SECONDS / 60)),
                        "keep_hours": round(KEEP_SECONDS / 3600, 1)}, "grades": list(mono.GRADES), "bw_filters": list(mono.FILTERS),
            "providers": [{"id": i, "label": label} for i, label in sso.enabled()] if ACCOUNTS else [],
            "free_frames": accounts.FREE_FRAMES, "billing": billing.config() if ACCOUNTS else None,
            "contact": pages.CONTACT or None, "refund_days": pages.REFUND_DAYS, "donate": pages.DONATE or None,
            "local": LOCAL}


def _upload_name(filename):
    """The name as the page shows it and a safe one to keep it under; 415 for other formats."""
    name = Path(filename or "photo").name
    suffix = Path(name).suffix.lower()
    if suffix not in ACCEPTED:
        raise HTTPException(415, f"{suffix or 'This file'} is not a raw or image format I can develop")
    safe = re.sub(r"[^A-Za-z0-9._ -]", "_", name)[:120].lstrip("-. ") or f"photo{suffix}"
    return name, safe if safe.lower().endswith(suffix) else f"photo{suffix}"


def _arrived_whole(request, user, upload_id, size, sha):
    """A photograph is in: count it, and start the clock that deletes it."""
    if store:
        store.add_photo(upload_id, user["id"], sha)
    _held[upload_id] = (limits.person(request, user), size)
    _arrive(upload_id)
    _previews[upload_id] = "making"
    _previewer.submit(_make_preview, upload_id)
    stats.event("funnel 2: added a photograph")


def _make_preview(upload_id):
    """The preview of a photograph that has come in, in its own process (preview.py)."""
    out = PREVIEWS / upload_id
    try:
        source = next((UPLOADS / upload_id).iterdir(), None)
        if source is not None:
            subprocess.run([sys.executable, "-m", "dyeroom.web.preview", str(source), str(out)], timeout=60,
                           creationflags=NO_WINDOW,
                           capture_output=True, env=_worker_env())
    except (OSError, subprocess.SubprocessError) as exc:
        log.info("No preview for %s: %s", upload_id, exc)
    _previews[upload_id] = "made" if (out / "preview.jpg").is_file() else "none"


@app.post("/api/uploads")
async def upload(request: Request, file: UploadFile = File(...)):
    user = await run_in_threadpool(_user, request)  # checked in access() before the file arrived
    if store and user is None:
        raise HTTPException(401, "Sign in to develop your own photographs")
    name, safe = _upload_name(file.filename)
    upload_id = uuid.uuid4().hex
    folder = UPLOADS / upload_id
    folder.mkdir()
    size = 0
    digest = hashlib.sha256()  # for the keyed fingerprint that makes adding the same file again free
    with open(folder / safe, "wb") as out:
        while chunk := await file.read(1 << 20):
            size += len(chunk)
            digest.update(chunk)
            if size > MAX_BYTES:
                out.close()
                shutil.rmtree(folder, ignore_errors=True)
                raise HTTPException(413, f"Larger than {MAX_BYTES // (1024 * 1024)} MB")
            out.write(chunk)
    await run_in_threadpool(_arrived_whole, request, user, upload_id, size, digest.hexdigest())
    return {"upload_id": upload_id, "name": name, "bytes": size}


class UploadStart(BaseModel):
    name: str = Field(max_length=300)
    bytes: int = Field(gt=0)
    fingerprint: str = Field("", max_length=64)


@app.post("/api/uploads/start")
async def upload_start(request: Request, req: UploadStart):
    """A photograph to come in parts: checked now, as a whole upload is before it is sent."""
    if req.bytes > MAX_BYTES:
        raise HTTPException(413, f"Larger than {MAX_BYTES // (1024 * 1024)} MB")
    refused = await _upload_checks(request, req.bytes, req.fingerprint)
    if refused:
        return refused
    user = await run_in_threadpool(_user, request)
    name, safe = _upload_name(req.name)
    upload_id = uuid.uuid4().hex
    folder = UPLOADS / upload_id
    folder.mkdir()
    (folder / safe).touch()
    _partial[upload_id] = {"who": limits.person(request, user), "user": user, "name": name, "path": folder / safe,
                           "size": req.bytes, "got": 0, "next": 0, "digest": hashlib.sha256(),
                           "lock": asyncio.Lock()}
    _arrive(upload_id)  # an upload abandoned half-way is swept like any other left idle
    return {"upload_id": upload_id, "part_bytes": PART_BYTES}


def _append(part, data):
    with open(part["path"], "ab") as out:
        out.write(data)
    part["digest"].update(data)


@app.put("/api/uploads/{upload_id}/{index}")
async def upload_part(upload_id: str, index: int, request: Request):
    """One part, in order. A part sent again (its answer lost on the way) is not added twice."""
    part = _partial.get(upload_id)
    sender = await run_in_threadpool(_user, request) if store else None
    if part is None or part["who"] != limits.person(request, sender):
        raise HTTPException(404, GONE)
    data = await request.body()
    async with part["lock"]:
        if index < part["next"]:
            return {"received": part["got"]}
        if index > part["next"]:
            raise HTTPException(409, "A part is missing: send them in order")
        if part["got"] + len(data) > part["size"] or (len(data) < PART_BYTES and part["got"] + len(data) < part["size"]):
            raise HTTPException(400, "The parts do not add up to the photograph")
        await run_in_threadpool(_append, part, data)
        part["got"] += len(data)
        part["next"] += 1
    _use(upload_id)
    return {"received": part["got"]}


@app.post("/api/uploads/{upload_id}/finish")
async def upload_finish(upload_id: str, request: Request):
    part = _partial.get(upload_id)
    sender = await run_in_threadpool(_user, request) if store else None
    if part is None or part["who"] != limits.person(request, sender):
        raise HTTPException(404, GONE)
    if part["got"] != part["size"]:
        raise HTTPException(400, "Not all of the photograph has arrived")
    _partial.pop(upload_id, None)
    await run_in_threadpool(_arrived_whole, request, part["user"], upload_id, part["size"],
                            part["digest"].hexdigest())
    return {"upload_id": upload_id, "name": part["name"], "bytes": part["size"]}


@app.get("/api/uploads/{upload_id}/{filename}")
def upload_preview(upload_id: str, filename: str):
    """The photograph as it came in, small (preview.jpg, thumb.jpg): 202 while it is being
    made, 404 if there is none to be had or the photograph has gone."""
    if not ID.match(upload_id) or filename not in ("preview.jpg", "thumb.jpg") or upload_id not in _arrived:
        raise HTTPException(404)
    _use(upload_id)
    if _previews.get(upload_id) == "making":
        return Response(status_code=202, headers={"Retry-After": "1", "Cache-Control": "no-store"})
    path = PREVIEWS / upload_id / filename
    if not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})


@app.post("/api/sample")
def sample(request: Request):
    """A public-domain raw to try the process with, as if it had been uploaded."""
    if not SAMPLE.is_file():
        raise HTTPException(404, "No sample on this server")
    # Adding it costs nothing (a link to the file); it counts as a photograph added. Developing
    # it is what the sample allowance limits, in /api/jobs, and only when not developed before.
    wait = limits.UPLOADS.wait(limits.person(request, _user(request) if store else None))
    if wait:
        raise _too_many(wait, f"Many photographs added in the last hour: more in {limits.minutes(wait)}.")
    stats.event("funnel 1: tried the sample")
    upload_id = uuid.uuid4().hex
    folder = UPLOADS / upload_id
    folder.mkdir()
    target = folder / SAMPLE.name
    try:
        target.symlink_to(SAMPLE)
    except OSError:
        shutil.copyfile(SAMPLE, target)
    _arrive(upload_id)
    return {"upload_id": upload_id, "name": SAMPLE.name, "bytes": SAMPLE.stat().st_size}


class JobRequest(BaseModel):
    upload_id: str
    exposure: str = "camera"
    ev: float = Field(0.0, ge=-3, le=3)
    light: str = "native"
    filter: str = "auto"
    view: str = "lightbox"
    display: str = "p3"
    size: str = "draft"
    grain: bool = True
    tiff: bool = False
    film: str = "sunday64"
    rating: int = 400
    grade: int = 3
    bw_filter: str = "none"
    toning: str = "none"
    colourise: bool = False
    format: str = "35mm"
    sharpness: int = Field(0, ge=-100, le=100)
    clarity: int = Field(0, ge=-100, le=100)


def _is_sample(source):
    try:
        return source.resolve() == SAMPLE.resolve() or (
            source.name == SAMPLE.name and source.stat().st_size == SAMPLE.stat().st_size)
    except OSError:
        return False


@app.post("/api/jobs")
def create_job(req: JobRequest, request: Request):
    if not ID.match(req.upload_id) or not (UPLOADS / req.upload_id).is_dir() or req.upload_id in _forgotten:
        raise HTTPException(404, GONE)
    _use(req.upload_id)
    if req.light not in ("native", "balanced") or req.exposure not in ("camera", "auto") \
            or req.view not in VIEWINGS or req.display not in ("p3", "srgb") \
            or (req.filter != "auto" and req.filter not in FILTERS) or req.size not in ("draft", "full") \
            or req.film not in pipeline.FILMS or req.rating not in mono.RATINGS or req.grade not in mono.GRADES \
            or req.bw_filter not in mono.FILTERS or req.toning not in mono.TONING or req.format not in FORMATS:
        raise HTTPException(422, "Unknown setting")
    if req.size == "full" and not ALLOW_FULL:
        raise HTTPException(403, "Full-size developing is switched off on this server")
    req.ev = round(req.ev * 3) / 3  # thirds of a stop, as the page offers
    source = next((UPLOADS / req.upload_id).iterdir())
    sample = _is_sample(source)
    settings = json.dumps(req.model_dump(exclude={"upload_id"}), sort_keys=True)
    if sample and settings in _sample_jobs:  # free for everyone, so developed once per setting
        previous = JOBS / _sample_jobs[settings]
        if previous.is_dir() and _status(previous).get("state") in ("queued", "running", "done"):
            return {"job_id": previous.name}
    user = _user(request) if store else None
    if store and not sample and user is None:
        raise HTTPException(401, "Sign in to develop your own photographs")
    who = limits.person(request, user)
    with _lock:
        waiting = len(_queues.get(who, ()))
        everyone = sum(len(q) for q in _queues.values())
    if waiting >= limits.WAITING and not limits.unlimited(who):
        raise _too_many(30, f"You have {waiting} photographs waiting for the developer. More go in as these come out.")
    if everyone >= limits.QUEUE_MAX:
        stats.event("limit: lab full")
        raise _too_many(60, "The lab is very busy. Your photographs go in as soon as there is room.")
    wait = (limits.SAMPLES.wait(f"sample:{limits.address(request)}") if sample else
            limits.DEVELOPS.wait(who, weight=limits.FULL_WEIGHT if req.size == "full" else 1))
    if wait:
        stats.event("limit: samples" if sample else "limit: developments")
        raise _too_many(wait, f"The sample has been developed many times from here: again in {limits.minutes(wait)}, "
                              "or develop your own photographs." if sample else
                              f"Many developments in the last hour: more in {limits.minutes(wait)}.")
    charged = False
    if store and not sample:
        try:
            store.charge(req.upload_id, user["id"])
        except LookupError:
            raise HTTPException(404, GONE)
        except accounts.NoFilm:
            raise HTTPException(402, "Out of film: buy a roll or start a plan to develop this photograph")
        charged = True
    job_id = uuid.uuid4().hex
    job_dir = JOBS / job_id
    job_dir.mkdir()
    params = req.model_dump() | {"source": str(source), "name": source.name, "charged": charged,
                                 "long_edge": None if req.size == "full" else DRAFT_EDGE}
    (job_dir / "params.json").write_text(json.dumps(params), encoding="utf-8")
    _write_status(job_dir, state="queued")
    if sample:
        _sample_jobs[settings] = job_id
    _enqueue(job_id, who, req.size)
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    if not ID.match(job_id) or not (JOBS / job_id).is_dir():
        raise HTTPException(404, "Job not found")
    status = _status(JOBS / job_id)
    _use(_upload_of(JOBS / job_id))
    if status.get("state") == "queued":
        status["ahead"], status["wait"] = _waiting_for(job_id)
    status.pop("usage", None)
    status.pop("crash", None)
    return JSONResponse(status, headers={"Cache-Control": "no-store"})


@app.get("/api/jobs/{job_id}/{filename}")
def job_file(job_id: str, filename: str, download: bool = False):
    if not ID.match(job_id) or filename not in FILES:
        raise HTTPException(404)
    path = JOBS / job_id / filename
    if not path.is_file():
        raise HTTPException(404)
    params = json.loads((JOBS / job_id / "params.json").read_text(encoding="utf-8"))
    _use(params.get("upload_id"))
    nice = f"{Path(params['name']).stem}_{params.get('film', 'sunday64')}{path.suffix}"
    return FileResponse(path, media_type=FILES[filename], filename=nice if download else None,
                        headers={"Cache-Control": "private, max-age=86400"})


def _exported(job_id, fmt, adjustments, geometry=None):
    """(file bytes, file name) of a finished slide at full resolution with the page's
    adjustments and framing, carrying the original's metadata. HTTPException if the frame is gone."""
    job_dir = JOBS / job_id
    if not ID.match(job_id) or not (job_dir / "slide16.npy").is_file():
        raise HTTPException(404, GONE)
    params = json.loads((job_dir / "params.json").read_text(encoding="utf-8"))
    _use(params.get("upload_id"))
    name = f"{Path(params['source']).stem}_{params.get('film', 'sunday64')}.{fmt}"
    if fmt == "jpg" and adjust.is_identity(adjustments) and adjust.geometry_is_identity(geometry) \
            and (job_dir / "slide.jpg").is_file():
        return (job_dir / "slide.jpg").read_bytes(), name  # as developed, metadata already in
    display = params["display"]
    space = spectra.P3 if display == "p3" else spectra.SRGB
    with _exporting:
        source = np.load(job_dir / "slide16.npy", mmap_mode="r")
        if not adjust.geometry_is_identity(geometry):
            source = adjust.frame(np.asarray(source), geometry)
        result = np.empty(source.shape, np.uint16)
        for top in range(0, source.shape[0], 256):  # in bands of rows: bounded memory at full size
            block = np.asarray(source[top:top + 256], np.float32) / 65535.0
            result[top:top + 256] = np.round(adjust.apply(block, adjustments, space) * 65535.0)
        data = output.jpeg_bytes(result, display) if fmt == "jpg" else output.tiff_bytes(result, display)
        del result
    if metadata.available():  # the original's metadata, unchanged
        scratch = job_dir / f"export-{uuid.uuid4().hex}.{fmt}"
        try:
            scratch.write_bytes(data)
            ai = "colours" in (_status(job_dir).get("info") or {})
            if metadata.carry_over(params["source"], scratch, ai_colours=ai):
                data = scratch.read_bytes()
        finally:
            scratch.unlink(missing_ok=True)
    return data, name


class ExportRequest(BaseModel):
    format: str = "jpg"
    adjust: dict = Field(default_factory=dict)
    geometry: dict = Field(default_factory=dict)


@app.post("/api/jobs/{job_id}/export")
def export(job_id: str, req: ExportRequest, request: Request):
    """The finished slide at full resolution with the page's adjustments applied."""
    if req.format not in ("jpg", "tif"):
        raise HTTPException(422, "Unknown format")
    wait = limits.EXPORTS.wait(limits.person(request, _user(request)))
    if wait:
        raise _too_many(wait, f"Many exports in the last hour: more in {limits.minutes(wait)}.")
    began = time.time()
    data, name = _exported(job_id, req.format, req.adjust, req.geometry)
    stats.export(req.format, 1, round(time.time() - began, 1), len(data))
    return Response(data, media_type="image/jpeg" if req.format == "jpg" else "image/tiff",
                    headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"})


# --- the whole roll as one ZIP ------------------------------------------------------------------
# The page sends which frames and their adjustments, then downloads the ZIP by a plain link,
# so the browser writes it straight to disk while the server makes it frame by frame.

class RollFrame(BaseModel):
    job_id: str
    adjust: dict = Field(default_factory=dict)
    geometry: dict = Field(default_factory=dict)


class RollRequest(BaseModel):
    format: str = "jpg"
    frames: list[RollFrame] = Field(min_length=1, max_length=500)


@app.post("/api/rolls")
def new_roll(req: RollRequest, request: Request):
    if req.format not in ("jpg", "tif"):
        raise HTTPException(422, "Unknown format")
    frames = [f for f in req.frames if ID.match(f.job_id) and (JOBS / f.job_id / "slide16.npy").is_file()]
    if not frames:
        raise HTTPException(404, GONE)
    who = limits.person(request, _user(request))
    for _ in frames:
        wait = limits.EXPORTS.wait(who)
        if wait:
            raise _too_many(wait, f"Many exports in the last hour: more in {limits.minutes(wait)}.")
    roll_id = uuid.uuid4().hex
    _rolls[roll_id] = {"format": req.format, "frames": [(f.job_id, f.adjust, f.geometry) for f in frames],
                       "created": time.time()}
    return {"roll_id": roll_id, "frames": len(frames)}


class _Pipe:
    """A write-only file for zipfile that hands on what was written."""

    def __init__(self):
        self.parts = []

    def write(self, data):
        self.parts.append(bytes(data))
        return len(data)

    def flush(self):
        pass

    def take(self):
        out = b"".join(self.parts)
        self.parts.clear()
        return out


def _zip(roll):
    pipe, names, missing, total, began = _Pipe(), set(), [], 0, time.time()
    with zipfile.ZipFile(pipe, "w", zipfile.ZIP_STORED, allowZip64=True) as archive:
        for job_id, adjustments, geometry in roll["frames"]:
            try:
                data, name = _exported(job_id, roll["format"], adjustments, geometry)
            except (HTTPException, OSError, ValueError):
                missing.append(job_id)
                continue
            stem, ext = name.rsplit(".", 1)
            n = 1
            while name.lower() in names:
                n += 1
                name = f"{stem} ({n}).{ext}"
            names.add(name.lower())
            entry = zipfile.ZipInfo(name, time.localtime()[:6])
            entry.compress_type = zipfile.ZIP_STORED
            with archive.open(entry, "w", force_zip64=len(data) > 0x7FFFFFFF) as out:
                for at in range(0, len(data), 1 << 20):
                    out.write(data[at:at + (1 << 20)])
                    yield pipe.take()
            total += len(data)
            del data
        if missing:
            archive.writestr("Not exported.txt", f"{len(missing)} frames had already left the lab and could not be "
                                                 "exported. Add them again to develop them.\n")
    yield pipe.take()
    stats.export(roll["format"], len(roll["frames"]) - len(missing), round(time.time() - began, 1), total)


@app.get("/api/rolls/{roll_id}.zip")
def roll_zip(roll_id: str):
    roll = _rolls.get(roll_id) if ID.match(roll_id) else None
    if roll is None:
        raise HTTPException(404, "This download has expired. Export the roll again.")
    name = f"Dyeroom {time.strftime('%Y-%m-%d')} {'JPEG' if roll['format'] == 'jpg' else 'TIFF'}.zip"
    return StreamingResponse(_zip(roll), media_type="application/zip",
                             headers={"Content-Disposition": f'attachment; filename="{name}"',
                                      "Cache-Control": "no-store"})


# --- accounts ------------------------------------------------------------------------------

def _accounts_on():
    if not store:
        raise HTTPException(404)


def _signed_in(request, user_id):
    response = RedirectResponse("/app", 303)
    response.set_cookie(SESSION_COOKIE, store.new_session(user_id), max_age=accounts.SESSION_SECONDS,
                        httponly=True, secure=_secure(request), samesite="lax")
    response.delete_cookie(LOGIN_COOKIE, path="/auth")
    return response


@app.get("/auth/{provider}")
def sign_in(provider: str, request: Request):
    _accounts_on()
    if provider not in dict(sso.enabled()):
        raise HTTPException(404)
    if limits.SIGN_INS.wait(limits.address(request)):
        return RedirectResponse("/app?signin=later", 303)
    if provider == "dev":
        return _signed_in(request, store.sign_in("dev", "test-user", "test@localhost", "Test user"))
    state, nonce = store.begin_login(provider)
    response = RedirectResponse(sso.authorize_url(provider, f"{_base(request)}/auth/{provider}/callback",
                                                  state, nonce), 303)
    secure = _secure(request)  # Apple comes back with a cross-site POST: the cookie must allow it
    response.set_cookie(LOGIN_COOKIE, state, max_age=accounts.LOGIN_SECONDS, path="/auth", httponly=True,
                        secure=secure, samesite="none" if secure else "lax")
    return response


@app.api_route("/auth/{provider}/callback", methods=["GET", "POST"])
async def sign_in_return(provider: str, request: Request):
    _accounts_on()
    params = dict(request.query_params)
    if request.method == "POST":
        params.update({k: v for k, v in (await request.form()).items() if isinstance(v, str)})
    state, cookie = params.get("state", ""), request.cookies.get(LOGIN_COOKIE, "")
    login = await run_in_threadpool(store.finish_login, state) if state else None
    if "error" in params:  # cancelled at the provider
        return RedirectResponse("/app", 303)
    if login is None or login[0] != provider or not secrets.compare_digest(state, cookie) or "code" not in params:
        return RedirectResponse("/app?signin=failed", 303)
    try:
        who = await run_in_threadpool(sso.identity, provider, params["code"],
                                      f"{_base(request)}/auth/{provider}/callback", login[1], params.get("user"))
    except sso.SignInError as exc:
        log.warning("Sign-in failed: %s", exc)
        return RedirectResponse("/app?signin=failed", 303)
    welcome = True
    if not await run_in_threadpool(store.known, provider, who["subject"]):
        # Free frames for at most a few new accounts a day from one address: making account
        # after account is not a way to develop for nothing.
        welcome = not limits.NEW_ACCOUNTS.wait(limits.address(request))
        stats.event("new account" if welcome else "new account without free frames")
    user_id = await run_in_threadpool(store.sign_in, provider, who["subject"], who["email"], who["name"], welcome)
    return await run_in_threadpool(_signed_in, request, user_id)


@app.post("/auth/logout")
def sign_out(request: Request):
    _accounts_on()
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        store.end_session(token)
    response = JSONResponse({"ok": True})
    response.delete_cookie(SESSION_COOKIE)
    return response


class Photographs(BaseModel):
    uploads: list[str] = Field(default_factory=list, max_length=1000)


@app.post("/api/keep")
def keep(req: Photographs):
    """The page is still working on these photographs."""
    for upload_id in req.uploads:
        _use(upload_id)
    return {"ok": True}


@app.post("/api/forget")
def forget(req: Photographs, request: Request):
    """Delete these photographs and everything made from them now (as soon as none is in the
    developer). Sent by the page when it closes, and by its Clear button."""
    user = _user(request)
    for upload_id in req.uploads:
        if not ID.match(upload_id) or upload_id not in _arrived:
            continue
        photo = store.photo(upload_id) if store else None
        if photo is not None and (user is None or photo["user_id"] != user["id"]):
            continue  # someone else's
        _forgotten.add(upload_id)
    _sweep_now.set()
    return {"ok": True}


class Fingerprints(BaseModel):
    fingerprints: list[str] = Field(default_factory=list, max_length=500)


@app.post("/api/free")
def free(req: Fingerprints, request: Request):
    """Which of these files (by SHA-256) this user has developed before: adding them again is free."""
    _accounts_on()
    user = _user(request)
    if user is None:
        raise HTTPException(401, "Not signed in")
    wait = limits.CHECKS.wait(f"u:{user['id']}")
    if wait:
        raise _too_many(wait, f"Too many checks: again in {limits.minutes(wait)}.")
    return {"free": [bool(SHA256.match(f.lower())) and store.is_free(user["id"], f.lower())
                     for f in req.fingerprints]}


# --- presets --------------------------------------------------------------------------------

PRESET_CHECKS = {
    "film": lambda v: v in pipeline.FILMS, "exposure": lambda v: v in ("camera", "auto"),
    "ev": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and -3 <= v <= 3,
    "light": lambda v: v in ("native", "balanced"), "filter": lambda v: v == "auto" or v in FILTERS,
    "view": lambda v: v in VIEWINGS, "grain": lambda v: isinstance(v, bool),
    "rating": lambda v: v in mono.RATINGS, "grade": lambda v: v in mono.GRADES,
    "bw_filter": lambda v: v in mono.FILTERS, "toning": lambda v: v in mono.TONING,
    "sharpness": lambda v: isinstance(v, int) and not isinstance(v, bool) and -100 <= v <= 100,
    "clarity": lambda v: isinstance(v, int) and not isinstance(v, bool) and -100 <= v <= 100,
}


def _clean_preset(raw):
    """Only known development settings with valid values, and cleaned adjustments."""
    raw = raw if isinstance(raw, dict) else {}
    out = {}
    for key, ok in PRESET_CHECKS.items():
        try:
            if key in raw and ok(raw[key]):
                out[key] = raw[key]
        except TypeError:  # an unhashable value
            pass
    out["adjust"] = adjust.clean(raw.get("adjust"))
    return out


class PresetIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    settings: dict


def _member(request):
    _accounts_on()
    user = _user(request)
    if user is None:
        raise HTTPException(401, "Sign in to keep presets")
    return user


@app.get("/api/presets")
def list_presets(request: Request):
    return JSONResponse(store.presets(_member(request)["id"]), headers={"Cache-Control": "no-store"})


@app.post("/api/presets")
def save_preset(req: PresetIn, request: Request):
    """Save development settings and finishing adjustments under a name (replacing that name)."""
    user = _member(request)
    wait = limits.CHECKS.wait(f"u:{user['id']}")
    if wait:
        raise _too_many(wait, f"Too many changes to presets: again in {limits.minutes(wait)}.")
    name = " ".join(req.name.split())
    if not name:
        raise HTTPException(422, "A preset needs a name")
    settings = _clean_preset(req.settings)
    preset_id = store.save_preset(user["id"], name, settings)
    if preset_id is None:
        raise HTTPException(409, f"You have {accounts.MAX_PRESETS} presets already: delete one first")
    return {"id": preset_id, "name": name, "settings": settings}


@app.delete("/api/presets/{preset_id}")
def delete_preset(preset_id: str, request: Request):
    store.delete_preset(_member(request)["id"], preset_id)
    return {"ok": True}


@app.get("/api/me")
def me(request: Request):
    """Who is signed in, and how much film they have."""
    user = _user(request)
    body = {"accounts": ACCOUNTS, "signed_in": user is not None}
    if user:
        body |= store.summary(user["id"])
    return JSONResponse(body, headers={"Cache-Control": "no-store"})


@app.delete("/api/me")
def delete_me(request: Request):
    _accounts_on()
    user = _user(request)
    if user is None:
        raise HTTPException(401, "Not signed in")
    store.delete_user(user["id"])
    response = JSONResponse({"ok": True})
    response.delete_cookie(SESSION_COOKIE)
    return response


# --- billing -------------------------------------------------------------------------------

@app.post("/api/billing/webhook")
async def billing_webhook(request: Request):
    _accounts_on()
    raw = b""
    async for chunk in request.stream():  # read with a cap: the length may not be given
        raw += chunk
        if len(raw) > MAX_JSON:
            raise HTTPException(413, "Request too large")
    if not billing.verify_signature(raw, request.headers.get("paddle-signature", ""), billing.WEBHOOK_SECRET):
        alerts.send("webhook", "A payment notification arrived with a signature that is not valid. If purchases "
                               "stop arriving, check DYEROOM_PADDLE_WEBHOOK_SECRET.", stats)
        raise HTTPException(401, "Signature not valid")
    try:
        event = json.loads(raw)
    except ValueError:
        raise HTTPException(400, "Not JSON")
    result = await run_in_threadpool(billing.handle, event, store, stats)
    return {"ok": True, "result": result}


@app.post("/api/billing/portal")
def billing_portal(request: Request):
    """Where to manage a plan, payment method and receipts."""
    _accounts_on()
    user = _user(request)
    if user is None:
        raise HTTPException(401, "Not signed in")
    if billing.PROVIDER == "test":
        billing.test_end(store, user["id"])
        return {"url": None, "note": "Test plan ended"}
    if not user["customer_id"]:
        raise HTTPException(404, "Nothing bought yet")
    try:
        return {"url": billing.portal_url(user["customer_id"], store.subscription_ids(user["id"]))}
    except (OSError, KeyError, ValueError) as exc:
        log.error("Customer portal: %s", exc)
        raise HTTPException(502, "The payment provider did not answer; try again in a minute")


@app.post("/api/billing/opened")
def billing_opened(request: Request):
    """The page opened the checkout: a step counted for /admin, with nothing about who."""
    _accounts_on()
    if not limits.CHECKS.wait(limits.person(request, _user(request))):
        stats.event("funnel 3: opened the checkout")
    return {"ok": True}


class TestPurchase(BaseModel):
    plan: str


@app.post("/api/billing/test-buy")
def billing_test_buy(req: TestPurchase, request: Request):
    _accounts_on()
    user = _user(request)
    if billing.PROVIDER != "test":
        raise HTTPException(404)
    if user is None:
        raise HTTPException(401, "Not signed in")
    try:
        billing.test_buy(store, user["id"], req.plan)
    except KeyError:
        raise HTTPException(422, "Unknown plan")
    stats.event("funnel 4: bought a roll" if req.plan == "roll" else "funnel 4: started a plan")
    return store.summary(user["id"])


# --- for the owner, and the legal pages --------------------------------------------------------

def _replicated():
    """When Litestream last copied the accounts off the server, or None if it is not running."""
    try:
        folder = DATA / ".accounts.db-litestream"
        return max((p.stat().st_mtime for p in folder.rglob("*") if p.is_file()), default=None)
    except OSError:
        return None


@app.get("/admin")
def admin(request: Request):
    """The lab at a glance: queue, developments, failures, sales, backups. For DYEROOM_ADMIN_EMAILS,
    or with DYEROOM_ADMIN_PASSWORD."""
    user = _user(request)
    if not (user and user["email"] and user["email"].lower() in ADMINS) and not _admin_password(request):
        if ADMIN_PASSWORD:  # ask for it, as browsers do
            return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="Dyeroom admin"'})
        raise HTTPException(404)
    with _lock:
        running = sum(1 for j in _jobs.values() if "started" in j)
        waiting = [time.time() - j["queued"] for j in _jobs.values() if "started" not in j]
    disk = shutil.disk_usage(PHOTOS)
    now = {"waiting": len(waiting), "oldest_wait": max(waiting, default=0), "developing": running,
           "workers": WORKERS, "photos_held": len(_arrived), "held_gb": sum(b for _, b in _held.values()) / 1024 ** 3,
           "space_free_gb": disk.free / 1024 ** 3, "space_gb": disk.total / 1024 ** 3, "in_memory": IN_MEMORY,
           "cores": os.cpu_count() or 1, "last_backup": store.last_snapshot(BACKUPS) if store else None,
           "replicated": _replicated() if store else None,
           "alerts_to": bool(alerts.URL), "legal_missing": pages.missing()}
    sales = [(title, store.report(time.time() - span)) for title, span in
             (("Last 24 hours", 86400), ("Last 7 days", 7 * 86400), ("Last 30 days", 30 * 86400))] if store else []
    html = pages.admin(now, stats.summary(), sales, stats.failures(time.time() - 7 * 86400)[:25],
                       stats.recent_alerts())
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


def _legal(name):
    facts = {"in_memory": IN_MEMORY, "idle_minutes": max(1, round(IDLE_SECONDS / 60)),
             "keep_hours": round(KEEP_SECONDS / 3600, 1), "accounts": ACCOUNTS}
    return HTMLResponse(pages.legal(name, facts), headers={"Cache-Control": "no-cache"})


@app.api_route("/terms", methods=["GET", "HEAD"])  # HEAD too: link checkers use it
def terms():
    return _legal("terms")


@app.api_route("/privacy", methods=["GET", "HEAD"])
def privacy():
    return _legal("privacy")


@app.api_route("/refunds", methods=["GET", "HEAD"])
def refunds():
    if not ACCOUNTS:  # free: nothing is sold
        raise HTTPException(404)
    return _legal("refunds")


STATIC = Path(__file__).parent / "static"


class Static(StaticFiles):
    """The page's files, with cache headers so Cloudflare and browsers keep them: those linked
    with a ?v= stamp (code and styles; a new version gets a new address) for a year, the rest
    (images, icons) for a day."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            stamped = b"v=" in scope.get("query_string", b"")
            response.headers["Cache-Control"] = ("public, max-age=31536000, immutable" if stamped
                                                 else "public, max-age=86400")
        return response


app.mount("/static", Static(directory=STATIC), name="static")


@app.get("/licences")
def licences():
    """Licences of the data and models Dyeroom is built on."""
    data = Path(__file__).resolve().parents[1] / "data"
    parts = [f"{'=' * 78}\n{path.name}\n{'=' * 78}\n\n{path.read_text(encoding="utf-8")}" for path in sorted(data.glob("LICENSE-*.txt"))]
    return Response("\n\n".join(parts), media_type="text/plain; charset=utf-8")


@app.get("/install.sh")
@app.get("/install.ps1")
def install_script(request: Request):
    """The installers. macOS and Linux:  curl -LsSf https://dyeroom.app/install.sh | sh
    Windows:  powershell -ExecutionPolicy ByPass -c "irm https://dyeroom.app/install.ps1 | iex" """
    script = (Path(__file__).parent / request.url.path.lstrip("/")).read_text(encoding="utf-8")
    return Response(script, media_type="text/plain; charset=utf-8", headers={"Cache-Control": "public, max-age=300"})


@app.get("/api/here")
def here():
    """An open page saying it is there: local mode keeps the lab running while one is."""
    return {"ok": True}


@app.api_route("/", methods=["GET", "HEAD"])
def home(request: Request):
    """What Dyeroom is, for people and search engines; the app is at /app."""
    if LOCAL:
        return RedirectResponse("/app", status_code=303)
    facts = {"in_memory": IN_MEMORY, "idle_minutes": max(1, round(IDLE_SECONDS / 60)),
             "keep_hours": round(KEEP_SECONDS / 3600, 1)}
    return HTMLResponse(site.home(_base(request), ACCOUNTS, pages.DONATE, facts, MAX_BYTES // (1024 * 1024)),
                        headers={"Cache-Control": "public, max-age=300"})


CONTENT = content.load()  # the film pages and guides, in content/
_rendered = {}             # (path, base) -> page: they change only with a new release


def _cached(request, path, render):
    key = (path, _base(request))
    if key not in _rendered:
        _rendered[key] = render(_base(request))
    return HTMLResponse(_rendered[key], headers={"Cache-Control": "public, max-age=300"})


def _content(request, path):
    item = CONTENT.get(path)
    if not item:
        raise StarletteHTTPException(404)
    return _cached(request, path, lambda base: site.page(base, ACCOUNTS, pages.DONATE, item, CONTENT))


@app.api_route("/films/{name}", methods=["GET", "HEAD"])
def film_page(request: Request, name: str):
    return _content(request, f"/films/{name}")


@app.api_route("/guides/{name}", methods=["GET", "HEAD"])
def guide_page(request: Request, name: str):
    return _content(request, f"/guides/{name}")


@app.api_route("/how-it-works", methods=["GET", "HEAD"])
def how_it_works(request: Request):
    return _content(request, "/how-it-works")


@app.api_route("/about", methods=["GET", "HEAD"])
def about(request: Request):
    return _content(request, "/about")


@app.api_route("/films", methods=["GET", "HEAD"])
def films(request: Request):
    return _cached(request, "/films", lambda base: site.listing(base, ACCOUNTS, pages.DONATE, "Films", CONTENT))


@app.api_route("/guides", methods=["GET", "HEAD"])
def guides(request: Request):
    return _cached(request, "/guides", lambda base: site.listing(base, ACCOUNTS, pages.DONATE, "Guides", CONTENT))


@app.exception_handler(StarletteHTTPException)
async def not_found(request: Request, exc):
    """A page, not JSON, for an address a person might type or follow; the API keeps JSON."""
    if exc.status_code == 404 and request.method in ("GET", "HEAD") \
            and not request.url.path.startswith(("/api/", "/static/", "/auth/")):
        return HTMLResponse(pages.not_found(), status_code=404)
    return await http_exception_handler(request, exc)


@app.api_route("/favicon.ico", methods=["GET", "HEAD"])
def favicon():
    return FileResponse(STATIC / "favicon.ico", headers={"Cache-Control": "public, max-age=86400"})


AI_TRAINING_BOTS = ("GPTBot", "ClaudeBot", "CCBot", "Google-Extended", "Applebot-Extended", "Meta-ExternalAgent",
                    "Bytespider", "cohere-training-data-crawler")


@app.api_route("/robots.txt", methods=["GET", "HEAD"])
def robots():
    """Everything may be read but the API, sign-in and the owner's page. /app is not blocked:
    search engines must be able to read its noindex. Crawlers that only gather text to train AI
    models are asked to stay away; search engines and AI search and assistants are welcome."""
    lines = ["# Crawlers that gather pages to train AI models: not here.",
             *[f"User-agent: {bot}" for bot in AI_TRAINING_BOTS], "Disallow: /", "",
             "# Search engines, and AI search and assistants: welcome.",
             "User-agent: *", "Disallow: /api/", "Disallow: /auth/", "Disallow: /admin", "Allow: /"]
    if PUBLIC_URL:
        lines += ["", f"Sitemap: {PUBLIC_URL}/sitemap.xml"]
    return Response("\n".join(lines) + "\n", media_type="text/plain",
                    headers={"Cache-Control": "public, max-age=3600"})


@app.api_route("/sitemap.xml", methods=["GET", "HEAD"])
def sitemap(request: Request):
    """The pages worth finding: the home page, the films and guides, and the legal pages once
    they are complete. The films and guides say when they were last changed."""
    paths = ["/", "/films", "/guides"] + ([] if pages.missing() else ["/terms", "/privacy"] + (["/refunds"] if ACCOUNTS else []))
    base = _base(request)
    rows = "".join(f"<url><loc>{base}{path}</loc></url>" for path in paths)
    rows += "".join(f"<url><loc>{base}{item.slug}</loc><lastmod>{item.updated.isoformat()}</lastmod></url>"
                    for item in sorted(CONTENT.values(), key=lambda item: item.slug))
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{rows}</urlset>\n')
    return Response(xml, media_type="application/xml", headers={"Cache-Control": "public, max-age=3600"})


@app.api_route("/app", methods=["GET", "HEAD"])
def index():
    """The app, with asset links stamped by file time so browsers never run stale code."""
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    for asset in ("style.css", "grade.js", "lab.js", "app.js"):
        stamp = int((STATIC / asset).stat().st_mtime)
        html = html.replace(f"/static/{asset}", f"/static/{asset}?v={stamp}")
    return Response(html, media_type="text/html", headers={"Cache-Control": "no-cache"})


def main():
    import uvicorn
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    uvicorn.run("dyeroom.web.app:app", host=os.environ.get("HOST", "127.0.0.1"),  # 0.0.0.0 to serve others (Docker)
                port=int(os.environ.get("PORT", "8000")), workers=1,
                proxy_headers=True, forwarded_allow_ips=os.environ.get("DYEROOM_TRUSTED_PROXIES", "127.0.0.1"),
                access_log=os.environ.get("DYEROOM_ACCESS_LOG", "0") in ("1", "true", "yes"),
                limit_concurrency=int(os.environ.get("DYEROOM_MAX_CONNECTIONS", "500")))
