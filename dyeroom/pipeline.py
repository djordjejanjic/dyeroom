"""From a photograph to a Sunday 64 slide or a Monday 400 print (mono.py), as seen on your
screen."""
import time
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np

from . import capture, colourise as colouriser, detail, exposure, film as film_model, mono, process as reversal, \
    spectra, viewing as views
from .process import Process


FILMS = {"sunday64": "Sunday 64", "monday400": mono.NAME}


class MonochromeOriginal(ValueError):
    """A black-and-white file sent to a colour film."""
    code = "monochrome"


@dataclass
class Shoot:
    film: str = "sunday64"        # sunday64 (colour slide) or monday400 (black-and-white print)
    exposure: str = "camera"      # camera: as bright as the camera's rendering; auto: from the scene
    ev: float = 0.0               # exposure compensation, in stops, on top of that
    light: str = "native"         # native: the real scene light; balanced: as white-balanced
    filter: str = "auto"          # conversion filter on the lens with light=native; auto picks one
    view: str = "lightbox"        # lightbox or projector
    display: str = "p3"           # p3 or srgb
    process: Process = field(default_factory=Process)
    rating: int = 400             # Monday 400: exposure index, 400 to 3200 (push development)
    grade: int = 3                # Monday 400: paper contrast grade, 1 to 5
    toning: str = "none"          # Monday 400: selenium toner, none, light (1+20) or strong (1+5)
    colourise: bool = False       # Sunday 64: give a black-and-white original guessed colours first
    bw_filter: str = "none"       # Monday 400: contrast filter on the lens (8, 15, 25, 11, 58)
    format: str = "35mm"          # film format (capture.FORMATS): bigger frames, finer grain and more detail
    sharpness: int = 0            # -100 (soft) to 100 (crisp), after the camera's own sharpening is taken out
    clarity: int = 0              # -100 to 100: local contrast of the scene the film sees


def taking_light(cap, shoot):
    """Spectrum of the light that reaches the film."""
    if shoot.light == "native" and cap.scene_cct:
        light = spectra.scene_light(cap.scene_cct)
        if shoot.filter != "auto":
            name = shoot.filter
        elif cap.flash:
            name = "none"  # electronic flash is daylight-balanced, like the film: room light goes warm
        else:
            name = spectra.pick_filter(cap.scene_cct)
    else:
        light = spectra.daylight(5500)  # the light the film is balanced for
        name = "none"
    cap.notes["filter"] = name
    light = light * spectra.conversion_filter(spectra.FILTERS[name]) * spectra.lens_transmission()
    return spectra.normalise(light)  # metered through the lens: same luminance either way


STAGES = ["Reading the photograph", "Exposing the film", "First developer",
          "Reversal and colour developers", "Viewing the slide"]


def stages(film):
    return mono.STAGES if film == "monday400" else STAGES


def develop(path, shoot, long_edge=None, log=print, progress=None, on_read=None):
    """Develop one photograph. Returns linear display RGB, the capture, and a summary.

    progress(stage_index, stage_name) is called as each stage of the process starts;
    on_read(capture) as soon as the photograph has been read.
    """
    names = stages(shoot.film)

    def stage(i):
        if progress:
            progress(i, names[i])

    t0 = time.time()
    stage(0)
    cap = capture.read(path, long_edge)
    cap.um_per_px = capture.um_per_px(cap.rgb.shape, shoot.format)
    if on_read:
        on_read(cap)
    mono_film = shoot.film == "monday400"
    on_film = cap
    if not mono_film and cap.monochrome:
        if not (shoot.colourise and colouriser.available()):
            raise MonochromeOriginal("This photograph is black and white, and Sunday 64 is a colour film: it would "
                                     f"only make a grey slide. Develop it on {mono.NAME}"
                                     + (", or colourise it first." if colouriser.available() else "."))
        on_film = colouriser.apply(cap)  # the original stays as it was, for the comparison
        cap.notes["colours"] = on_film.notes["colours"]
    sharper = detail.apply(on_film.rgb, on_film.sharpened, shoot.sharpness, shoot.clarity)
    if sharper is not on_film.rgb:
        on_film = replace(on_film, rgb=sharper)
    del sharper
    rgb = mono.render(on_film, shoot, stage) if mono_film else render(on_film, shoot, stage)
    info = dict(width=int(rgb.shape[1]), height=int(rgb.shape[0]), film=shoot.film, format=shoot.format,
                scene_light_k=round(cap.scene_cct) if cap.scene_cct else None,
                filter=cap.notes.get("filter"), view=None if mono_film else shoot.view,
                rating=shoot.rating if mono_film else None, grade=shoot.grade if mono_film else None,
                toning=shoot.toning if mono_film else None,
                exposure_time_s=cap.exposure_time, seconds=round(time.time() - t0, 1),
                **{k: v for k, v in cap.notes.items() if k != "filter"})
    cct = f"{cap.scene_cct:.0f} K" if cap.scene_cct else "n/a"
    extras = ", ".join(f"{k} {v}" for k, v in cap.notes.items() if k not in ("filter",))
    log(f"  {Path(path).name}: {rgb.shape[1]}x{rgb.shape[0]}, scene light {cct}, "
        f"filter {cap.notes.get('filter')}, {extras}, {info['seconds']:.1f} s")
    return rgb, cap, info


def render(cap, shoot, stage=lambda i: None):
    """The film and the viewing, from an already read photograph. Linear display RGB."""
    film = film_model.load()
    view = views.VIEWINGS[shoot.view]
    space = spectra.P3 if shoot.display == "p3" else spectra.SRGB

    stage(1)
    stops = exposure.choose(cap, shoot.exposure, shoot.view, shoot.process.first_developer)
    cap.notes["exposure"] = shoot.exposure
    cap.notes["film exposure ev"] = round(stops + shoot.ev, 2)  # against the camera's metering
    log_h = reversal.layer_exposure(cap.rgb * 2.0 ** (stops + shoot.ev), film, taking_light(cap, shoot),
                                    cap.scene_cct if shoot.light == "native" else None)
    log_h += reversal.metered_grey_log_h(film)  # metered grey -> the film's exposure at ISO 64
    log_h += reversal.grey_balance(film)  # emulsion batch balanced for 5000 K viewing
    # A flash-lit subject gets a burst of about 1/1000 s whatever the shutter time.
    log_h = reversal.reciprocity(log_h, None if cap.flash else cap.exposure_time)
    log_h = reversal.irradiation(log_h, cap.um_per_px)
    stage(2)
    developed = reversal.first_developer(log_h, film, shoot.process, cap.um_per_px)
    stage(3)
    grains = reversal.grain_count_per_um2(film, view.light)
    dyes = reversal.reversal_and_dyes(developed, film, shoot.process, cap.um_per_px, grains)
    stage(4)
    xyz, white = views.slide_to_xyz(dyes, film, view, exposure.eye_gain(shoot.view))
    return views.to_display(xyz, white, view, space).astype(np.float32)
