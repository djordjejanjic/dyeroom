"""Telling the owner when the lab needs attention.

An alert is logged, kept in the statistics (stats.py) and, when DYEROOM_ALERT_URL is set,
sent there as an HTTP POST:

  ntfy (https://ntfy.sh/<a long secret topic>, or your own ntfy server): a push notification
     on your phone with the ntfy app; the body is plain text
  Slack or Discord incoming webhooks: JSON, as each expects
  anything else: the plain text

Alerts carry no pictures, file names or accounts. One alert of each kind per
DYEROOM_ALERT_QUIET_MINUTES (default 60), so a bad hour sends one message, not hundreds.

  python -m dyeroom.web.alerts "A test"      sends a test alert now
"""
import json
import logging
import os
import sys
import threading
import time
import urllib.parse
import urllib.request

log = logging.getLogger("dyeroom.alerts")

URL = os.environ.get("DYEROOM_ALERT_URL", "").strip()
QUIET = float(os.environ.get("DYEROOM_ALERT_QUIET_MINUTES", "60")) * 60
FAILURES = int(os.environ.get("DYEROOM_ALERT_FAILURES", "3"))   # failed developments ...
FAILURE_MINUTES = 15                                            # ... within this many minutes
QUEUE_MINUTES = float(os.environ.get("DYEROOM_ALERT_QUEUE_MINUTES", "10"))  # a photograph waited this long

_last = {}
_lock = threading.Lock()


def send(kind, message, stats=None, wait=False):
    """Raise an alert, unless one of this kind went out in the last QUIET seconds."""
    now = time.time()
    with _lock:
        if now - _last.get(kind, 0) < QUIET:
            return False
        _last[kind] = now
    log.error("Alert (%s): %s", kind, message)
    thread = threading.Thread(target=_deliver, args=(kind, message, stats), daemon=True)
    thread.start()
    if wait:
        thread.join(15)
    return True


def _deliver(kind, message, stats):
    delivered = False
    if URL:
        try:
            with urllib.request.urlopen(_request(message), timeout=10):
                delivered = True
        except (OSError, ValueError) as exc:
            log.error("Alert not delivered to DYEROOM_ALERT_URL: %s", exc)
    if stats is not None:
        try:
            stats.alert(kind, message, delivered)
        except Exception as exc:  # the alert must never take anything down with it
            log.error("Alert not recorded: %s", exc)


def _request(message):
    host = (urllib.parse.urlparse(URL).hostname or "").lower()
    text = f"Dyeroom: {message}"
    if host == "hooks.slack.com":
        body, kind = json.dumps({"text": text}).encode(), "application/json"
    elif host in ("discord.com", "discordapp.com"):
        body, kind = json.dumps({"content": text}).encode(), "application/json"
    else:
        body, kind = text.encode(), "text/plain; charset=utf-8"
    return urllib.request.Request(URL, data=body, method="POST",
                                  headers={"Content-Type": kind, "Title": "Dyeroom", "Tags": "warning"})


if __name__ == "__main__":
    logging.basicConfig()
    if not URL:
        sys.exit("Set DYEROOM_ALERT_URL first (for example https://ntfy.sh/<a long secret topic>)")
    send("test", " ".join(sys.argv[1:]) or "A test alert: alerts reach you.", wait=True)
