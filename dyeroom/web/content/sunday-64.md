---
slug: /films/sunday-64
title: "Sunday 64: a colour slide film simulation for raw files"
description: "Sunday 64 develops your raw photo like a colour slide: exposure, reversal development, then a light box or projector. Free, no account."
h1: "Sunday 64"
subline: "A colour slide film, developed the long way."
updated: 2026-11-03
author: Djordje Janjic
breadcrumb: Home > Films > Sunday 64
image: /static/og/sunday-64.jpg
image_alt: "Yellow flowers and tall grass against a hazy blue sky, developed on Sunday 64"
---

[figure]
/static/guides/flowers-light-box.jpg | Yellow flowers and tall grass against a hazy blue sky, developed on Sunday 64 and seen on a light box: dense colour and deep shadows.
Olympus E-P7 on Sunday 64, seen on a light box. Raw file from raw.pixls.us, released CC0.
[/figure]

Sunday 64 is the colour slide film in Dyeroom. You give it a raw photograph. It is exposed on three emulsion layers, put through a black-and-white first developer, re-exposed, developed again in three colour developers, bleached and fixed, and then looked at on a light box or a projector screen. Every one of those steps is modelled, in that order, and the picture you get back is what is left at the end.

It is a simulation, not a preset. A preset moves sliders on a picture that already exists. Here the picture is made by the process, so the result depends on the file the way a slide depended on the light. [Presets and simulation compared](/guides/film-presets-vs-film-simulation).

[Develop the sample raw on Sunday 64](/app?sample=1&film=sunday64) or open your own photographs in the lab. No account is needed.

## What a slide is

Most film makes a negative, and you make a print from it later. A slide film makes the final picture itself, a small positive transparency that you hold up to the light or project onto a wall. There is no second stage in which a printer can rescue a poor exposure. The photographer judged the exposure by the slides that came back, and many learned to give a little less light than the meter said, because slide film punishes overexposure: highlights wash out and cannot be recovered.

That is part of the look. A slide is seen by light passing through it, so colour is dense where the film is dense, shadows go properly dark, and clear film, where almost nothing was exposed to dark, glows like a lamp. A photograph viewed on paper or a screen has to imitate that. Dyeroom does it by working out what the finished slide would pass to your eye, and then rebuilding that appearance for your screen.

## The process, in order

1. **Light into three layers.** The film has a layer sensitive to blue at the top, then a yellow filter layer that stops blue light from reaching the layers beneath it, then a layer sensitive to green, then one sensitive to red. Each pixel of your photograph is turned into a plausible reflectance spectrum, lit by the light the camera balanced for, and measured against the spectral sensitivity of each layer.
2. **A latent image.** In each layer, grains of silver halide catch photons by chance. A grain that has caught enough can be developed; one that has caught too few stays nearly untouched. This is where grain comes from.
3. **First developer.** A black-and-white developer turns the exposed grains into metallic silver in every layer, which makes a negative image. As silver forms it releases a chemical that slows development in the same layer and in its neighbours. That is why colours come out more saturated, and it also sharpens edges.
4. **Re-exposure and colour development.** What the first developer did not touch is the positive image. Red light through the base fogs what is left in the red-sensitive layer, and a developer makes cyan dye there. Blue light from the top fogs the blue-sensitive layer, and a second developer makes yellow dye. A third developer, which carries its own fogging agent, makes magenta dye from whatever is left in the green-sensitive layer.
5. **Bleach and fix.** All the silver is removed, including the yellow filter layer's. Only three dyes on a clear base remain.
6. **Viewing.** Light passes through the dyes, and an eye adapted to the light and to the slide sees the result.

The [full account of how slide film was developed](/guides/how-slide-film-was-developed) takes each of these in turn.

[figure]
/static/guides/stage-reading.jpg | The raw file being read in the lab | Reading the raw
/static/guides/stage-negative.jpg | The black-and-white negative forming in the first developer | First developer
/static/guides/stage-dyes.jpg | The dyes building in the colour developers | Colour developers
/static/guides/stage-slide.jpg | The finished slide in its mount on the light box | On the light box
Four of the stages, as the lab shows them while it works.
[/figure]

