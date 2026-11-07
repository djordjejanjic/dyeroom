# Dyeroom

*Developed the long way.*

Dyeroom develops your digital photographs, raw files or phone pictures, on simulated film.
Not a preset laid over the picture: the light is exposed onto a modelled emulsion and taken
through the chemistry, step by step.

- **Sunday 64**, a colour slide film: three emulsion layers, a black-and-white first
  developer, re-exposure, three colour developers, bleach and fix, then the slide on a light
  box or a projector, rebuilt for your screen.
- **Monday 400**, a black-and-white negative: developed (pushed if you like), fixed, and
  enlarged onto graded paper, with selenium toning if you want it.

The films are built from their makers' published measurements and checked against them; what
is measured, what is fitted and what is assumed is written down in
[DEVELOPING.md](DEVELOPING.md).

## Try it

**[dyeroom.app](https://dyeroom.app)**: in the browser, nothing to install, free. Your
photographs are deleted when you leave.

## Run it on your computer

A one-command install for macOS, Windows and Linux is on its way. Until then, from source
(Python 3.11 or later; macOS and Linux for now, Windows is being worked on):

```sh
git clone https://github.com/djordjejanjic/dyeroom
cd dyeroom
python3 -m venv .venv
.venv/bin/pip install -e ".[web]"
.venv/bin/dyeroom-web          # then open http://127.0.0.1:8000
```

Or from the command line, without the app:

```sh
.venv/bin/dyeroom PHOTO.RAF                  # a draft, into ./out
.venv/bin/dyeroom PHOTO.RAF --full --tiff    # full resolution, and a 16-bit TIFF
.venv/bin/dyeroom --help
```

With [ExifTool](https://exiftool.org) installed, exports keep the camera's metadata.

## Support it

Dyeroom is free and stays free. If it is worth something to you,
[buy me a coffee](https://buymeacoffee.com/geoyanj).

## Contributing

Issues and pull requests are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md). Contributions
are accepted under the [contributor agreement](CLA.md), which you sign with one comment on
your first pull request.

## Licence

Dyeroom is free software under the GNU Affero General Public License, version 3 or later
([LICENSE](LICENSE)): you may use, study, change and share it, also commercially, as long as
what you share, or run for others as a website, comes with its source under the same licence.

The licence covers the code, not the name: "Dyeroom" and its logo identify this project. A
changed copy you share or host needs a name of its own.

What Dyeroom is built from, and the licences of the data, models and software it uses:
[SOURCES.md](SOURCES.md).
