# Contributing to Dyeroom

Thank you for helping. Bug reports, photographs that come out wrong, and pull requests are all
welcome.

## Before you start

- **Something that looks wrong:** open an issue with the camera, the file type, the settings
  and what you expected. A raw file that shows it helps most, but only one you took yourself
  or one in the public domain.
- **A bigger change** (a new stock, a change to the film model): open an issue first, so we can
  agree on the approach before you spend the time.

## Setting up

```sh
git clone https://github.com/djordjejanjic/dyeroom
cd dyeroom
python3 -m venv .venv
.venv/bin/pip install -e ".[test]"
.venv/bin/python -m unittest discover -s tests
.venv/bin/dyeroom-web        # the app at http://127.0.0.1:8000
```

How everything works, stage by stage: [DEVELOPING.md](DEVELOPING.md).

## Pull requests

- Keep each pull request to one change, with tests where it changes behaviour. The tests must
  pass on macOS and Linux (and on Windows once it is supported).
- Write code that reads like the code around it: the same naming, the same density of comments,
  comments that say why rather than what. British spelling (colour, grey).
- **A change to the film model** should say what it does to the picture, with numbers: the
  tests that compare the films to their data sheets, and before and after on a few test raws
  (`tools/sample_raws.txt` lists public-domain ones).
- **Names:** the stocks are Sunday 64 and Monday 400. The real films they are modelled on, their
  makers, developers and processes are named only in [SOURCES.md](SOURCES.md), in code, data,
  comments and documentation alike.
- **Photographs:** commit only test files that are yours to give or in the public domain, and
  say which.

## The contributor agreement

Before your first pull request is merged, you sign the [contributor agreement](CLA.md): you keep
the copyright in your work and give the maintainer a broad licence to it, and the maintainer
promises that every version with your work in it stays available as open source. A bot asks you
on the pull request; you sign by replying with one sentence. It covers all your later
contributions too.

## Licence

By contributing, your work is also published under the project's licence, the GNU Affero
General Public License, version 3 or later ([LICENSE](LICENSE)).
