"""The installed lab, end to end:  python tools/smoke_local.py PHOTO

After the installer (dyeroom/web/install.sh or install.ps1) has run: finds the dyeroom command
where uv puts it, starts the lab without a window, checks that it answers only with its key,
develops PHOTO the way the page does (upload, preview, develop, the result), checks the
shortcut the installer made, and stops the lab. Exits non-zero on the first thing that fails.
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

EXE = Path.home() / ".local" / "bin" / ("dyeroom.exe" if sys.platform == "win32" else "dyeroom")


def shortcut():
    if sys.platform == "darwin":
        return Path.home() / "Applications" / "Dyeroom.app" / "Contents" / "MacOS" / "Dyeroom"
    if sys.platform == "win32":
        return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Dyeroom.lnk"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "applications" / "dyeroom.desktop"


def main():
    photo = Path(sys.argv[1])
    assert EXE.exists(), f"no dyeroom command at {EXE}"
    assert shortcut().exists(), f"no shortcut at {shortcut()}"
    started = time.monotonic()
    opened = subprocess.run([str(EXE), "open", "--no-window"], capture_output=True, text=True, timeout=600)
    found = re.search(r"http://127\.0\.0\.1:(\d+)/app\?key=(\S+)", opened.stdout)
    assert found, f"the lab did not start:\n{opened.stdout}\n{opened.stderr}"
    base, key = f"http://127.0.0.1:{found[1]}", found[2]
    print(f"started in {time.monotonic() - started:.0f} s")

    def call(path, data=None, headers=None, key_cookie=True):
        cookie = {"Cookie": f"dyeroom_key={key}"} if key_cookie else {}
        request = urllib.request.Request(base + path, data=data, headers={**cookie, **(headers or {})})
        with urllib.request.urlopen(request, timeout=600) as reply:
            return reply.status, reply.read()

    try:
        call("/api/options", key_cookie=False)
        raise AssertionError("the lab answered without its key")
    except urllib.error.HTTPError as refused:
        assert refused.code == 403, refused.code
    options = json.loads(call("/api/options")[1])
    assert options["local"], options
    boundary = uuid.uuid4().hex
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{photo.name}"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n").encode() + photo.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    upload = json.loads(call("/api/uploads", body, {"Content-Type": f"multipart/form-data; boundary={boundary}"})[1])
    for _ in range(240):
        status, _ = call(f"/api/uploads/{upload['upload_id']}/preview.jpg")
        if status == 200:
            break
        time.sleep(0.5)
    assert status == 200, "no preview"
    print("preview: made")
    started = time.monotonic()
    job = json.loads(call("/api/jobs", json.dumps({"upload_id": upload["upload_id"]}).encode(),
                          {"Content-Type": "application/json"})[1])["job_id"]
    while (state := json.loads(call(f"/api/jobs/{job}")[1]))["state"] not in ("done", "failed"):
        time.sleep(1)
    assert state["state"] == "done", state
    status, image = call(f"/api/jobs/{job}/view.jpg")
    assert status == 200 and image[:2] == b"\xff\xd8", "no result"
    print(f"developed in {time.monotonic() - started:.0f} s ({len(image) // 1024} KB)")
    stopped = subprocess.run([str(EXE), "stop"], capture_output=True, text=True, timeout=60)
    print(stopped.stdout.strip())
    for _ in range(40):
        try:
            call("/api/health")
        except (urllib.error.URLError, ConnectionError, OSError):
            print("stopped")
            return
        time.sleep(0.5)
    raise AssertionError("the lab did not stop")


if __name__ == "__main__":
    main()
