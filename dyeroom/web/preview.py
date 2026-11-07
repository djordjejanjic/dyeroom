"""A look at a photograph before it is developed:  python -m dyeroom.web.preview SOURCE OUT_DIR

Writes OUT_DIR/thumb.jpg for the frames list, then OUT_DIR/preview.jpg for the viewer: the
image file itself made small, or for a raw the camera's own JPEG inside it (a quick decode of
the raw when there is none big enough, ExifTool's copy when LibRaw cannot open the file),
turned upright. Nothing about the development depends on it. Run in its own process, as the
developer is: a file made to crash a decoder takes down only this.
"""
import io
import os
import subprocess
import sys
from pathlib import Path

import pi_heif
import rawpy
from PIL import Image, ImageOps

EDGE = 2048        # the viewer, sharp on a high-density screen
THUMB_EDGE = 360   # the frames list
SMALLEST = 1000    # an embedded JPEG smaller than this is not worth showing large
IMAGES = {".jpg", ".jpeg", ".heic", ".heif", ".tif", ".tiff", ".png"}
Image.MAX_IMAGE_PIXELS = 80_000_000  # as capture.py: larger pictures are refused
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # Windows: no console flashing up
pi_heif.register_heif_opener()
# LibRaw's flip: how the camera was held, as the turn the picture needs
TURNS = {3: Image.Transpose.ROTATE_180, 5: Image.Transpose.ROTATE_90, 6: Image.Transpose.ROTATE_270}


def _jpeg(data):
    """An embedded JPEG, decoded at about the size needed, upright if it says how."""
    img = Image.open(io.BytesIO(data))
    img.draft("RGB", (EDGE, EDGE))
    turned = img.getexif().get(0x0112, 1) not in (None, 1)
    return ImageOps.exif_transpose(img), turned


def _from_raw(path):
    with rawpy.imread(str(path)) as raw:
        turn = TURNS.get(raw.sizes.flip)
        img, turned = None, False
        try:
            thumb = raw.extract_thumb()
        except (rawpy.LibRawError, ValueError):
            thumb = None
        if thumb is not None and thumb.format == rawpy.ThumbFormat.JPEG:
            img, turned = _jpeg(thumb.data)
        elif thumb is not None and thumb.format == rawpy.ThumbFormat.BITMAP:
            img = Image.fromarray(thumb.data)
        if img is not None and max(img.size) >= SMALLEST:
            return img if turned or turn is None else img.transpose(turn)
        return Image.fromarray(raw.postprocess(half_size=True, use_camera_wb=True, output_bps=8))  # upright


def _from_exiftool(path):
    """The largest JPEG ExifTool finds in a raw LibRaw cannot open (a very new camera)."""
    found = []
    for tag in ("JpgFromRaw", "PreviewImage", "OtherImage"):
        run = subprocess.run(["exiftool", "-b", f"-{tag}", str(path)], capture_output=True, timeout=30,
                             creationflags=NO_WINDOW)
        if run.returncode == 0 and run.stdout[:2] == b"\xff\xd8":
            found.append(run.stdout)
    if not found:
        return None
    img, turned = _jpeg(max(found, key=len))
    if not turned:
        run = subprocess.run(["exiftool", "-n", "-s3", "-Orientation", str(path)], capture_output=True, timeout=30,
                             creationflags=NO_WINDOW)
        img = ImageOps.exif_transpose(_oriented(img, run.stdout.strip()))
    return img


def _oriented(img, orientation):
    """img carrying an EXIF orientation, for exif_transpose to apply."""
    try:
        value = int(orientation)
    except ValueError:
        return img
    exif = img.getexif()
    exif[0x0112] = value
    img.info["exif"] = exif.tobytes()
    return img


def read(path):
    """The photograph as a Pillow image, upright, with its colour profile in info; None if none can be had."""
    path = Path(path)
    if path.suffix.lower() in IMAGES:
        img = Image.open(path)
        img.draft("RGB", (EDGE, EDGE))
        return ImageOps.exif_transpose(img)
    try:
        return _from_raw(path)
    except (rawpy.LibRawError, OSError, ValueError):
        return _from_exiftool(path)


def write(img, out):
    """thumb.jpg, then preview.jpg (its presence says both are there), each written whole."""
    icc = img.info.get("icc_profile")
    if img.mode.startswith("I"):  # 16-bit greys (a scan, say): to 8 bits, not clipped to white
        img = img.convert("I").point(lambda v: v * (1 / 256)).convert("L")
    big = img.convert("RGB")
    big.thumbnail((EDGE, EDGE), Image.Resampling.LANCZOS, reducing_gap=3.0)
    small = big.copy()
    small.thumbnail((THUMB_EDGE, THUMB_EDGE), Image.Resampling.LANCZOS)
    for picture, name, quality in ((small, "thumb.jpg", 80), (big, "preview.jpg", 85)):
        tmp = out / f"{name}.tmp"
        picture.save(tmp, "JPEG", quality=quality, icc_profile=icc)
        os.replace(tmp, out / name)


def main():
    source, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    img = read(source)
    if img is not None:
        write(img, out)


if __name__ == "__main__":
    main()
