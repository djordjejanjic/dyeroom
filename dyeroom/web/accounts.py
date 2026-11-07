"""Accounts and film: who is signed in, and how many photographs they may still develop.

One SQLite file beside the uploads holds it all:

  users          one per sign-in (provider + subject), with the email and name it gave
  sessions       sign-in cookies; only their SHA-256 is stored
  logins         sign-ins under way (state and nonce), for ten minutes
  ledger         every change to a user's frames: welcome frames, rolls bought,
                 photographs developed, refunds, grants
  photos         each uploaded photograph and how it was paid for. A photograph costs one
                 frame the first time it is developed; developing it again with other
                 settings is free. If it cannot be developed at all, the frame comes back.
                 Adding the same file again later is free too: each photograph keeps a
                 fingerprint, a keyed hash of the file's bytes (HMAC-SHA-256 with a secret
                 kept beside the database, and the user's id), for FINGERPRINT_DAYS. It
                 cannot be turned back into the picture or matched across accounts; no
                 pictures or file names are kept.
  presets        saved development settings and finishing adjustments, by name
  subscriptions  monthly or yearly plans, kept in step with the payment provider
  events         webhook events already handled
  secrets        the key for fingerprints, kept in the database so a backup restores it too

A plan covers up to PLAN_CAP photographs per billing period before frames are used.

Backups: the server copies the database to DYEROOM_DATA/backups once a day and keeps the
copies BACKUP_DAYS (default 14). That protects against mistakes, not against losing the
server: replicate DYEROOM_DATA/accounts.db off the server too (Litestream, see DEVELOPING.md).

Admin:  python -m dyeroom.web.accounts show EMAIL
        python -m dyeroom.web.accounts grant EMAIL FRAMES [NOTE]   (negative to take back)
        python -m dyeroom.web.accounts backup [FOLDER]              (a copy now; default DATA/backups)
"""
import contextlib
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import sys
import threading
import time
import uuid
from pathlib import Path

