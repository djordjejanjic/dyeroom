"""Sharpness and clarity of the photograph before it reaches the film.

Phones, and cameras saving JPEGs, sharpen what they save: every edge gets a light rim on its
bright side and a dark one on its dark side. Film never made those halos, and under the
grain they read as a digital photograph. measure() finds them: it follows the brightness
across a few thousand clean edges (a flat field each side of a step) of the original at its
own resolution, as the camera wrote it, and takes the median overshoot, in parts of the
step. An unsharpened raw measures about nothing there; a phone's JPEG a tenth or so. If the
picture is sharpened, it finds the gentlest blend towards a blurred copy that takes the halos
out (the inverse of an unsharp mask to first order): the smallest radius that can do it
with a plausible strength, so detail finer than the sharpening is left alone. Edges are
taken to be straight, so blurring a profile stands in for blurring the picture.

apply() takes that out on the working image, then adds the photographer's own choices:
sharpness (softer, like an older lens, or crisper) and clarity (local contrast, with an
edge-preserving base so large edges get no halos of their own). Both act on brightness only,
in a perceptual encoding, so colours keep their hue.
"""
import cv2
import numpy as np

T = np.arange(-18, 18.01, 0.5, dtype=np.float32)  # along a profile, px across the edge
INNER = np.abs(T) <= 9                            # where halos are looked for
RADII = (0.6, 0.8, 1.0, 1.25, 1.6, 2.0, 2.5, 3.2, 4.0)  # sharpening radii tried, px of the original
STRENGTHS = np.arange(0.0, 0.701, 0.025)          # blends towards the blurred copy tried
SHARPENED = 0.03  # median halo above which the picture counts as sharpened
LEFT = 0.01       # median halo left after taking it out
EDGES = 100       # fewer clean edges than this: no verdict
ENCODE = 1 / 2.2  # brightness as a JPEG roughly stores it, where cameras sharpen
LUMA = np.array([0.2627, 0.6780, 0.0593], dtype=np.float32)  # Rec.2020


