"""python -m dyeroom PHOTO [PHOTO ...] [options]"""
import argparse
from pathlib import Path

from . import capture, local, metadata, mono, output, pipeline, spectra
from .viewing import VIEWINGS
from .capture import RAW_SUFFIXES
from .process import Process


def collect(inputs):
    """Files to develop; in folders a raw wins over the camera JPEG of the same frame."""
    files = []
    for item in map(Path, inputs):
        if item.is_dir():
            found = sorted(p for p in item.iterdir()
                           if p.suffix.lower() in RAW_SUFFIXES | {".jpg", ".jpeg", ".tif", ".tiff", ".png"})
            raws = {p.stem for p in found if p.suffix.lower() in RAW_SUFFIXES}
            files += [p for p in found if p.suffix.lower() in RAW_SUFFIXES or p.stem not in raws]
        else:
            files.append(item)
    return files


def main():
    import sys
    if len(sys.argv) < 2 or sys.argv[1] in local.COMMANDS:  # python -m dyeroom: the lab, as the command
        return local.main(sys.argv[1:])
    ap = argparse.ArgumentParser(prog="dyeroom", description="Develop photographs as Sunday 64 slides "
                                                           "or Monday 400 black-and-white prints.",
                                 epilog="With no photographs, dyeroom opens the lab on this computer in a "
                                        "window; also: dyeroom stop, dyeroom shortcut, dyeroom colourise-model.")
    ap.add_argument("inputs", nargs="+", help="raw files, images, or folders")
    ap.add_argument("--film", choices=list(pipeline.FILMS), default="sunday64",
                    help="sunday64: colour slide; monday400: black-and-white negative, printed")
    ap.add_argument("--rating", type=int, choices=list(mono.RATINGS), default=400,
                    help="Monday 400: exposure index; 1600 and 3200 are push-developed")
    ap.add_argument("--grade", type=int, choices=list(mono.GRADES), default=3, help="Monday 400: paper grade")
    ap.add_argument("--toning", choices=list(mono.TONING), default="none",
                    help="Monday 400: selenium toner, light (1+20: deeper blacks) or strong (1+5: purple-brown)")
    ap.add_argument("--bw-filter", choices=list(mono.FILTERS), default="none",
                    help="Monday 400: 8 yellow, 15 deep yellow, 25 red, 11 yellow-green, 58 green")
    ap.add_argument("--colourise", action="store_true",
                    help="Sunday 64: give black-and-white originals colours guessed by DDColor first")
    ap.add_argument("--format", choices=list(capture.FORMATS), default="35mm",
                    help="film format the picture is laid onto: 35mm, 645, 6x6 or 6x7 (finer grain on bigger frames)")
    ap.add_argument("-o", "--out", default="out", help="output folder (default: ./out)")
    ap.add_argument("--size", type=int, default=2400, help="long edge in pixels for drafts (default 2400)")
    ap.add_argument("--full", action="store_true", help="full resolution")
    ap.add_argument("--exposure", choices=["camera", "auto"], default="camera",
                    help="camera: as bright as the camera's own rendering; auto: placed from the "
                         "scene itself, correcting under- and overexposed files")
    ap.add_argument("--ev", type=float, default=0.0, help="exposure compensation in stops, on top")
    ap.add_argument("--light", choices=["native", "balanced"], default="native",
                    help="native: daylight film sees the real scene light (tungsten turns amber)")
    ap.add_argument("--filter", choices=["auto", *spectra.FILTERS], default="auto",
                    help="colour-conversion filter with --light native (auto: the closest one)")
    ap.add_argument("--view", choices=list(VIEWINGS), default="lightbox",
                    help="how the slide is seen: 5000 K light box, or projected in a dark room")
    ap.add_argument("--display", choices=["p3", "srgb"], default="p3")
    ap.add_argument("--first-developer", type=float, default=1.0,
                    help="first developer time relative to the standard time (push/pull)")
    ap.add_argument("--no-grain", action="store_true")
    ap.add_argument("--tiff", action="store_true", help="also write a 16-bit TIFF")
    args = ap.parse_args()

    shoot = pipeline.Shoot(film=args.film, rating=args.rating, grade=args.grade, bw_filter=args.bw_filter,
                           toning=args.toning, colourise=args.colourise, format=args.format,
                           exposure=args.exposure, ev=args.ev, light=args.light, filter=args.filter,
                           view=args.view, display=args.display,
                           process=Process(first_developer=args.first_developer, grain=not args.no_grain))
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for path in collect(args.inputs):
        rgb, _, info = pipeline.develop(path, shoot, None if args.full else args.size)
        out = out_dir / f"{path.stem}_{args.film}"
        output.save(rgb, out, args.display, args.tiff)
        for done in (out.with_suffix(".jpg"), out.with_suffix(".tif")):  # the original's metadata, unchanged
            if done.exists():
                metadata.carry_over(path, done, ai_colours="colours" in info)


if __name__ == "__main__":
    main()
