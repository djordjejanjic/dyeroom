# Sources, credits and licences

What Dyeroom is built from: the measured data, the papers, and the software and models it
uses, with their licences. This is the one place where the films the stocks are modelled on
are named.

## The films

Sunday 64 is modelled on Kodak Kodachrome 64, Monday 400 on Kodak Tri-X 400. Kodak,
Kodachrome and Tri-X are trademarks of Eastman Kodak Company. Dyeroom is an independent
project and is not affiliated with, sponsored by or endorsed by Kodak.

**Sunday 64.** Kodak publications E-88 and E-55 (2009), *KODACHROME 64 and 200 Films*
([E-88](https://125px.com/docs/film/kodak/e88-2009_06.pdf); the KR 64 figures are the same in
both): layer spectral sensitivities, characteristic curves (Status A), dye spectral
densities, MTF, RMS granularity, reciprocity and filter recommendations, digitised from the
PDF's vector drawings by `tools/digitise_sunday64.py` into `dyeroom/data/sunday64.json`.
Kodak's Q-60K3 Kodachrome IT8 reference data (batch 1999:10), for checking only. The steps of
the Kodachrome process (K-14).

**Monday 400.** Kodak Alaris, *KODAK PROFESSIONAL TRI-X 320 and 400 Films*, publication F-4017
(revised 10-21): spectral sensitivity, characteristic curves in D-76 (large tank), development
times, MTF, granularity, reciprocity and filter factors; curves digitised from the PDF's
vector drawings by `tools/digitise_monday400.py` into `dyeroom/data/monday400.json`, tables
typed from it. Paper grades after ISO 6846. Selenium toning after the makers' published
instructions (Kodak, Ilford), in words only.

## Measurements and papers

- **Status A densitometer response** (ISO 5-3), `dyeroom/data/status_a.json`: digitised from
  E. J. Giorgianni, T. E. Madden and M. A. Kriss, *Digital Color Management* (Wiley, 2009),
  p. 335, as published in the history of [spektrafilm](https://github.com/andreavolpato/spektrafilm)
  by Andrea Volpato, GPL-3.0.
- **Neutral rendering:** the default tone curve and rendering steps of Adobe's DNG SDK
  reference renderer (`dng_render.cpp`), `dyeroom/data/acr3_default_tone_curve.txt`.
- **Spectral reconstruction:** Otsu, Yamamoto and Hachisuka, *Reproducing Spectral
  Reflectances From Tristimulus Colours* (2018); Jakob and Hanika, *A Low-Dimensional
  Function Space for Efficient Spectral Upsampling* (2019).
- **Colour appearance:** CIECAM16 (Li et al., 2017), through colour-science.
- **Film physics:** the quantum ("hit") theory of the latent image (Silberstein); light
  spread in a turbid emulsion (Frieser); the adjacency effect (Nelson); granularity
  (Nutting, Selwyn).
- **Schott KG3** transmission, from the Schott/Newport data sheet.
- **The sample photograph** (`samples/sample-olympus-e-p7.orf`) and the test raws listed in
  `tools/sample_raws.txt`: [raw.pixls.us](https://raw.pixls.us), public domain (CC0). The
  pictures in the site's guides (`dyeroom/web/static/guides`, `og`) are developed from them.
- **The portrait** on the About page (`dyeroom/web/static/about/djordje-janjic.jpg`) is
  Djordje Janjic's own and is not covered by the project's licence.

## Software and models

| What | Used for | Licence |
|---|---|---|
| [DDColor](https://github.com/piddnad/DDColor) by Kang et al. (ICCV 2023), [paper_tiny weights](https://huggingface.co/piddnad/ddcolor_paper_tiny) | colourising black-and-white originals (an AI guess, labelled as such) | Apache-2.0 (`dyeroom/data/LICENSE-ddcolor.txt`) |
| [LibRaw](https://www.libraw.org) through [rawpy](https://github.com/letmaik/rawpy) | reading raw files | LGPL-2.1 or CDDL-1.0; rawpy MIT |
| [libheif](https://github.com/strukturag/libheif) and libde265 through [pi-heif](https://github.com/bigcat88/pillow_heif) | reading HEIC | LGPL-3.0; pi-heif BSD-3-Clause |
| [ExifTool](https://exiftool.org) by Phil Harvey, run as a separate program | carrying the camera's metadata into exports | Perl's Artistic License or GPL |
| [NumPy](https://numpy.org), [SciPy](https://scipy.org), [colour-science](https://www.colour-science.org) | the simulation | BSD-3-Clause |
| [OpenCV](https://opencv.org) | image operations | Apache-2.0 |
| [Pillow](https://python-pillow.org), [tifffile](https://github.com/cgohlke/tifffile), [imagecodecs](https://github.com/cgohlke/imagecodecs) | reading and writing images | MIT-CMU, BSD-3-Clause |
| [ONNX Runtime](https://onnxruntime.ai) | running the colourising model | MIT |
| [FastAPI](https://fastapi.tiangolo.com), [Uvicorn](https://www.uvicorn.org) | the web app | MIT, BSD-3-Clause |

Dyeroom itself: GNU Affero General Public License, version 3 or later ([LICENSE](LICENSE)).
