"""The original's metadata, carried over to every exported file unchanged.

Camera, lens, exposure settings, dates, GPS, copyright, captions, keywords and maker notes
(EXIF, IPTC, XMP) are copied from the uploaded original with ExifTool, which reads every
raw format. The original is only read, never written.

Not copied are the tags that describe the original's pixels and would be false for the
developed picture: orientation (the picture is already upright), pixel dimensions,
embedded thumbnails and previews (they show the original), the colour profile and
colour-space tags (the export carries its own profile), and Camera Raw settings (an editor
would apply them again). ExifTool's "unsafe" raw-structure tags are never copied.

When the colours were guessed by AI (colourise.py) one tag is added, in the file's metadata
and not in the picture: IPTC Digital Source Type "compositeWithTrainedAlgorithmicMedia"
(Edited using Generative AI), so that the edit can be recognised by software.

Without ExifTool installed, exports carry no copied metadata.
"""
import logging
import os
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger("dyeroom.metadata")

AI_EDITED = "http://cv.iptc.org/newscodes/digitalsourcetype/compositeWithTrainedAlgorithmicMedia"
NOT_COPIED = [
    "Orientation", "XMP-tiff:Orientation",
    "ExifImageWidth", "ExifImageHeight", "XMP-tiff:ImageWidth", "XMP-tiff:ImageLength",
    "XMP-exif:PixelXDimension", "XMP-exif:PixelYDimension",
    "ThumbnailImage", "PreviewImage", "JpgFromRaw", "OtherImage",
    "ICC_Profile:all", "ColorSpace", "XMP-exif:ColorSpace", "InteropIFD:all",
    "XMP-crs:all", "XMP-crss:all",
]


def available():
    return shutil.which("exiftool") is not None


def carry_over(original, exported, ai_colours=False):
    """Copy the original's metadata into an exported JPEG or TIFF (rewritten in place).
    Returns False, and leaves the export as it was, if that could not be done."""
    if not available() or not Path(original).exists():
        return False
    command = ["exiftool", "-q", "-q", "-overwrite_original", "-tagsFromFile", str(original), "-all:all"]
    command += [f"--{tag}" for tag in NOT_COPIED]
    if ai_colours:
        command.append(f"-XMP-iptcExt:DigitalSourceType={AI_EDITED}")
    # ExifTool reads a stranger's file: it gets what it needs to run, and none of the server's secrets.
    env = {k: v for k, v in os.environ.items()
           if k.upper() in ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR",
                            "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATHEXT")}  # the last five: Windows
    try:
        run = subprocess.run(command + [str(exported)], capture_output=True, text=True, timeout=60, env=env,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("Metadata not copied to %s: %s", exported, exc)
        return False
    if run.returncode != 0:
        log.warning("Metadata not copied to %s: %s", exported, run.stderr.strip()[:300])
        return False
    return True
