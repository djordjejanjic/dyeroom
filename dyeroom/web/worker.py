"""Develop one web job in its own process:  python -m dyeroom.web.worker JOB_DIR

Running each job in a fresh process bounds memory (a full-size raw can take several GB),
frees it afterwards, and keeps a crashing decoder from taking the server down.
"""
import json
import os
import resource
import sys
import traceback
from pathlib import Path


import numpy as np

from .. import metadata, neutral, output, pipeline, spectra
from ..process import Process

VIEW_EDGE = 2400   # what the browser shows
THUMB_EDGE = 360
EARLY_EDGE = 1200  # the raw, neutral, shown while it develops


def write_status(job_dir, **status):
    tmp = job_dir / "status.json.tmp"
    tmp.write_text(json.dumps(status))
    os.replace(tmp, job_dir / "status.json")


def usage():
    """Processor seconds this development used (with the tools it ran) and its peak memory."""
    own, tools = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = own.ru_utime + own.ru_stime + tools.ru_utime + tools.ru_stime
    per_mb = 1024 * 1024 if sys.platform == "darwin" else 1024  # ru_maxrss: bytes on macOS, KiB on Linux
    return {"cpu": round(cpu, 2), "peak_mb": round(own.ru_maxrss / per_mb)}


def _jpeg(encoded, path, display, edge):
    path.write_bytes(output.jpeg_bytes(encoded, display, quality=92, long_edge=edge))


def main(job_dir):
    job_dir = Path(job_dir)
    params = json.loads((job_dir / "params.json").read_text())
    total = len(pipeline.stages(params.get("film", "sunday64"))) + 1

    def progress(i, name):
        write_status(job_dir, state="running", stage=i + 1, stages=total, stage_name=name,
                     early=(job_dir / "early.jpg").exists())

    def on_read(cap):
        early = neutral.preview(cap, EARLY_EDGE, space)
        _jpeg(early, job_dir / "early.jpg", display, EARLY_EDGE)

    try:
        display = params["display"]
        space = spectra.P3 if display == "p3" else spectra.SRGB
        shoot = pipeline.Shoot(film=params.get("film", "sunday64"), exposure=params.get("exposure", "camera"),
                               ev=params["ev"], light=params["light"], filter=params["filter"],
                               view=params["view"], display=params["display"],
                               process=Process(grain=params["grain"]), rating=params.get("rating", 400),
                               grade=params.get("grade", 3), bw_filter=params.get("bw_filter", "none"),
                               toning=params.get("toning", "none"), colourise=params.get("colourise", False),
                               format=params.get("format", "35mm"), sharpness=params.get("sharpness", 0),
                               clarity=params.get("clarity", 0))
        rgb, cap, info = pipeline.develop(Path(params["source"]), shoot, params["long_edge"],
                                          log=lambda *_: None, progress=progress, on_read=on_read)
        write_status(job_dir, state="running", stage=total, stages=total, stage_name="Finishing the files")
        encoded = output.encode(rgb)
        np.save(job_dir / "slide16.npy", np.round(encoded * 65535).astype(np.uint16))  # for adjusted downloads
        (job_dir / "slide.jpg").write_bytes(output.jpeg_bytes(encoded, display))
        if params["tiff"]:
            output.save(rgb, job_dir / "slide", display, tiff=True)
        for done in (job_dir / "slide.jpg", job_dir / "slide.tif"):  # the original's metadata, unchanged
            if done.exists():
                metadata.carry_over(params["source"], done, ai_colours="colours" in info)
        _jpeg(encoded, job_dir / "view.jpg", display, VIEW_EDGE)
        _jpeg(encoded, job_dir / "thumb.jpg", display, THUMB_EDGE)
        _jpeg(neutral.preview(cap, VIEW_EDGE, space), job_dir / "before.jpg", display, VIEW_EDGE)
        write_status(job_dir, state="done", info=info, usage=usage())
    except Exception as exc:  # report, never crash silently
        (job_dir / "error.log").write_text(traceback.format_exc())
        message = str(exc) if isinstance(exc, ValueError) else f"{type(exc).__name__}: {exc}"
        write_status(job_dir, state="failed", error=message[:300], code=getattr(exc, "code", None), usage=usage())
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1])
