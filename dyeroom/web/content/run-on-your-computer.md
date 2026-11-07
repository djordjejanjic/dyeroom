---
slug: /run-on-your-computer
title: "Run Dyeroom on your own computer: macOS, Windows and Linux"
description: "Dyeroom is free and open source. Install it with one line and it develops with your computer's full power, and your photographs never leave it."
h1: "Run it on your own computer"
subline: "Dyeroom is free and open source. Installed with one line, it develops with all of your computer's power, and your photographs never leave it."
updated: 2026-11-08
author: Djordje Janjic
breadcrumb: Home > Run it on your computer
image: /static/og/home.jpg
image_alt: "A Sunday 64 slide developed by Dyeroom: yellow flowers and tall grass against a hazy blue sky"
---

The browser lab at dyeroom.app shares one small server with everyone who is using it. On your own computer, Dyeroom is the same lab, with the same films and settings, in its own window, and all of the machine is yours:

- **Faster.** It develops with all of your computer's processor and memory, without waiting in line.
- **Private.** Your photographs are never uploaded. The lab runs on your computer, and the one thing it sends out is a question to PyPI, once a day, whether a newer version is there.
- **No limits.** Full size, whole rolls, as many photographs as your computer can hold.

## macOS and Linux

Open Terminal and paste this line:

```
curl -LsSf https://dyeroom.app/install.sh | sh
```

## Windows

Open PowerShell from the Start menu and paste this line:

```
powershell -ExecutionPolicy ByPass -c "irm https://dyeroom.app/install.ps1 | iex"
```

Then open Dyeroom from your applications or the Start menu, or type `dyeroom` in a new terminal window. The first start after installing takes a little longer.

## What the installer does

It installs uv, Astral's installer for Python programs, which brings its own Python, then Dyeroom itself, and adds Dyeroom to your applications or the Start menu. Nothing needs administrator rights. Both installers are short, and you can read them before you run them: [install.sh](https://github.com/djordjejanjic/dyeroom/blob/main/dyeroom/web/install.sh) and [install.ps1](https://github.com/djordjejanjic/dyeroom/blob/main/dyeroom/web/install.ps1).

To update, run the same line again, or `uv tool upgrade dyeroom`; Dyeroom says when a newer version is out. If you already use Python, `pipx install dyeroom` works too. The [README](https://github.com/djordjejanjic/dyeroom#run-it-on-your-computer) has the rest, including how to remove it.

## Free and open source

Dyeroom is free software under the GNU Affero General Public License: the code, how the film model works, stage by stage, and how to contribute are on [GitHub](https://github.com/djordjejanjic/dyeroom). If it is worth something to you, [a coffee](https://buymeacoffee.com/geoyanj) keeps it public and keeps new versions coming.
