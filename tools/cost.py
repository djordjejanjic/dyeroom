"""Cost per frame: develop raws here exactly as the web server does, and price the time.

python tools/cost.py --eur-month 40 [--cores N] [--full] [RAW ...]    (default: the bundled sample)

Run it on the server you rent, or one like it. Each development runs in its own process, as on
the server (dyeroom/web/worker.py), and its processor time, peak memory and wall time are
measured. The cost of a frame is the month's price spread over the processor seconds the
server has in a month (cores x 30 days), times the processor seconds one development uses:
the cost with the server fully used. Once the lab is live, /admin shows the same from real work.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dyeroom.web.stats import cost_per_frame  # noqa: E402

SAMPLE = ROOT / "samples" / "sample-olympus-e-p7.orf"


def develop(raw, film, size, scratch):
    job_dir = Path(tempfile.mkdtemp(dir=scratch))
    params = {"source": str(raw), "name": raw.name, "film": film, "exposure": "camera", "ev": 0.0, "light": "native",
              "filter": "auto", "view": "lightbox", "display": "p3", "grain": True, "tiff": False, "rating": 400,
              "grade": 3, "bw_filter": "none", "toning": "none", "colourise": False, "format": "35mm",
              "long_edge": None if size == "full" else 2400}
    (job_dir / "params.json").write_text(json.dumps(params))
    began = time.time()
    subprocess.run([sys.executable, "-m", "dyeroom.web.worker", str(job_dir)], cwd=ROOT, capture_output=True,
                   env={**os.environ, "TMPDIR": str(scratch)})
    status = json.loads((job_dir / "status.json").read_text())
    if status.get("state") != "done":
        sys.exit(f"{raw.name}: {status.get('error')}")
    return time.time() - began, status["usage"]["cpu"], status["usage"]["peak_mb"], status["info"]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("raws", nargs="*", type=Path, default=[SAMPLE])
    ap.add_argument("--eur-month", type=float, required=True, help="the server's price a month, in euros")
    ap.add_argument("--cores", type=int, default=os.cpu_count(), help="processor cores the server has")
    ap.add_argument("--full", action="store_true", help="full size too (slow; needs several GB of memory)")
    args = ap.parse_args()
    sizes = ("draft", "full") if args.full else ("draft",)
    print(f"{args.cores} cores, €{args.eur_month:g} a month\n")
    print(f"{'photograph':28} {'film':10} {'size':6} {'pixels':>12} {'wall':>7} {'processor':>10} {'peak':>8} "
          f"{'€ per 1,000':>12}")
    with tempfile.TemporaryDirectory() as scratch:
        develop(args.raws[0], "sunday64", "draft", Path(scratch))  # warm the caches, not counted
        for raw in args.raws:
            for film in ("sunday64", "monday400"):
                for size in sizes:
                    wall, cpu, peak, info = develop(raw, film, size, Path(scratch))
                    cost = cost_per_frame(cpu, args.cores, args.eur_month)
                    print(f"{raw.name[:28]:28} {film:10} {size:6} {info['width']:>5} × {info['height']:<5}"
                          f"{wall:6.1f} s {cpu:8.1f} s {peak:6.0f} MB  €{1000 * cost:9.2f}")
    print("\nOne worker develops 3600 / wall seconds an hour; DYEROOM_WORKERS more need that much more memory each.")


if __name__ == "__main__":
    main()
