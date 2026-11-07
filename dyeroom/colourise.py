"""Colour for a black-and-white original on a colour film: an AI guess, not a measurement.

A black-and-white photograph holds no colour, so any colour it gets is invented. DDColor
(Kang et al., ICCV 2023; code and weights Apache-2.0), its tiny model run by ONNX Runtime on
the CPU, looks at the picture at 512 x 512 and predicts the CIELab a* and b* of every pixel
from what it recognises: sky, skin, foliage. Those colours are enlarged to full size and
laid under the photograph's own luminance, so tones and detail stay the original's and only
the colours are new. The result then goes onto Sunday 64 like any colour photograph.

The model file is made once with tools/export_ddcolor.py. It is looked for at
DYEROOM_COLOURISE_MODEL, by default data/cache/ddcolor_paper_tiny.onnx; without it (or
without onnxruntime) colourising is simply not offered.
"""
import os
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from . import neutral, spectra
from .capture import _luminance

MODEL = Path(os.environ.get("DYEROOM_COLOURISE_MODEL",
                            Path(__file__).parent / "data" / "cache" / "ddcolor_paper_tiny.onnx"))
SIZE = 512  # the model's input, width and height
NAME = "DDColor"


def runtime():
    """Whether ONNX Runtime, which runs the model, is installed."""
    try:
        import onnxruntime  # noqa: F401
    except ImportError:
        return False
    return True


def available():
    return MODEL.is_file() and runtime()


@lru_cache(maxsize=1)
def _session():
    import onnxruntime
    return onnxruntime.InferenceSession(str(MODEL), providers=["CPUExecutionProvider"])


def predict_ab(lightness):
    """CIELab a*, b* (h, w, 2) the model guesses for a picture of this L* (h, w), at 512 x 512."""
    small = cv2.resize(lightness.astype(np.float32), (SIZE, SIZE), interpolation=cv2.INTER_AREA)
    grey = np.dstack([small, np.zeros_like(small), np.zeros_like(small)])
    rgb = cv2.cvtColor(grey, cv2.COLOR_Lab2RGB)  # what the model was trained on: grey sRGB, 0-1
    ab = _session().run(None, {"input": rgb.transpose(2, 0, 1)[None].astype(np.float32)})[0][0]
    return ab.transpose(1, 2, 0)


def _displayed(cap):
    """The original as it is seen: the file itself, or a neutral rendering of the raw (sRGB, 0-1)."""
    h, w = cap.rgb.shape[:2]
    if cap.raw_scale is None and cap.preview is not None:
        return cv2.resize(cap.preview.astype(np.float32), (w, h), interpolation=cv2.INTER_AREA)
    return neutral.preview(cap, max(h, w), spectra.SRGB, 0.0).astype(np.float32)


def apply(cap):
    """A copy of the capture with guessed colour, scene luminance unchanged."""
    h, w = cap.rgb.shape[:2]
    shown = _displayed(cap)
    lightness = cv2.cvtColor(np.clip(shown, 0, 1), cv2.COLOR_RGB2Lab)[..., 0]
    ab = cv2.resize(predict_ab(lightness), (w, h), interpolation=cv2.INTER_LINEAR)
    coloured = cv2.cvtColor(np.dstack([lightness, ab]).astype(np.float32), cv2.COLOR_Lab2RGB)
    linear = spectra.SRGB.cctf_decoding(np.clip(coloured, 0, 1))
    rec2020 = linear @ (spectra.REC2020.matrix_XYZ_to_RGB @ spectra.SRGB.matrix_RGB_to_XYZ).T
    y = _luminance(rec2020.astype(np.float32))
    ratio = np.where(y[..., None] > 1e-4, rec2020 / np.maximum(y, 1e-4)[..., None], 1.0)
    rgb = (ratio * _luminance(cap.rgb)[..., None]).astype(np.float32)
    return replace(cap, rgb=rgb, monochrome=False, notes={**cap.notes, "colours": f"guessed by {NAME}"})
