"""Fair use: how much one person may ask of the lab in a while.

A person is a signed-in account, or else an IP address (an IPv6 address counts by its /64,
which is one household or phone). Behind a reverse proxy, uvicorn takes the client's address
from X-Forwarded-For only when the proxy is listed in DYEROOM_TRUSTED_PROXIES; otherwise every
visitor would look like the proxy and share one allowance. Behind Cloudflare, set
DYEROOM_CLIENT_IP_HEADER=cf-connecting-ip: Cloudflare keeps whatever X-Forwarded-For a
browser sends and adds the real address after it, so that header could be faked to get
round the limits; CF-Connecting-IP is Cloudflare's own. Only when nothing but Cloudflare can
reach the app (its tunnel), or the header itself could be faked.

Counts live in memory and are forgotten once their window has passed: nothing here is written
to disk, and a restart starts everyone afresh.

Configuration (environment), per person unless said otherwise:
  DYEROOM_UPLOADS_PER_HOUR      photographs added               (default 120)
  DYEROOM_DEVELOPS_PER_HOUR     developments, first or again; a full-size one counts
                                  as FULL_WEIGHT, being that much longer in the developer
                                                                  (default 60)
  DYEROOM_EXPORTS_PER_HOUR      exported files                  (default 120: a roll of 36,
                                  exported three times; caps what one person can pull)
  DYEROOM_SAMPLES_PER_HOUR      sample developments, per address (default 30)
  DYEROOM_NEW_ACCOUNTS_PER_DAY  accounts given free frames, per address (default 3)
  DYEROOM_WAITING_PER_PERSON    photographs waiting for the developer at once (default 40)
  DYEROOM_HELD_GB_PER_PERSON    photographs held in the lab at once (default 4)
  DYEROOM_QUEUE_MAX             photographs waiting for the developer, everyone together (default 400)
  DYEROOM_UNLIMITED             addresses or account ids none of the per-person limits apply to,
                                  comma-separated (the owner at work, say); an IPv6 address
                                  stands for its /64. The lab-wide queue limit still applies.
"""
import collections
import ipaddress
import math
import os
import threading
import time


def _number(name, default):
    return float(os.environ.get(name, default))


class Window:
    """At most `count` events per `seconds` for each key (a sliding window)."""

    def __init__(self, count, seconds):
        self.count, self.seconds = int(count), seconds
        self.events = collections.defaultdict(collections.deque)
        self.lock = threading.Lock()

    def wait(self, key, now=None, weight=1):
        """0 if one more (counting as `weight`) is allowed now, and counts it; else the
        seconds until it would be."""
        if key in UNLIMITED:
            return 0.0
        now = now or time.time()
        with self.lock:
            q = self.events[key]
            while q and q[0] <= now - self.seconds:
                q.popleft()
            if len(q) + weight > self.count:
                return q[min(len(q) - 1, len(q) + weight - self.count - 1)] + self.seconds - now if q else 0.0
            q.extend([now] * weight)
            return 0.0

    def prune(self, now=None):
        now = now or time.time()
        with self.lock:
            for key in [k for k, q in self.events.items() if not q or q[-1] <= now - self.seconds]:
                del self.events[key]


def _unlimited(entries):
    """The keys the limits leave alone, from DYEROOM_UNLIMITED."""
    keys = set()
    for entry in filter(None, (e.strip() for e in entries.split(","))):
        try:
            ip = ipaddress.ip_address(entry)
        except ValueError:
            keys.add(f"u:{entry}")
            continue
        key = str(ip) if ip.version == 4 else str(ipaddress.ip_network(f"{ip}/64", strict=False))
        keys.update({f"ip:{key}", f"sample:{key}"})
    return keys


UNLIMITED = _unlimited(os.environ.get("DYEROOM_UNLIMITED", ""))
UPLOADS = Window(_number("DYEROOM_UPLOADS_PER_HOUR", 120), 3600)
DEVELOPS = Window(_number("DYEROOM_DEVELOPS_PER_HOUR", 60), 3600)
FULL_WEIGHT = 4  # a full-size development holds the developer about four times as long as a draft
EXPORTS = Window(_number("DYEROOM_EXPORTS_PER_HOUR", 120), 3600)
SAMPLES = Window(_number("DYEROOM_SAMPLES_PER_HOUR", 30), 3600)
NEW_ACCOUNTS = Window(_number("DYEROOM_NEW_ACCOUNTS_PER_DAY", 3), 86400)
SIGN_INS = Window(30, 600)       # sign-ins started, per address
CHECKS = Window(240, 3600)       # fingerprint checks and preset changes
WINDOWS = (UPLOADS, DEVELOPS, EXPORTS, SAMPLES, NEW_ACCOUNTS, SIGN_INS, CHECKS)

WAITING = int(_number("DYEROOM_WAITING_PER_PERSON", 40))
HELD_BYTES = _number("DYEROOM_HELD_GB_PER_PERSON", 4) * 1024 ** 3
QUEUE_MAX = int(_number("DYEROOM_QUEUE_MAX", 400))
CLIENT_IP_HEADER = os.environ.get("DYEROOM_CLIENT_IP_HEADER", "").strip().lower()


def address(request):
    """The client's address as a key: IPv4 whole, IPv6 by its /64."""
    host = (request.headers.get(CLIENT_IP_HEADER) if CLIENT_IP_HEADER else None) \
        or (request.client.host if request.client else "unknown")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return host
    if ip.version == 6:
        if ip.ipv4_mapped:
            return str(ip.ipv4_mapped)
        return str(ipaddress.ip_network(f"{ip}/64", strict=False))
    return str(ip)


def person(request, user=None):
    """Whom a request counts against: the account when signed in, else the address."""
    return f"u:{user['id']}" if user else f"ip:{address(request)}"


def unlimited(who):
    """Whether `who` (from person()) is spared the per-person limits."""
    return who in UNLIMITED


def minutes(seconds):
    """'a minute' / '12 minutes', for messages."""
    m = max(1, math.ceil(seconds / 60))
    return "a minute" if m == 1 else f"{m} minutes"


def prune():
    for window in WINDOWS:
        window.prune()
