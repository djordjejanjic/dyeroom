---
slug: /about
title: "About Dyeroom and its maker, Djordje Janjic"
description: "Dyeroom is made by Djordje Janjic, a software engineer and photographer from Belgrade. Why it exists, how it is made, and why it is free."
h1: "About Dyeroom"
subline: "Made by Djordje Janjic, in Belgrade."
updated: 2026-11-03
author: Djordje Janjic
breadcrumb: Home > About
same_as:
  - https://djordjejanjic.rs
  - https://www.instagram.com/_djordjejanjic/
image: /static/og/about.jpg
image_alt: "Djordje Janjic"
---

[figure portrait]
/static/about/djordje-janjic.jpg | Djordje Janjic, smiling, sitting beside an arcade machine.
[/figure]

I'm Djordje Janjic. I'm a software engineer and a photographer, and I am from Belgrade. My work is at [djordjejanjic.rs](https://djordjejanjic.rs), and my photographs are on [Instagram](https://www.instagram.com/_djordjejanjic/).

## Why I built it

I wanted a great film simulation for my digital photographs. No simulation can copy film one to one, and Dyeroom does not either. But to me a picture is far cooler, and looks truer to analog, when it has gone through a simulation of the physical process itself: exposed on the film, developed step by step, and seen on a light box or printed on paper, instead of shaped by a preset afterwards.

It is a model, and I say so wherever it matters. [How Dyeroom works](/how-it-works) lists what is measured, what is modelled and what is assumed, and the pages on each film end with what the model cannot do. I would rather you trust it for the right reasons than believe it is more than it is.

## How it is made

Dyeroom is written in Python. A raw file is read, turned into light that would have reached each of the film's three layers, and carried through the chemistry in order: latent image, first developer, re-exposure, colour developers, bleach and fix, and the slide on a light box or projector. Monday 400 does the same for a black-and-white negative and then prints it on paper. The films are built from the film makers' published technical data. Where that data stops, I made assumptions, and the how-it-works page says which.

I did not start from nothing. Dyeroom uses published work on spectral reconstruction and colour appearance, an open-source model for colourising black-and-white photographs, and the public-domain raw files collected at raw.pixls.us. Another open-source film simulation, [spektrafilm](https://github.com/andreavolpato/spektrafilm) by Andrea Volpato, is a related project, and Dyeroom credits its published history for the densitometer response it uses. The credits are in [How Dyeroom works](/how-it-works#standing-on-other-peoples-work).

Dyeroom is free software too, under the GNU Affero General Public License. The source code is on [GitHub](https://github.com/djordjejanjic/dyeroom), with the whole model written down, and you can run Dyeroom on your own computer with one command: `curl -LsSf https://dyeroom.app/install.sh | sh` on a Mac or Linux, `powershell -ExecutionPolicy ByPass -c "irm https://dyeroom.app/install.ps1 | iex"` on Windows.

Dyeroom is an independent project. It is not affiliated with, sponsored by or endorsed by any film maker. The footer names the films the two stocks are modelled on and says whose trademarks those are.

## Your photographs

Dyeroom does not keep your photographs. They are held only while you work on them, and deleted when you close the page, after a short time without activity, or at the latest a few hours after upload. There is no gallery and no account, and the site sets no cookies. The [privacy notice](/privacy) has the details.

## It is free

Everything in Dyeroom is free, with every film, setting and kind of export open to everyone and nothing to sign up for. If you find it useful, you can [buy me a coffee](https://buymeacoffee.com/geoyanj) to help keep it running. A donation buys nothing extra. Everyone gets the same.

## My other free projects

- **[The Human Cell](https://cellulahumana.com).** A living 3D model of a human cell. Fly into 19 parts, from the nucleus to the DNA, each explained and sourced, in seven languages.
- **[Towline](https://towline.app).** Formula 1 replays and live timing, with new ways to read a race.

## Get in touch

If you find something wrong in a picture or a page, or you want to talk about how it works, write to me: [hello@dyeroom.app](mailto:hello@dyeroom.app). You can also find me on [Instagram](https://www.instagram.com/_djordjejanjic/).
