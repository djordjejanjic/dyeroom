"""Reading a linear DNG ourselves: Apple ProRAW and other DNGs whose data is already RGB.

LibRaw reads most raws, but not a DNG 1.7 file whose data is compressed with JPEG XL, which is
how recent iPhones save ProRAW (it needs Adobe's DNG SDK, which LibRaw is not built with here).
Such a file holds three-channel linear camera RGB in tiles, not a Bayer mosaic, so no
demosaicing is needed: tifffile decodes the tiles (JPEG XL through imagecodecs, or the older
lossless JPEG), and the colour follows the DNG specification, chapter 6: the colour matrices
interpolated for the as-shot white, the camera's neutral mapped to the white of the scene,
and that white adapted to D50 and then to Rec.2020's D65.

Only linear (LinearRaw) DNGs are read here. A Bayer DNG that LibRaw cannot read is still refused.
"""
import logging

import colour
import numpy as np
import tifffile

LINEAR_RAW = 34892
# CCT of the DNG calibration illuminants (EXIF LightSource codes), as Adobe's DNG SDK has them
ILLUMINANT_K = {1: 5500, 2: 4150, 3: 2850, 4: 5500, 9: 5500, 10: 6500, 11: 7500, 12: 6430, 13: 5000, 14: 4150,
                15: 3450, 17: 2856, 18: 4874, 19: 6774, 20: 5503, 21: 6504, 22: 7504, 23: 5003, 24: 3200}
D50 = np.array([0.3457, 0.3585])
D65 = np.array([0.3127, 0.3290])
REC2020 = colour.RGB_COLOURSPACES["ITU-R BT.2020"]


def _xyz(xy):
    return np.array([xy[0] / xy[1], 1.0, (1 - xy[0] - xy[1]) / xy[1]])


def _bradford(xy_from, xy_to):
    return colour.adaptation.matrix_chromatic_adaptation_VonKries(_xyz(xy_from), _xyz(xy_to), transform="Bradford")


def _values(tag):
    """A TIFF (S)RATIONAL array as floats: tifffile gives numerators and denominators in turn."""
    v = np.asarray(tag.value, float).ravel()
    if tag.dtype in (5, 10):  # RATIONAL, SRATIONAL
        v = v[0::2] / v[1::2]
    return v


def _cct(xy):
    return float(colour.temperature.xy_to_CCT(np.clip(xy, 0.2, 0.6), method="Hernandez 1999"))


class _Colour:
    """The DNG colour tags of IFD 0, and the matrices they imply for one white."""

    def __init__(self, tags):
        get = lambda name: _values(tags[name]) if name in tags else None
        self.cms = [m.reshape(3, 3) for m in (get("ColorMatrix1"), get("ColorMatrix2")) if m is not None]
        self.fms = [m.reshape(3, 3) for m in (get("ForwardMatrix1"), get("ForwardMatrix2")) if m is not None]
        self.temps = [ILLUMINANT_K.get(int(tags[name].value), 5000)
                      for name in ("CalibrationIlluminant1", "CalibrationIlluminant2") if name in tags]
        self.neutral = get("AsShotNeutral")
        self.white_xy = get("AsShotWhiteXY")
        if not self.cms:
            raise ValueError("This DNG has no colour matrix")

    def _pick(self, matrices, cct):
        """Interpolate the two calibrations by inverse temperature, as the specification does."""
        if len(matrices) == 1 or len(self.temps) < 2 or self.temps[0] == self.temps[1]:
            return matrices[0]
        (t1, m1), (t2, m2) = sorted(zip(self.temps, matrices[:2]), key=lambda pair: pair[0])
        g = np.clip((1 / cct - 1 / t2) / (1 / t1 - 1 / t2), 0.0, 1.0)
        return g * m1 + (1 - g) * m2

    def white(self):
        """The xy of the light the camera balanced for (from AsShotNeutral, by iteration)."""
        if self.neutral is None:
            return self.white_xy if self.white_xy is not None else D50
        xy = D50
        for _ in range(30):
            xyz = np.linalg.solve(self._pick(self.cms, _cct(xy)), self.neutral)
            new = xyz[:2] / xyz.sum()
            if np.abs(new - xy).max() < 1e-7:
                break
            xy = new
        return xy

    def camera_to_rec2020(self, xy):
        cct = _cct(xy)
        if self.fms and self.neutral is not None:
            to_pcs = self._pick(self.fms, cct) @ np.diag(1.0 / self.neutral)
        else:
            pcs_to_camera = self._pick(self.cms, cct) @ _bradford(D50, xy)
            pcs_to_camera /= (pcs_to_camera @ _xyz(D50)).max()
            to_pcs = np.linalg.inv(pcs_to_camera)
        return REC2020.matrix_XYZ_to_RGB @ _bradford(D50, D65) @ to_pcs


