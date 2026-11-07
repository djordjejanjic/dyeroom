"""The lab on your own computer:  dyeroom   (the same as  dyeroom open)

Starts the web app on this computer only, at a free port and with a key made at each start,
and opens it in an app window: Chrome, Edge, Chromium or Brave if there is one (Edge is on every
Windows), otherwise the default browser. Typing dyeroom again while it runs opens another window on the same lab. It
stops by itself some minutes after the last window closes, or with  dyeroom stop.

Photographs stay on this computer. The lab works on copies in its cache folder while you
work and deletes them when it next starts; nothing is sent anywhere.

  dyeroom open [--no-window] [--foreground]   start the lab (or find it running) and open it
  dyeroom stop                                stop it now
  dyeroom shortcut                            an icon in Applications (macOS), the app list (Linux)
                                              or the Start menu (Windows)
  dyeroom colourise-model                     fetch the colourising model, 270 MB, once
  dyeroom PHOTO ...                           develop from the command line instead (dyeroom --help)
"""
import hashlib
import json
import os
import plistlib
import re
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import webbrowser
from importlib import metadata as package_metadata
from pathlib import Path

COMMANDS = ("open", "stop", "shortcut", "colourise-model", "serve")
DONATE = "https://buymeacoffee.com/geoyanj"
ICON = Path(__file__).parent / "web" / "static" / "icon-512.png"
MODEL_NAME = "ddcolor_paper_tiny.onnx"
MODEL_URL = "https://github.com/djordjejanjic/dyeroom/releases/download/colourise-model-1/" + MODEL_NAME
MODEL_SHA256 = "75c9d2bc330d4cf8b880cafdbfb2590bb7434e9fd8da7ba5e256e2db947fd8d2"
MAC_BROWSERS = ("Google Chrome", "Microsoft Edge", "Chromium", "Brave Browser")
LINUX_BROWSERS = ("google-chrome", "google-chrome-stable", "microsoft-edge", "chromium", "chromium-browser",
                  "brave-browser")
WINDOWS_BROWSERS = (r"Google\Chrome\Application\chrome.exe", r"Microsoft\Edge\Application\msedge.exe",
                    r"BraveSoftware\Brave-Browser\Application\brave.exe")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # Windows: no console flashing up


def folders():
    """Where the lab keeps its own files and its working copies, as each system expects."""
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "Dyeroom", home / "Library" / "Caches" / "Dyeroom"
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local")) / "Dyeroom"
        return base, base / "Cache"
    return (Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share")) / "dyeroom",
            Path(os.environ.get("XDG_CACHE_HOME", home / ".cache")) / "dyeroom")


def memory_gb():
    """This computer's memory in GB, or None if it cannot be read."""
    if sys.platform == "win32":
        return _windows_memory_gb()
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024 ** 3
    except (AttributeError, ValueError, OSError):
        return None


def _windows_memory_gb():
    import ctypes

    class Status(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong) for name in ("ullTotalPhys", "ullAvailPhys", "ullTotalPageFile",
                                                    "ullAvailPageFile", "ullTotalVirtual", "ullAvailVirtual",
                                                    "ullAvailExtendedVirtual")]
    status = Status()
    status.dwLength = ctypes.sizeof(status)
    try:
        found = ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
    except (AttributeError, OSError):
        return None
    return status.ullTotalPhys / 1024 ** 3 if found else None


