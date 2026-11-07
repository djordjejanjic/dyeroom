---
slug: /guides/film-presets-vs-film-simulation
title: "Film presets vs film simulation: what is the difference?"
description: "A preset moves sliders; a simulation models the film and its chemistry. What each can and cannot do for the film look, and when a preset is better."
h1: "Film presets vs film simulation"
subline: "What the words mean, what each approach can do, and when to use which."
updated: 2026-11-03
author: Djordje Janjic
breadcrumb: Home > Guides > Film presets vs film simulation
image: /static/og/film-presets-vs-film-simulation.jpg
image_alt: "Watering cans by a garden bench, developed on Sunday 64"
---

[figure]
/static/guides/bench-raw.jpg | Watering cans, a clay pot and plastic crates by a wooden garden bench: the neutral raw. | The raw
/static/guides/bench-sunday-64.jpg | The same file developed on Sunday 64. | Sunday 64
Nikon Z fc. Raw file from raw.pixls.us, released CC0.
[/figure]

The words around film look are used loosely, even by the people who sell the tools. A preset, a LUT, a film simulation and an emulation all promise something film-like, and they are different things. This page sorts them out, says what each can do well, says where each breaks, and says when you should not use Dyeroom at all.

I make Dyeroom, which is on the simulation side of this page. I have tried to be fair to the other side, because it is the better tool in several situations.

## The vocabulary

| Term | What it usually means |
|---|---|
| **Preset** | A saved set of editor settings: slider positions for tone, colour, grain and so on. Applied to a picture that already exists. |
| **LUT** | A lookup table: a fixed mapping from each input colour to an output colour. Applied to a picture that already exists, often in video and in some photo editors. |
| **In-camera film simulation** | A picture style in a camera's JPEG engine that renders the sensor data with a film-like character. |
| **Emulation** | A loose word for anything that imitates the appearance of a film. Often a preset or a LUT with a more serious name. |
| **Simulation** | A model of how the film responds to light and is processed, run on the scene data, so the output depends on the input. |

The last two are often swapped. Some products called emulations are real models, and some called simulations are presets. Judge the tool by what it does, not by the word.

## What a preset does well

It is fast and cheap. It fits into a catalogue workflow, so you can apply it to a hundred frames, tweak one slider, and move on. It gives a consistent look across a set, because it is a fixed transformation. It stays editable: you can pull the grain back or lift the shadows after. And a careful preset maker can tune it against real film scans and for the cameras they know.

## Where a preset breaks

It is applied to a picture that has already been rendered. That rendering was done by the editor or the camera, with decisions already made about tone, white balance and the handling of highlights. The preset then moves things around in a fixed way.

Film did not do that. Film responded to the light in the scene. An overexposed frame lost its highlights in a particular way, a tungsten-lit room went amber unless you used a filter, and a deeply coloured subject changed what the neighbouring colours did. A preset does not know any of that about your file, so the same preset can look right on one frame and wrong on the next. It is also made on one camera, in one kind of light, so it sits differently on another sensor.

## What a simulation does differently

A simulation starts from the scene's light, which is why raw files matter, and puts it through each stage of the film's process in the order the film went through it. Dyeroom's [Sunday 64](/films/sunday-64) is a colour slide film: the light becomes an exposure on three emulsion layers, then a first developer, re-exposure, three colour developers, bleach and fix, and finally the slide as seen on a light box or a projector. [Monday 400](/films/monday-400) is a black-and-white negative developed, then enlarged on to graded paper. Each stage is a physical or chemical model, built from the film maker's published data where it exists and fitted or assumed where it does not.

So the result depends on the file the way film depended on the light: exposure, the colour of the light, a filter, the way a colour is lit all go into it. Change the exposure and the highlights roll off the way the model of the film rolls them off, rather than the way a fixed curve does.

Other physically based simulators exist. [spektrafilm](https://github.com/andreavolpato/spektrafilm) is an open-source spectral film and print simulation, and there is a spektrafilm module for darktable. Dyeroom credits it, and it is worth a look if you would rather work on your own machine.

## What a simulation cannot do

**It cannot be exact.** A camera records three numbers per pixel, not a spectrum, so the light that would have reached the film has to be guessed. Mixed lighting is treated as the single light the camera balanced for. And nothing in Dyeroom's slide model has been checked against a real slide of a scene whose light was recorded, because no such pair is public.

**It models a chosen film.** You get one slide film and one black-and-white film. A preset library has many looks.

**It is slower and has fewer controls than an editor.** A photograph has to be developed, which takes a while, and what comes back is a JPEG or a TIFF, not a raw. You can still adjust colour, tones and crop afterwards, and re-develop with other settings, but you are no longer editing a raw file.

**It is not built for bulk delivery.** A roll can be developed and exported as a ZIP, but speed and batch editing are what editors are good at.

## When to use which

- You have a large set to deliver, a catalogue, a deadline: use a **preset**. It is faster and good enough, and it is what the tools are built for.
- You want a camera that produces film-like JPEGs straight out: use an **in-camera simulation**, and enjoy it.
- You want a look on video, or want to match footage: a **LUT** is the standard tool.
- You want to know what a film would have done with this particular file, you like the density and behaviour of a slide, or you want the print stage of black-and-white: use a **simulation**.
- You want both: many people do. Develop a few favourites through the simulation, and use a preset for everything else.

## Where Dyeroom's own "Presets" fit

Dyeroom also has a feature called Presets. It saves your development settings together with a frame's Colour and Tones adjustments under a name, so you can apply them to the next photograph or to every frame in the lab. That is a preset in the plain sense of the word, but it saves how you set the film, not a picture's look. The film is still developed from the file each time.

## Try it

[Develop the sample raw on Sunday 64](/app?sample=1&film=sunday64) and compare it against the raw with the Split view. For how the look is made, read [the slide film look from a raw file](/guides/slide-film-look-from-raw) and [how slide film was developed](/guides/how-slide-film-was-developed).