def _edges(y, most=20000, seed=0):
    """Strong edge points (thinned to the ridge of the gradient) and their normals."""
    smooth = cv2.GaussianBlur(y, (0, 0), 1.0)
    gx = cv2.Sobel(smooth, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(smooth, cv2.CV_32F, 0, 1, ksize=3)
    m = np.hypot(gx, gy)
    direction = (np.round(np.arctan2(gy, gx) / (np.pi / 4)) % 4).astype(np.int8)
    ridge = np.zeros(m.shape, bool)
    pad = np.pad(m, 1)
    h, w = m.shape
    for d, (dy, dx) in enumerate(((0, 1), (1, 1), (1, 0), (1, -1))):
        ahead = pad[1 + dy:h + 1 + dy, 1 + dx:w + 1 + dx]
        behind = pad[1 - dy:h + 1 - dy, 1 - dx:w + 1 - dx]
        ridge |= (direction == d) & (m >= ahead) & (m >= behind)
    ridge &= m > np.percentile(m, 97)
    edge = int(T[-1]) + 2
    ridge[:edge] = ridge[-edge:] = False
    ridge[:, :edge] = ridge[:, -edge:] = False
    ys, xs = np.nonzero(ridge)
    if len(ys) > most:
        pick = np.random.default_rng(seed).choice(len(ys), most, replace=False)
        ys, xs = ys[pick], xs[pick]
    return xs, ys, gx[ys, xs] / m[ys, xs], gy[ys, xs] / m[ys, xs]


def _profiles(y, xs, ys, nx, ny):
    """Brightness across each edge, dark side first."""
    mx = (xs[:, None] + nx[:, None] * T[None]).astype(np.float32)
    my = (ys[:, None] + ny[:, None] * T[None]).astype(np.float32)
    return cv2.remap(y, mx, my, cv2.INTER_LINEAR)


def _halo(p):
    """Per edge: the mean of overshoot and undershoot as parts of the step, and whether the
    edge is clean (a step between two flat fields, clear of black and white)."""
    t = T[INNER]
    p = p[..., INNER]
    lo, hi = p[..., t <= -5.5], p[..., t >= 5.5]
    low, high = np.median(lo, -1), np.median(hi, -1)
    step = np.maximum(high - low, 1e-6)
    clean = ((high - low > 0.08) & (low > 0.04) & (high < 0.9)
             & (np.abs(lo - low[..., None]).max(-1) < 0.08 * step)
             & (np.abs(hi - high[..., None]).max(-1) < 0.08 * step))
    over = p[..., (t > 0) & (t < 5.5)].max(-1) - high
    under = low - p[..., (t < 0) & (t > -5.5)].min(-1)
    return (over + under) / (2 * step), clean


def _blur_profiles(p, sigma):
    """Profiles of the picture blurred by sigma px (straight edges: a blur along the profile)."""
    kernel = np.exp(-0.5 * (np.arange(-4 * sigma, 4 * sigma + 0.01, 0.5) / sigma) ** 2).astype(np.float32)
    kernel /= kernel.sum()
    return cv2.filter2D(p, -1, kernel[None], borderType=cv2.BORDER_REPLICATE)


def measure(encoded):
    """(strength, radius in px) of the blend that takes the camera's sharpening out of this
    picture, from its brightness as stored (0-1) at full resolution; (0, 0) if it is not sharpened."""
    y = np.ascontiguousarray(encoded, dtype=np.float32)
    edges = _edges(y)
    if len(edges[0]) < EDGES:  # a plain picture: nothing to measure on
        return 0.0, 0.0
    p = _profiles(y, *edges)
    halo, clean = _halo(p)
    if clean.sum() < EDGES or np.median(halo[clean]) < SHARPENED:
        return 0.0, 0.0
    p = p[clean]
    for sigma in RADII:
        q = _blur_profiles(p, sigma)
        tried = p[None] + STRENGTHS[:, None, None] * (q - p)[None]
        left = np.median(_halo(tried)[0], axis=1)
        good = np.nonzero(left <= LEFT)[0]
        if len(good):
            return float(STRENGTHS[good[0]]), sigma
    return float(STRENGTHS[-1]), RADII[-1]


def _guided(image, radius, eps):
    """Edge-preserving smoothing of an image by itself (He, Sun and Tang's guided filter),
    worked out small and brought back up: the base it gives is smooth anyway."""
    h, w = image.shape
    scale = min(1.0, 800 / max(h, w))
    small = cv2.resize(image, (max(1, round(w * scale)), max(1, round(h * scale))), interpolation=cv2.INTER_AREA)
    r = max(1, round(radius * scale))
    box = lambda a: cv2.boxFilter(a, -1, (2 * r + 1, 2 * r + 1))
    mean = box(small)
    var = box(small * small) - mean * mean
    a = var / (var + eps)
    b = mean - a * mean
    a, b = (cv2.resize(box(c), (w, h), interpolation=cv2.INTER_LINEAR) for c in (a, b))
    return a * image + b


def apply(rgb, undo=(0.0, 0.0), sharpness=0, clarity=0):
    """The working picture (linear RGB) with the camera's sharpening taken out (undo: strength
    and radius in px of this picture) and the photographer's sharpness and clarity, -100 to 100.
    Returns the same array when there is nothing to do."""
    strength, radius = undo
    if not (strength and radius) and not sharpness and not clarity:
        return rgb
    long_edge = max(rgb.shape[:2])
    out = np.power(np.maximum(rgb, 0.0), ENCODE).astype(np.float32)
    if strength or sharpness:  # on encoded luma, added to every channel: as cameras sharpen, so undone
        luma = out @ LUMA
        change = np.zeros_like(luma)
        if strength and radius:
            change += strength * (cv2.GaussianBlur(luma, (0, 0), radius) - luma)
        # At least half a pixel: narrower, the blur is all but nothing and the slider does nothing
        # (a picture under 2000 px); drafts and full size are wider than that.
        if sharpness < 0:  # towards a soft lens: a blur of about 1.6 px at 4000 px wide
            soft = luma + change
            change += (-sharpness / 100) * 0.75 * (cv2.GaussianBlur(soft, (0, 0), max(0.5, 0.0004 * long_edge)) - soft)
        elif sharpness > 0:  # an unsharp mask of about 1 px at 4000 px wide
            soft = luma + change
            change += (sharpness / 100) * 1.2 * (soft - cv2.GaussianBlur(soft, (0, 0), max(0.5, 0.00025 * long_edge)))
        out += change[..., None]
        del luma, change
    np.maximum(out, 0.0, out=out)
    np.power(out, 1 / ENCODE, out=out)
    if clarity:  # local contrast, in stops around an edge-preserving base about 2 % of the picture wide
        log = np.log(np.maximum(out @ LUMA, 1e-5))
        detail = log - _guided(log, 0.02 * long_edge, 0.04)
        out *= np.exp(np.clip((clarity / 100) * 0.5 * detail, -1.4, 1.4))[..., None]
        del log, detail
    return out