def _orient(img, orientation):
    """Turn an array upright by the TIFF Orientation tag."""
    return {2: lambda a: a[:, ::-1], 3: lambda a: a[::-1, ::-1], 4: lambda a: a[::-1],
            5: lambda a: a.swapaxes(0, 1), 6: lambda a: np.rot90(a, -1), 7: lambda a: np.rot90(a, 1)[::-1],
            8: lambda a: np.rot90(a, 1)}.get(int(orientation), lambda a: a)(img)


def _raw_page(tif):
    """The full-resolution linear raw image: IFD 0 or one of its SubIFDs (NewSubfileType 0)."""
    for page in [tif.pages[0], *(tif.pages[0].pages or [])]:
        if page.photometric == LINEAR_RAW and not page.tags.valueof("NewSubfileType", 0) & 1:
            return page
    return None


def is_linear(path):
    try:
        with tifffile.TiffFile(path) as tif:
            return _raw_page(tif) is not None
    except Exception:
        return False


def read(path, resize):
    """dict(rgb, preview, cct, ...) like capture's other decoders. `resize(img)` sizes the picture."""
    log = logging.getLogger("tifffile")
    level = log.level
    log.setLevel(logging.ERROR)
    try:
        with tifffile.TiffFile(path) as tif:
            ifd0, raw = tif.pages[0], _raw_page(tif)
            if raw is None:
                raise ValueError("Not a linear DNG")
            tags = ifd0.tags
            colours = _Colour({t.name: t for t in tags.values()})
            data = raw.asarray()
            if data.ndim == 2:
                data = data[..., None]
            data = data[..., :3]
            table = raw.tags.valueof("LinearizationTable")
            if table is not None:
                lut = np.asarray(table, np.float32)
                data = lut[np.minimum(data, len(lut) - 1)]
            black = np.broadcast_to(np.asarray(raw.tags.valueof("BlackLevel", 0), np.float32).ravel()[:3], (3,))
            white = np.broadcast_to(np.asarray(raw.tags.valueof("WhiteLevel", 65535), np.float32).ravel()[:3], (3,))
            camera = data.astype(np.float32, copy=False)  # in place from here: a 48 MP file is large
            camera -= black
            camera /= white - black
            np.clip(camera, 0.0, None, out=camera)
            if "DefaultCropOrigin" in raw.tags and "DefaultCropSize" in raw.tags:
                x, y = np.round(_values(raw.tags["DefaultCropOrigin"])).astype(int)
                w, h = np.round(_values(raw.tags["DefaultCropSize"])).astype(int)
                camera = camera[y:y + h, x:x + w]
            orientation = tags.valueof("Orientation", 1)
            camera = _orient(resize(np.ascontiguousarray(camera)), orientation)  # smaller first, then upright
            xy = colours.white()
            rgb = np.clip(np.ascontiguousarray(camera) @ colours.camera_to_rec2020(xy).T.astype(np.float32), 0.0, None)
            preview = None
            if ifd0 is not raw and ifd0.photometric in (2, 6):  # RGB or YCbCr: the camera's own rendering
                try:
                    preview = resize(np.ascontiguousarray(ifd0.asarray()[..., :3]).astype(np.float32) / 255.0)
                    preview = np.ascontiguousarray(_orient(preview, orientation))
                except Exception:
                    preview = None
    finally:
        log.setLevel(level)
    return dict(rgb=rgb.astype(np.float32), preview=preview, cct=_cct(xy), exposure_time=None, flash=None,
                decoder="DNG reader")