FREE_FRAMES = int(os.environ.get("DYEROOM_FREE_FRAMES", "5"))
PLAN_CAP = int(os.environ.get("DYEROOM_PLAN_CAP", "1000"))  # photographs per billing period (fair use)
FINGERPRINT_DAYS = float(os.environ.get("DYEROOM_FINGERPRINT_DAYS", "30"))  # re-adding a file is free this long
MAX_PRESETS = 100
SESSION_SECONDS = 90 * 86400
LOGIN_SECONDS = 600
ACTIVE = ("active", "trialing", "past_due")  # past_due: the provider is still retrying the payment
GRACE = 3 * 86400                            # a plan keeps working this long past its period end
BACKUP_DAYS = float(os.environ.get("DYEROOM_BACKUP_DAYS", "14"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  subject TEXT NOT NULL,
  email TEXT,
  name TEXT,
  customer_id TEXT,
  created REAL NOT NULL,
  deleted REAL,
  UNIQUE (provider, subject)
);
CREATE INDEX IF NOT EXISTS users_customer ON users (customer_id);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  expires REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS logins (
  state TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  nonce TEXT NOT NULL,
  created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS ledger (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  delta INTEGER NOT NULL,
  reason TEXT NOT NULL,
  ref TEXT,
  created REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS ledger_user ON ledger (user_id);
CREATE UNIQUE INDEX IF NOT EXISTS ledger_once ON ledger (reason, ref) WHERE reason IN ('welcome', 'roll');
CREATE TABLE IF NOT EXISTS photos (
  upload_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  paid TEXT,
  charged REAL,
  jobs INTEGER NOT NULL DEFAULT 0,
  developed INTEGER NOT NULL DEFAULT 0,
  created REAL NOT NULL,
  fingerprint TEXT
);
CREATE INDEX IF NOT EXISTS photos_user ON photos (user_id, paid, charged);
CREATE TABLE IF NOT EXISTS subscriptions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  status TEXT NOT NULL,
  plan TEXT,
  period_start REAL,
  period_end REAL,
  ends REAL,
  updated TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS subscriptions_user ON subscriptions (user_id);
CREATE TABLE IF NOT EXISTS presets (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  name TEXT NOT NULL,
  settings TEXT NOT NULL,
  updated REAL NOT NULL,
  UNIQUE (user_id, name)
);
CREATE TABLE IF NOT EXISTS events (
  id TEXT PRIMARY KEY,
  received REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS secrets (
  name TEXT PRIMARY KEY,
  value BLOB NOT NULL
);
"""


class NoFilm(Exception):
    """No frames left, and no plan that covers another photograph."""


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=5000")  # backups and replication read alongside
        self.db.executescript(SCHEMA)
        columns = {row[1] for row in self.db.execute("PRAGMA table_info(photos)")}
        if "fingerprint" not in columns:  # databases from before fingerprints
            self.db.execute("ALTER TABLE photos ADD COLUMN fingerprint TEXT")
        self.db.execute("CREATE INDEX IF NOT EXISTS photos_fingerprint ON photos (user_id, fingerprint)")
        self.lock = threading.RLock()
        self.path = Path(path)
        row = self.db.execute("SELECT value FROM secrets WHERE name = 'fingerprint'").fetchone()
        if row is None:
            key_file = self.path.with_name("fingerprint.key")  # where earlier versions kept it
            key = key_file.read_bytes() if key_file.exists() else secrets.token_bytes(32)
            self.db.execute("INSERT INTO secrets (name, value) VALUES ('fingerprint', ?)", (key,))
            row = (key,)
        self.key = bytes(row[0])

    @contextlib.contextmanager
    def tx(self):
        """One write transaction at a time; everything inside commits or nothing does."""
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                yield self.db
            except BaseException:
                self.db.execute("ROLLBACK")
                raise
            self.db.execute("COMMIT")

    def _one(self, sql, args=()):
        with self.lock:
            return self.db.execute(sql, args).fetchone()

    # --- users and sessions ---------------------------------------------------------------

    def known(self, provider, subject):
        """Whether this identity has an account here already (deleted ones too)."""
        return self._one("SELECT 1 FROM users WHERE provider = ? AND subject = ?", (provider, subject)) is not None

    def sign_in(self, provider, subject, email=None, name=None, welcome=True):
        """The user for this identity, created with the welcome frames on first sign-in
        (unless welcome is False: too many new accounts from one address)."""
        now = time.time()
        with self.tx() as db:
            row = db.execute("SELECT id FROM users WHERE provider = ? AND subject = ?", (provider, subject)).fetchone()
            if row:  # Apple sends the name only the first time: keep what we have
                db.execute("UPDATE users SET email = COALESCE(?, email), name = COALESCE(?, name), deleted = NULL "
                           "WHERE id = ?", (email, name, row["id"]))
                return row["id"]
            user_id = uuid.uuid4().hex
            db.execute("INSERT INTO users (id, provider, subject, email, name, created) VALUES (?, ?, ?, ?, ?, ?)",
                       (user_id, provider, subject, email, name, now))
            if FREE_FRAMES and welcome:
                db.execute("INSERT INTO ledger (user_id, delta, reason, ref, created) VALUES (?, ?, 'welcome', ?, ?)",
                           (user_id, FREE_FRAMES, user_id, now))
            return user_id

    def user(self, user_id):
        return self._one("SELECT * FROM users WHERE id = ? AND deleted IS NULL", (user_id,))

    def user_by_email(self, email):
        return self._one("SELECT * FROM users WHERE lower(email) = lower(?) AND deleted IS NULL "
                         "ORDER BY created LIMIT 1", (email,))

    def user_by_customer(self, customer_id):
        return self._one("SELECT * FROM users WHERE customer_id = ? AND deleted IS NULL", (customer_id,))

    def set_customer(self, user_id, customer_id):
        with self.tx() as db:
            db.execute("UPDATE users SET customer_id = ? WHERE id = ?", (customer_id, user_id))

    def new_session(self, user_id):
        token = secrets.token_urlsafe(32)
        now = time.time()
        with self.tx() as db:
            db.execute("DELETE FROM sessions WHERE expires < ?", (now,))
            db.execute("INSERT INTO sessions (token_hash, user_id, expires) VALUES (?, ?, ?)",
                       (_hash(token), user_id, now + SESSION_SECONDS))
        return token

    def user_for(self, token):
        return self._one("SELECT users.* FROM sessions JOIN users ON users.id = sessions.user_id "
                         "WHERE token_hash = ? AND expires > ? AND deleted IS NULL", (_hash(token), time.time()))

    def end_session(self, token):
        with self.tx() as db:
            db.execute("DELETE FROM sessions WHERE token_hash = ?", (_hash(token),))

    def delete_user(self, user_id):
        """Sign out everywhere and forget the email and name. The ledger stays (it is the
        record of payments), and so does the identity, so the free frames are not given twice."""
        with self.tx() as db:
            db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            db.execute("DELETE FROM presets WHERE user_id = ?", (user_id,))
            db.execute("UPDATE photos SET fingerprint = NULL WHERE user_id = ?", (user_id,))
            db.execute("UPDATE users SET email = NULL, name = NULL, deleted = ? WHERE id = ?", (time.time(), user_id))

    def begin_login(self, provider):
        state, nonce = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
        now = time.time()
        with self.tx() as db:
            db.execute("DELETE FROM logins WHERE created < ?", (now - LOGIN_SECONDS,))
            db.execute("INSERT INTO logins (state, provider, nonce, created) VALUES (?, ?, ?, ?)",
                       (state, provider, nonce, now))
        return state, nonce

    def finish_login(self, state):
        """(provider, nonce) of a sign-in under way, used once."""
        with self.tx() as db:
            row = db.execute("SELECT * FROM logins WHERE state = ?", (state,)).fetchone()
            db.execute("DELETE FROM logins WHERE state = ?", (state,))
        if row is None or row["created"] < time.time() - LOGIN_SECONDS:
            return None
        return row["provider"], row["nonce"]

    # --- frames ---------------------------------------------------------------------------

    @staticmethod
    def _balance(db, user_id):
        return db.execute("SELECT COALESCE(SUM(delta), 0) FROM ledger WHERE user_id = ?", (user_id,)).fetchone()[0]

    @staticmethod
    def _plan(db, user_id, now):
        marks = ",".join("?" * len(ACTIVE))
        return db.execute(f"SELECT * FROM subscriptions WHERE user_id = ? AND status IN ({marks}) "
                          "AND (period_end IS NULL OR period_end + ? > ?) ORDER BY period_end DESC LIMIT 1",
                          (user_id, *ACTIVE, GRACE, now)).fetchone()

    @staticmethod
    def _used(db, user_id, since):
        return db.execute("SELECT COUNT(*) FROM photos WHERE user_id = ? AND paid = 'plan' AND charged >= ?",
                          (user_id, since or 0)).fetchone()[0]

    def grant(self, user_id, frames, reason="grant", ref=None):
        """Add (or take back) frames. Welcome frames and rolls count once per ref."""
        with self.tx() as db:
            cur = db.execute("INSERT OR IGNORE INTO ledger (user_id, delta, reason, ref, created) VALUES (?, ?, ?, ?, ?)",
                             (user_id, frames, reason, ref, time.time()))
            return cur.rowcount == 1

    def summary(self, user_id, now=None):
        now = now or time.time()
        with self.lock:
            user = self.db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            frames = self._balance(self.db, user_id)
            sub = self._plan(self.db, user_id, now)
            plan, available = None, max(0, frames)
            if sub:
                used = self._used(self.db, user_id, sub["period_start"])
                plan = {"id": sub["plan"], "status": sub["status"], "renews": None if sub["ends"] else sub["period_end"],
                        "ends": sub["ends"], "used": used, "cap": PLAN_CAP}
                available += max(0, PLAN_CAP - used)
            return {"id": user_id, "email": user["email"], "name": user["name"], "frames": frames, "plan": plan,
                    "available": available, "customer": bool(user["customer_id"])}

    # --- photographs ----------------------------------------------------------------------

    def fingerprint(self, user_id, sha256_hex):
        """The keyed fingerprint stored for a file whose SHA-256 is sha256_hex."""
        return hmac.new(self.key, f"{user_id}:{sha256_hex.lower()}".encode(), hashlib.sha256).hexdigest()

    @staticmethod
    def _developed_before(db, user_id, print_, besides=None):
        return db.execute("SELECT 1 FROM photos WHERE user_id = ? AND fingerprint = ? AND developed = 1 "
                          "AND upload_id IS NOT ? LIMIT 1", (user_id, print_, besides)).fetchone() is not None

    def is_free(self, user_id, sha256_hex):
        """Whether this user has developed this very file before (so adding it again is free)."""
        with self.lock:
            return self._developed_before(self.db, user_id, self.fingerprint(user_id, sha256_hex))

    def add_photo(self, upload_id, user_id, sha256_hex=None):
        print_ = self.fingerprint(user_id, sha256_hex) if sha256_hex else None
        with self.tx() as db:
            db.execute("INSERT INTO photos (upload_id, user_id, created, fingerprint) VALUES (?, ?, ?, ?)",
                       (upload_id, user_id, time.time(), print_))

    def photo(self, upload_id):
        return self._one("SELECT * FROM photos WHERE upload_id = ?", (upload_id,))

    def charge(self, upload_id, user_id, now=None):
        """Pay for developing this photograph: free if it is already paid for, else from the
        plan while it has room, else one frame. Raises LookupError if the photograph is not
        this user's, NoFilm if there is nothing to pay with."""
        now = now or time.time()
        with self.tx() as db:
            photo = db.execute("SELECT * FROM photos WHERE upload_id = ?", (upload_id,)).fetchone()
            if photo is None or photo["user_id"] != user_id:
                raise LookupError(upload_id)
            db.execute("UPDATE photos SET jobs = jobs + 1 WHERE upload_id = ?", (upload_id,))
            if photo["paid"]:
                return photo["paid"]
            sub = self._plan(db, user_id, now)
            if photo["fingerprint"] and self._developed_before(db, user_id, photo["fingerprint"], upload_id):
                paid = "again"  # the same file, developed before: free
            elif sub and self._used(db, user_id, sub["period_start"]) < PLAN_CAP:
                paid = "plan"
            elif self._balance(db, user_id) > 0:
                paid = "frame"
                db.execute("INSERT INTO ledger (user_id, delta, reason, ref, created) VALUES (?, -1, 'develop', ?, ?)",
                           (user_id, upload_id, now))
            else:
                raise NoFilm()
            db.execute("UPDATE photos SET paid = ?, charged = ? WHERE upload_id = ?", (paid, now, upload_id))
            return paid

    def settle(self, upload_id, developed):
        """A job for this photograph has ended. If it was never developed and nothing else is
        trying, what it cost comes back."""
        with self.tx() as db:
            photo = db.execute("SELECT * FROM photos WHERE upload_id = ?", (upload_id,)).fetchone()
            if photo is None:
                return
            jobs = max(0, photo["jobs"] - 1)
            if developed:
                db.execute("UPDATE photos SET jobs = ?, developed = 1 WHERE upload_id = ?", (jobs, upload_id))
            elif jobs == 0 and not photo["developed"] and photo["paid"]:
                self._refund(db, photo)
            else:
                db.execute("UPDATE photos SET jobs = ? WHERE upload_id = ?", (jobs, upload_id))

    @staticmethod
    def _refund(db, photo):
        if photo["paid"] == "frame":
            db.execute("INSERT INTO ledger (user_id, delta, reason, ref, created) VALUES (?, 1, 'refund', ?, ?)",
                       (photo["user_id"], photo["upload_id"], time.time()))
        db.execute("UPDATE photos SET jobs = 0, paid = NULL, charged = NULL WHERE upload_id = ?", (photo["upload_id"],))

    def recover(self):
        """After a restart the job queue is gone: refund photographs that never got developed.
        Fingerprints older than FINGERPRINT_DAYS are erased."""
        with self.tx() as db:
            db.execute("UPDATE photos SET fingerprint = NULL WHERE fingerprint IS NOT NULL AND created < ?",
                       (time.time() - FINGERPRINT_DAYS * 86400,))
            for photo in db.execute("SELECT * FROM photos WHERE paid IS NOT NULL AND developed = 0").fetchall():
                self._refund(db, photo)
            db.execute("UPDATE photos SET jobs = 0 WHERE jobs != 0")

    # --- plans and webhook events ---------------------------------------------------------

    def put_subscription(self, sub_id, user_id, status, plan, period_start, period_end, ends, updated):
        """Record a plan's state, unless a newer one is already recorded (webhooks can arrive
        out of order). `updated` is the provider's ISO 8601 time, which sorts as text."""
        with self.tx() as db:
            row = db.execute("SELECT updated FROM subscriptions WHERE id = ?", (sub_id,)).fetchone()
            if row and row["updated"] > updated:
                return False
            db.execute("INSERT OR REPLACE INTO subscriptions (id, user_id, status, plan, period_start, period_end, "
                       "ends, updated) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                       (sub_id, user_id, status, plan, period_start, period_end, ends, updated))
            return True

    def subscription_ids(self, user_id):
        with self.lock:
            return [r[0] for r in self.db.execute("SELECT id FROM subscriptions WHERE user_id = ?", (user_id,))]

    # --- presets --------------------------------------------------------------------------

    def presets(self, user_id):
        with self.lock:
            rows = self.db.execute("SELECT id, name, settings FROM presets WHERE user_id = ? ORDER BY name COLLATE NOCASE",
                                   (user_id,)).fetchall()
        return [{"id": r["id"], "name": r["name"], "settings": json.loads(r["settings"])} for r in rows]

    def save_preset(self, user_id, name, settings):
        """Save under this name, replacing a preset of the same name. Returns its id, or None
        when the user already has MAX_PRESETS others."""
        with self.tx() as db:
            row = db.execute("SELECT id FROM presets WHERE user_id = ? AND name = ?", (user_id, name)).fetchone()
            if row is None and db.execute("SELECT COUNT(*) FROM presets WHERE user_id = ?",
                                          (user_id,)).fetchone()[0] >= MAX_PRESETS:
                return None
            preset_id = row["id"] if row else uuid.uuid4().hex
            db.execute("INSERT OR REPLACE INTO presets (id, user_id, name, settings, updated) VALUES (?, ?, ?, ?, ?)",
                       (preset_id, user_id, name, json.dumps(settings), time.time()))
            return preset_id

    def delete_preset(self, user_id, preset_id):
        with self.tx() as db:
            db.execute("DELETE FROM presets WHERE id = ? AND user_id = ?", (preset_id, user_id))

    def take_back_roll(self, transaction_id, adjustment_id):
        """A bought roll was refunded: the frames of it not yet used leave the account.
        Returns how many were taken, or None if no roll was bought in that transaction."""
        with self.tx() as db:
            roll = db.execute("SELECT user_id, delta FROM ledger WHERE reason = 'roll' AND ref = ?",
                              (transaction_id,)).fetchone()
            if roll is None:
                return None
            if db.execute("SELECT 1 FROM ledger WHERE reason = 'roll refunded' AND ref IN (?, ?)",
                          (adjustment_id, transaction_id)).fetchone():
                return 0
            taken = min(roll["delta"], max(0, self._balance(db, roll["user_id"])))
            db.execute("INSERT INTO ledger (user_id, delta, reason, ref, created) VALUES (?, ?, 'roll refunded', ?, ?)",
                       (roll["user_id"], -taken, transaction_id, time.time()))
            return taken

    # --- for the owner ----------------------------------------------------------------------

    def report(self, since, now=None):
        """Accounts and sales since a time, for the admin page."""
        now = now or time.time()
        with self.lock:
            def count(sql, *args):
                return self.db.execute(sql, args).fetchone()[0]
            marks = ",".join("?" * len(ACTIVE))
            return {
                "accounts": count("SELECT COUNT(*) FROM users WHERE deleted IS NULL"),
                "new_accounts": count("SELECT COUNT(*) FROM users WHERE created >= ?", since),
                "rolls": count("SELECT COUNT(*) FROM ledger WHERE reason = 'roll' AND created >= ?", since),
                "rolls_refunded": count("SELECT COUNT(*) FROM ledger WHERE reason = 'roll refunded' AND created >= ?", since),
                "plans": count(f"SELECT COUNT(DISTINCT user_id) FROM subscriptions WHERE status IN ({marks}) "
                               "AND (period_end IS NULL OR period_end + ? > ?)", *ACTIVE, GRACE, now),
                "developed": count("SELECT COUNT(*) FROM photos WHERE paid IS NOT NULL AND charged >= ?", since),
                "paid_with": dict(self.db.execute("SELECT paid, COUNT(*) FROM photos WHERE paid IS NOT NULL AND "
                                                  "charged >= ? GROUP BY paid", (since,)).fetchall()),
                "refunded_frames": count("SELECT COUNT(*) FROM ledger WHERE reason = 'refund' AND created >= ?", since),
            }

    def snapshot(self, folder):
        """A consistent copy of the database, made while it is in use, as
        folder/accounts-<date>-<time>.db; copies older than BACKUP_DAYS are deleted."""
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"accounts-{time.strftime('%Y%m%d-%H%M%S')}.db"
        partial = folder / f"{target.name}.part"
        copy = sqlite3.connect(str(partial))
        try:
            with self.lock:
                self.db.backup(copy)
            if copy.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise sqlite3.DatabaseError("the copy failed its integrity check")
        finally:
            copy.close()
        partial.chmod(0o600)
        os.replace(partial, target)
        for old in folder.glob("accounts-*.db"):
            if old.stat().st_mtime < time.time() - BACKUP_DAYS * 86400:
                old.unlink(missing_ok=True)
        return target

    def last_snapshot(self, folder):
        """When the newest copy in folder was made (0 if there is none)."""
        return max((p.stat().st_mtime for p in Path(folder).glob("accounts-*.db")), default=0.0)

    def event_seen(self, event_id):
        return self._one("SELECT 1 FROM events WHERE id = ?", (event_id,)) is not None

    def mark_event(self, event_id):
        with self.tx() as db:
            db.execute("INSERT OR IGNORE INTO events (id, received) VALUES (?, ?)", (event_id, time.time()))


def _admin(argv):
    data = Path(os.environ.get("DYEROOM_DATA", "web-data")).resolve()
    store = Store(data / "accounts.db")
    if argv[:1] == ["backup"]:
        print(store.snapshot(argv[1] if len(argv) > 1 else data / "backups"))
        return
    if len(argv) >= 2 and argv[0] in ("show", "grant"):
        user = store.user_by_email(argv[1])
        if user is None:
            sys.exit(f"No account with the email {argv[1]}")
        if argv[0] == "grant":
            store.grant(user["id"], int(argv[2]), "grant", " ".join(argv[3:]) or None)
        s = store.summary(user["id"])
        print(f"{s['email']}  {s['name'] or ''}\n  frames left: {s['frames']}\n  plan: {s['plan'] or 'none'}")
        return
    sys.exit(__doc__[__doc__.index("Admin:"):])


if __name__ == "__main__":
    _admin(sys.argv[1:])
