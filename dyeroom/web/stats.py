"""What the lab has done, for its owner: developments, exports, failures and alerts.

No pictures, file names or accounts: a development is recorded by its film, format, size,
how long it waited and took, the processor time and memory it used, the kind of file (.raf,
.jpg ...) and, if it failed, the error with any file name taken out. Rows are kept
STATS_DAYS. One SQLite file, DYEROOM_DATA/stats.db.

  python -m dyeroom.web.stats        the last day, week and month, and recent failures
"""
import os
import sqlite3
import sys
import threading
import time
from pathlib import Path

STATS_DAYS = float(os.environ.get("DYEROOM_STATS_DAYS", "90"))
SERVER_EUR_MONTH = float(os.environ.get("DYEROOM_SERVER_EUR_MONTH", "0") or 0)  # for the cost per frame
TYPICAL = {"draft": 15.0, "full": 75.0}  # seconds, until the lab has its own numbers

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  finished REAL NOT NULL,
  film TEXT, size TEXT, format TEXT, sample INTEGER NOT NULL DEFAULT 0,
  ok INTEGER NOT NULL,
  waited REAL, seconds REAL, cpu REAL, peak_mb REAL, megapixels REAL,
  suffix TEXT, error TEXT
);
CREATE INDEX IF NOT EXISTS jobs_finished ON jobs (finished);
CREATE TABLE IF NOT EXISTS exports (
  finished REAL NOT NULL, format TEXT, frames INTEGER NOT NULL, seconds REAL, bytes INTEGER
);
CREATE TABLE IF NOT EXISTS alerts (
  sent REAL NOT NULL, kind TEXT NOT NULL, message TEXT NOT NULL, delivered INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
  at REAL NOT NULL, kind TEXT NOT NULL
);
"""
WINDOWS = (("Last 24 hours", 86400), ("Last 7 days", 7 * 86400), ("Last 30 days", 30 * 86400))


class Stats:
    def __init__(self, path):
        self.db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.executescript(SCHEMA)
        self.lock = threading.Lock()

    def close(self):
        self.db.close()

    def _write(self, sql, args):
        with self.lock:
            self.db.execute(sql, args)

    def _rows(self, sql, args=()):
        with self.lock:
            return self.db.execute(sql, args).fetchall()

    # --- recording ------------------------------------------------------------------------

    def job(self, film, size, format_, sample, ok, waited, seconds, cpu, peak_mb, megapixels, suffix, error):
        self._write("INSERT INTO jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (time.time(), film, size, format_, int(sample), int(ok), waited, seconds, cpu, peak_mb,
                     megapixels, suffix, error))

    def export(self, format_, frames, seconds, size):
        self._write("INSERT INTO exports VALUES (?, ?, ?, ?, ?)", (time.time(), format_, frames, seconds, size))

    def alert(self, kind, message, delivered):
        self._write("INSERT INTO alerts VALUES (?, ?, ?, ?)", (time.time(), kind, message, int(delivered)))

    def event(self, kind):
        """Something worth counting: a sign-up, a limit reached."""
        self._write("INSERT INTO events VALUES (?, ?)", (time.time(), kind))

    def prune(self):
        cut = time.time() - STATS_DAYS * 86400
        with self.lock:
            for table, column in (("jobs", "finished"), ("exports", "finished"), ("alerts", "sent"), ("events", "at")):
                self.db.execute(f"DELETE FROM {table} WHERE {column} < ?", (cut,))

    # --- reading --------------------------------------------------------------------------

    def failures(self, since):
        return self._rows("SELECT * FROM jobs WHERE ok = 0 AND finished >= ? ORDER BY finished DESC", (since,))

    def typical_seconds(self, size):
        """How long a development of this size usually takes here: the median of the last 50."""
        rows = self._rows("SELECT seconds FROM jobs WHERE ok = 1 AND size = ? AND seconds IS NOT NULL "
                          "ORDER BY finished DESC LIMIT 50", (size,))
        times = sorted(r[0] for r in rows)
        return times[len(times) // 2] if len(times) >= 3 else TYPICAL.get(size, TYPICAL["draft"])

    def summary(self, now=None):
        now = now or time.time()
        out = []
        for title, span in WINDOWS:
            since = now - span
            out.append({"title": title, **self._period(since)})
        return out

    def _period(self, since):
        def one(sql, args=()):
            with self.lock:
                return self.db.execute(sql, (since, *args)).fetchone()

        jobs = one("SELECT COUNT(*) n, SUM(ok = 0) failed, SUM(sample) samples, SUM(size = 'full') fullsize, "
                   "SUM(cpu) cpu FROM jobs WHERE finished >= ?")
        sizes = {}
        for size in ("draft", "full"):
            times = sorted(r[0] for r in self._rows("SELECT seconds FROM jobs WHERE ok = 1 AND size = ? AND "
                                                    "finished >= ? AND seconds IS NOT NULL", (size, since)))
            cpus = sorted(r[0] for r in self._rows("SELECT cpu FROM jobs WHERE ok = 1 AND size = ? AND "
                                                   "finished >= ? AND cpu IS NOT NULL", (size, since)))
            waits = sorted(r[0] for r in self._rows("SELECT waited FROM jobs WHERE size = ? AND finished >= ? "
                                                    "AND waited IS NOT NULL", (size, since)))
            peaks = [r[0] for r in self._rows("SELECT peak_mb FROM jobs WHERE size = ? AND finished >= ? "
                                              "AND peak_mb IS NOT NULL", (size, since))]
            sizes[size] = {"n": len(times), "median_s": _pick(times, 0.5), "p90_s": _pick(times, 0.9),
                           "median_cpu": _pick(cpus, 0.5), "median_wait": _pick(waits, 0.5),
                           "p90_wait": _pick(waits, 0.9), "peak_mb": max(peaks) if peaks else None}
        exports = one("SELECT COUNT(*) n, SUM(frames) frames, SUM(bytes) bytes FROM exports WHERE finished >= ?")
        events = {r["kind"]: r["n"] for r in self._rows("SELECT kind, COUNT(*) n FROM events WHERE at >= ? "
                                                       "GROUP BY kind", (since,))}
        alerts = one("SELECT COUNT(*) FROM alerts WHERE sent >= ?")[0]
        return {"jobs": jobs["n"], "failed": jobs["failed"] or 0, "samples": jobs["samples"] or 0,
                "full": jobs["fullsize"] or 0, "cpu_hours": (jobs["cpu"] or 0) / 3600, "sizes": sizes,
                "exports": exports["n"], "exported_frames": exports["frames"] or 0,
                "exported_gb": (exports["bytes"] or 0) / 1e9, "events": events, "alerts": alerts}

    def recent_alerts(self, limit=10):
        return self._rows("SELECT * FROM alerts ORDER BY sent DESC LIMIT ?", (limit,))


def _pick(values, q):
    return values[min(len(values) - 1, int(q * len(values)))] if values else None


def cost_per_frame(cpu_seconds, cores, eur_month=SERVER_EUR_MONTH):
    """What one development costs in server time: the month's price over the processor
    seconds the server has in a month, times the seconds a development uses."""
    if not (eur_month and cpu_seconds and cores):
        return None
    return eur_month / (cores * 30 * 86400) * cpu_seconds


def main():
    data = Path(os.environ.get("DYEROOM_DATA", "web-data")).resolve()
    if not (data / "stats.db").exists():
        sys.exit(f"No statistics yet at {data / 'stats.db'}")
    stats = Stats(data / "stats.db")
    cores = os.cpu_count() or 1
    for period in stats.summary():
        print(f"{period['title']}: {period['jobs']} developed, {period['failed']} failed, "
              f"{period['samples']} samples, {period['exports']} exports ({period['exported_frames']} frames)")
        for size, s in period["sizes"].items():
            if s["n"]:
                cost = cost_per_frame(s["median_cpu"], cores)
                print(f"  {size}: median {s['median_s']:.1f} s (90 % within {s['p90_s']:.1f} s), "
                      f"processor {s['median_cpu'] or 0:.1f} s, waited {s['median_wait'] or 0:.0f} s, "
                      f"peak {s['peak_mb'] or 0:.0f} MB" + (f", about €{cost:.4f} a frame" if cost else ""))
    print("\nFailures in the last 7 days:")
    for row in stats.failures(time.time() - 7 * 86400)[:20]:
        print(f"  {time.strftime('%Y-%m-%d %H:%M', time.localtime(row['finished']))}  {row['suffix'] or ''}  "
              f"{row['film']} {row['size']}  {row['error']}")


if __name__ == "__main__":
    main()