## Light box or projector

The setting is called Seen on, and it changes what you see rather than how the film was processed.

- **Light box.** The slide lies on a 5000 K light table and is looked at closely, as with a loupe. You see the slide's own density and contrast, the way a good scan shows it.
- **Projector.** The slide is projected with a quartz-halogen lamp in a dark room. It looks softer and warmer, with more shadow detail showing.

[figure]
/static/guides/flowers-light-box.jpg | The photograph developed on Sunday 64 and seen on a light box: dense and contrasty. | Light box
/static/guides/flowers-projector.jpg | The same slide projected: warmer and softer, with more detail in the shadows. | Projector
Olympus E-P7 on Sunday 64. Raw file from raw.pixls.us, released CC0.
[/figure]

## The controls that matter

**Exposure.** *As shot* gives the slide the brightness the camera chose, so the exposure you set is the exposure you get. *Auto* places the exposure from the scene itself, so an under- or overexposed file comes out at the same brightness either way. *Compensation* then adds or takes away light, in steps, as slide photographers did when they gave a third of a stop less. Neither is a brightness slider on a finished picture: the change goes into the film, and the film's tone scale decides what it does to shadows and highlights.

**Light and filter.** Daylight film sees the scene's real light. *As it was* uses the colour of light the camera's white balance recorded, and *Filter* is set to be chosen for the light, as a photographer would: a blue filter for tungsten lamps, a pale blue or amber one for slightly warm or cold light, nothing for daylight or for flash. Set the filter to *None* and a tungsten-lit room goes deep amber, as it did on the real thing. *Daylight* pretends everything was lit by daylight, which gives a neutral result. The [colour conversion filters guide](/guides/colour-conversion-filters) explains the choices.

**Format.** 35 mm, or 6×4.5, 6×6 and 6×7 on 120 film. On a bigger frame each pixel covers more film, so the grain is finer and less detail is lost to the emulsion. See [film grain by format](/guides/film-grain-by-format).

**Grain.** On by default. It is generated by the film model, because the camera's own sensor noise is removed first: film never saw it.

**After the film.** Colour, Tones and Crop work on the developed slide and need no new development. Export a JPEG or a 16-bit TIFF, or a whole roll in a ZIP. The original photograph's camera, lens, date and other metadata are copied across.

## What to expect

Dense, saturated colour with strong reds and blues, steep contrast, shadows that are allowed to be black, and highlights that are bright and clean until they are overexposed. Sources disagree about the exact character of this family of films, and so do photographers who shot them. Do not expect your favourite memory of one roll.

A slide film asks for colour. A black-and-white file is turned away, with two choices: print it on [Monday 400](/films/monday-400), or have it colourised first. Colourising is an AI guess, labelled as one in the app and in the exported file's metadata, and the colours it invents are not the colours that were there.

## The film it is modelled on

Sunday 64 is modelled on a real colour slide film of the 1970s to the 2000s that is no longer made. Its response curves, its three dyes and its layer sensitivities come from the film maker's own published technical data. The footer of this page names the film and says whose trademark it is. Dyeroom is an independent project, and a model of a film is not the film.

## What is measured, what is modelled, what is assumed

The film's response to light, its dyes and its sharpness come from the published data and are checked against it. The behaviour of the grains and the chemistry is a physical model fitted to those curves. A few things are assumed because they were never published: how strongly development in one layer slows its neighbours, set so that colours reach the familiar density and saturation, and how much speed a long exposure loses beyond the range the data sheet covers.

A camera records three numbers per pixel, not a spectrum, so the step from your photograph to the light that would have reached the film is an informed guess. It treats mixed lighting as the single light the camera balanced for. And nothing in this model has been checked against a real slide of a scene whose original light was also recorded, because no such pair has been published. Choose it as a look you like, not as a measurement.

## Try it

[Develop the sample raw on Sunday 64](/app?sample=1&film=sunday64), free and without an account. For the other film, see [Monday 400](/films/monday-400); for the whole process, [How Dyeroom works](/how-it-works).