def workers():
    """Drafts developed at once: each takes about 3 GB and a few cores; full size goes one at a time."""
    return max(1, min(4, (os.cpu_count() or 2) // 4, int((memory_gb() or 8) // 8)))


def settings(port, key):
    """The web app's settings for a lab on this computer."""
    data, cache = folders()
    out = {"DYEROOM_LOCAL": "1", "DYEROOM_LOCAL_KEY": key, "HOST": "127.0.0.1", "PORT": str(port),
           "DYEROOM_DATA": str(data), "DYEROOM_WORK": str(cache / "work"), "DYEROOM_WORKERS": str(workers()),
           "DYEROOM_KEEP_HOURS": "24", "DYEROOM_IDLE_MINUTES": "240", "DYEROOM_UNLIMITED": "127.0.0.1,::1",
           "DYEROOM_ACCOUNTS": "0", "DYEROOM_DONATE_URL": DONATE}
    # The colourising model lives in the app-data folder, fetched there when asked for (the
    # command or the page); a copy beside the package (working from source) is used if there is one.
    if (data / MODEL_NAME).is_file() or not (Path(__file__).parent / "data" / "cache" / MODEL_NAME).is_file():
        out["DYEROOM_COLOURISE_MODEL"] = str(data / MODEL_NAME)
    return out


def _instance_file():
    return folders()[0] / "lab.json"


def _running():
    """The lab already running on this computer ({port, key, pid}), or None."""
    try:
        info = json.loads(_instance_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return info if _answers(info) else None


def _answers(info):
    request = urllib.request.Request(f"http://127.0.0.1:{info['port']}/api/health",
                                     headers={"Cookie": f"dyeroom_key={info['key']}"})
    try:
        with urllib.request.urlopen(request, timeout=2) as reply:
            return reply.status == 200 and json.loads(reply.read()).get("ok")
    except (OSError, ValueError):
        return False


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start(info):
    """Start the lab ({port, key}) in the background and wait until it answers."""
    data, cache = folders()
    data.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    with open(cache / "lab.log", "ab") as log:
        # -I and its own folder: the installed Dyeroom, never a dyeroom folder where the command was typed.
        # Detached, so it goes on running when the terminal that started it closes.
        detached = ({"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
                    if sys.platform == "win32" else {"start_new_session": True})
        lab = subprocess.Popen([sys.executable, "-I", "-m", "dyeroom.local", "serve"], cwd=cache,
                               env={**os.environ, **settings(info["port"], info["key"])},
                               stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, **detached)
    info["pid"] = lab.pid
    deadline = time.monotonic() + 120
    while not _answers(info):
        if lab.poll() is not None or time.monotonic() > deadline:
            raise SystemExit(f"Dyeroom could not start. What it said is in {cache / 'lab.log'}")
        time.sleep(0.3)
    _instance_file().write_text(json.dumps(info), encoding="utf-8")
    return info


def _app_browser():
    """How to open an app window (no tabs or address bar) in a Chromium browser: a function of the
    address, or None when there is none (Chrome, Edge, Chromium or Brave)."""
    if sys.platform == "darwin":
        for name in MAC_BROWSERS:
            if any(Path(base, f"{name}.app").exists() for base in ("/Applications", Path.home() / "Applications")):
                # not waited on: opened from the app's own icon, `open` may not come back at once
                return lambda url: subprocess.Popen(["open", "-na", name, "--args", f"--app={url}"],
                                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif sys.platform == "win32":
        roots = [os.environ.get(k) for k in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
        for exe in (Path(root, name) for name in WINDOWS_BROWSERS for root in roots if root):
            if exe.is_file():
                return lambda url: subprocess.Popen([str(exe), f"--app={url}"])
    elif sys.platform.startswith("linux"):
        for name in LINUX_BROWSERS:
            if exe := shutil.which(name):
                return lambda url: subprocess.Popen([exe, f"--app={url}"], stdout=subprocess.DEVNULL,
                                                    stderr=subprocess.DEVNULL, start_new_session=True)
    return None


def window(url):
    """An app window in a Chromium browser if there is one, else a tab in the default browser."""
    (_app_browser() or webbrowser.open)(url)


# What the window shows at once while the lab starts (the first start after installing can take a
# while). A page opened from disk may not ask the lab itself whether it is up, so the launcher
# leaves a file beside it when it is (ready.png) or when it could not start (failed.png).
STARTING = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Dyeroom</title>
<style>
  html { height: 100%; background: #141311; color: #ece4d4;
         font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
  body { margin: 0; height: 100%; display: grid; place-items: center; text-align: center; padding: 0 24px; }
  h1 { font-size: 22px; font-weight: 600; letter-spacing: -0.01em; margin: 0 0 6px; }
  p { margin: 0 auto; color: #a59d8f; max-width: 28rem; }
</style></head>
<body><div><h1>Starting the lab</h1><p id="note">The first start after installing takes a little longer.</p></div>
<script>
  const lab = LAB, log = LOG, since = Date.now();
  const look = (name, then) => { const img = new Image(); img.onload = then; img.src = name + "?" + Date.now(); };
  (function wait() {
    look("ready.png", () => location.replace(lab));
    look("failed.png", () => {
      document.getElementById("note").textContent = "Dyeroom did not start. What it said is in " + log;
    });
    if (Date.now() - since < 300000) setTimeout(wait, 400);
  })();
</script></body></html>
"""


def _starting_window(open_window, url):
    """Open the starting page now; returns the folder to leave ready.png or failed.png in."""
    folder = folders()[1] / "starting"
    folder.mkdir(parents=True, exist_ok=True)
    for name in ("ready.png", "failed.png"):
        (folder / name).unlink(missing_ok=True)
    page = folder / "index.html"
    page.write_text(STARTING.replace("LAB", json.dumps(url)).replace("LOG", json.dumps(str(folders()[1] / "lab.log"))),
                    encoding="utf-8")
    open_window(page.as_uri())
    return folder


def open_lab(show=True, foreground=False):
    if foreground:  # in this terminal, with its messages; Ctrl-C stops it
        info = {"port": _free_port(), "key": secrets.token_urlsafe(24), "pid": os.getpid()}
        os.environ.update(settings(info["port"], info["key"]))
        _instance_file().parent.mkdir(parents=True, exist_ok=True)
        _instance_file().write_text(json.dumps(info), encoding="utf-8")
        print(f"Dyeroom: http://127.0.0.1:{info['port']}/app?key={info['key']}")
        if show:
            window(f"http://127.0.0.1:{info['port']}/app?key={info['key']}")
        serve()
        return
    info = _running()
    if info is None:
        print("Starting the lab...")
        info = {"port": _free_port(), "key": secrets.token_urlsafe(24)}
        url = f"http://127.0.0.1:{info['port']}/app?key={info['key']}"
        app_window = _app_browser() if show else None
        starting = _starting_window(app_window, url) if app_window else None
        if show and not starting and sys.platform == "darwin" and not sys.stdout.isatty():
            note = 'display notification "Starting the lab, a moment." with title "Dyeroom"'  # no window to say it
            try:  # never wait on it: with no one logged in to see it, it may not return
                subprocess.run(["osascript", "-e", note], capture_output=True, check=False, timeout=5)
            except subprocess.TimeoutExpired:
                pass
        try:
            _start(info)
        except SystemExit:
            if starting:
                shutil.copyfile(ICON, starting / "failed.png")
            raise
        if starting:
            shutil.copyfile(ICON, starting / "ready.png")  # the starting page turns into the lab
        elif show:
            window(url)
        from . import metadata
        if not metadata.available():
            print("Tip: with ExifTool installed, exports keep the camera's metadata "
                  "(macOS: brew install exiftool; Linux: sudo apt install libimage-exiftool-perl; "
                  "Windows: winget install OliverBetz.ExifTool).")
    else:
        url = f"http://127.0.0.1:{info['port']}/app?key={info['key']}"
        if show:
            window(url)
    if later := newer_version():
        print(f"Dyeroom {later} is out: run the installer again, or: uv tool upgrade dyeroom")
    print(f"Dyeroom is open at {url}\nIt stops by itself some minutes after the last window closes (or: dyeroom stop).")


def serve():
    """Run the lab (the web app in local mode) in this process until it stops."""
    from .web import app as web
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))  # Uvicorn hands it back after stopping: end tidily
    try:
        web.main()
    finally:
        try:
            if json.loads(_instance_file().read_text(encoding="utf-8")).get("pid") == os.getpid():
                _instance_file().unlink()
        except (OSError, ValueError):
            pass


def stop():
    info = _running()
    if info is None:
        print("The lab is not running.")
        return
    os.kill(info["pid"], signal.SIGTERM)
    if sys.platform == "win32":  # Windows ends it at once, before it can tidy up after itself
        _instance_file().unlink(missing_ok=True)
    print("The lab is stopping.")


def version():
    """The installed Dyeroom's version."""
    try:
        return package_metadata.version("dyeroom")
    except package_metadata.PackageNotFoundError:
        return "0"


def newer(latest, than):
    """Whether version latest (X.Y.Z) comes after than."""
    numbers = lambda v: tuple(int(n) for n in re.findall(r"\d+", v or "")[:3])
    return bool(latest) and numbers(latest) > numbers(than)


def newer_version():
    """A newer Dyeroom on PyPI, as the lab last found it (version.json), or None."""
    try:
        latest = json.loads((folders()[0] / "version.json").read_text(encoding="utf-8")).get("latest")
    except (OSError, ValueError, AttributeError):
        return None
    return latest if newer(latest, version()) else None


def _mac_icon(target):
    """Dyeroom.icns from the app's 512 px icon, with the tools every Mac has (sips, iconutil)."""
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "Dyeroom.iconset"
        iconset.mkdir()
        for size in (16, 32, 128, 256, 512):
            for scale in (1, 2):
                if size * scale <= 512:
                    name = f"icon_{size}x{size}{'@2x' if scale == 2 else ''}.png"
                    subprocess.run(["sips", "-z", str(size * scale), str(size * scale), str(ICON), "--out",
                                    str(iconset / name)], capture_output=True, check=True)
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(target)], capture_output=True, check=True)


def shortcut(home=None):
    """An icon that opens the lab: Dyeroom.app in ~/Applications on macOS, a desktop entry on Linux,
    a Start menu shortcut on Windows. Made on this computer, it needs no signing. Returns where it went."""
    home = Path(home or Path.home())
    if sys.platform == "win32":
        return _windows_shortcut(home)
    command = f'"{sys.executable}" -I -u -m dyeroom.local open'  # -u: its log is written as it goes
    if sys.platform == "darwin":
        app = home / "Applications" / "Dyeroom.app"
        (app / "Contents" / "MacOS").mkdir(parents=True, exist_ok=True)
        (app / "Contents" / "Resources").mkdir(exist_ok=True)
        with open(app / "Contents" / "Info.plist", "wb") as f:
            plistlib.dump({"CFBundleName": "Dyeroom", "CFBundleDisplayName": "Dyeroom",
                           "CFBundleIdentifier": "com.sysi.dyeroom", "CFBundleExecutable": "Dyeroom",
                           "CFBundleIconFile": "Dyeroom", "CFBundlePackageType": "APPL",
                           "CFBundleShortVersionString": version(),
                           "LSArchitecturePriority": ["arm64", "x86_64"],
                           "LSUIElement": True}, f)  # it opens the window and is gone: no Dock icon of its own
        launcher = app / "Contents" / "MacOS" / "Dyeroom"
        log = folders()[1] / "open.log"  # what it says, opened from the icon, for when it does not open
        # Finder may start a script under Rosetta, as an Intel program; Python must then still run as what
        # this Mac is (its libraries are for that), so on Apple silicon it is started as arm64 outright.
        launcher.write_text(f'#!/bin/sh\nmkdir -p "{log.parent}"\n'
                            'if [ "$(/usr/sbin/sysctl -n hw.optional.arm64 2>/dev/null)" = "1" ]; then\n'
                            f'  exec /usr/bin/arch -arm64 {command} >> "{log}" 2>&1\nfi\n'
                            f'exec {command} >> "{log}" 2>&1\n', encoding="utf-8")
        launcher.chmod(0o755)
        try:
            _mac_icon(app / "Contents" / "Resources" / "Dyeroom.icns")
        except (OSError, subprocess.CalledProcessError):
            pass  # the app works with the generic icon
        os.utime(app)  # Finder notices the new icon
        return app
    if sys.platform.startswith("linux"):
        share = Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share"))
        icon = share / "icons" / "hicolor" / "512x512" / "apps" / "dyeroom.png"
        icon.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ICON, icon)
        entry = share / "applications" / "dyeroom.desktop"
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_text("[Desktop Entry]\nType=Application\nName=Dyeroom\n"
                         "Comment=Develop photographs on simulated film\n"
                         f"Exec={command}\nIcon={icon}\nTerminal=false\nCategories=Graphics;Photography;\n",
                         encoding="utf-8")
        return entry
    raise SystemExit("Shortcuts are made on macOS, Linux and Windows.")


def _windows_shortcut(home):
    """Dyeroom in the Start menu: a shortcut to the installed Python without a console window
    (pythonw), with the app's icon. PowerShell makes it, as every Windows has."""
    from PIL import Image
    data = folders()[0]
    data.mkdir(parents=True, exist_ok=True)
    icon = data / "Dyeroom.ico"
    Image.open(ICON).save(icon, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    roaming = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
    programs = roaming / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    programs.mkdir(parents=True, exist_ok=True)
    link = programs / "Dyeroom.lnk"
    quoted = lambda path: str(path).replace("'", "''")  # PowerShell single-quoted strings
    script = (f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{quoted(link)}'); "
              f"$s.TargetPath = '{quoted(pythonw if pythonw.is_file() else sys.executable)}'; "
              "$s.Arguments = '-I -u -m dyeroom.local open'; "
              f"$s.IconLocation = '{quoted(icon)}'; $s.WorkingDirectory = '{quoted(data)}'; "
              "$s.Description = 'Develop photographs on simulated film'; $s.Save()")
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], check=True,
                   capture_output=True, creationflags=NO_WINDOW)
    return link


def fetch_colourise_model(progress=None):
    """Fetch DDColor's weights (Apache-2.0), for colourising black-and-white originals, into the
    app-data folder, checked against their SHA-256; returns where they are. progress(done, total)
    hears how far it is. OSError or ValueError if it could not be done (nothing is then kept)."""
    target = folders()[0] / MODEL_NAME
    if target.is_file():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    part, digest = target.with_suffix(".part"), hashlib.sha256()
    with urllib.request.urlopen(MODEL_URL, timeout=60) as reply, open(part, "wb") as out:
        total, done = int(reply.headers.get("content-length") or 0), 0
        while chunk := reply.read(1 << 20):
            out.write(chunk)
            digest.update(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    if digest.hexdigest() != MODEL_SHA256:
        part.unlink()
        raise ValueError("The download did not match the model it should be; nothing was kept.")
    part.replace(target)
    return target


def colourise_model():
    """The command: fetch the colourising model, saying how far it is."""
    if (folders()[0] / MODEL_NAME).is_file():
        print(f"The colourising model is already there: {folders()[0] / MODEL_NAME}")
        return
    print("Fetching the colourising model (DDColor, 270 MB, once)...")
    shown = []

    def progress(done, total):
        if total and (percent := 100 * done // total) not in shown:
            shown.append(percent)
            print(f"\r{percent:3d} %", end="", flush=True)
    try:
        fetch_colourise_model(progress)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"\n{exc}")
    print("\nDone. Colourising is there now (reload Dyeroom's window if it is open).")


def main(argv):
    command, flags = (argv[0], argv[1:]) if argv else ("open", [])
    if command == "open":
        open_lab(show="--no-window" not in flags, foreground="--foreground" in flags)
    elif command == "stop":
        stop()
    elif command == "shortcut":
        print(f"Added: {shortcut()}")
    elif command == "colourise-model":
        colourise_model()
    elif command == "serve":
        serve()


def entry():
    """The dyeroom command: the lab, or given photographs, the command-line developer (which
    loads the whole film model, so it is imported only then)."""
    argv = sys.argv[1:]
    if not argv or argv[0] in COMMANDS:
        main(argv)
    else:
        from .__main__ import main as develop
        develop()


if __name__ == "__main__":
    main(sys.argv[1:])
