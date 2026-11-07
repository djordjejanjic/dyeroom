---
slug: /how-it-works
title: "How Dyeroom works: raw file to film, stage by stage"
description: "From a raw file to a finished slide or print: exposure on three layers, development, dyes, viewing. What is measured, modelled and assumed."
h1: "How Dyeroom works"
subline: "A raw file goes in. A slide or a print comes out. This is what happens in between."
updated: 2026-11-03
author: Djordje Janjic
breadcrumb: Home > How it works
image: /static/og/how-it-works.jpg
image_alt: "Five stages of one photograph in the Dyeroom lab"
---

[figure]
/static/guides/stage-reading.jpg | The raw file being read in the lab | Reading the raw
/static/guides/stage-exposure.jpg | The latent image as the film is exposed | Exposure
/static/guides/stage-negative.jpg | The black-and-white negative forming in the first developer | First developer
/static/guides/stage-dyes.jpg | The dyes building in the colour developers | Colour developers
/static/guides/stage-slide.jpg | The finished slide in its mount on the light box | On the light box
Five stages of one photograph, as the lab shows them while it works.
[/figure]

Dyeroom develops a raw photograph on a simulated film. It is not a filter laid on a finished picture. The photograph goes through the stages the film would have gone through, each one a physical or chemical model, and the picture that results is whatever is left at the end. This page is the outline. Each film and each stage has its own page.

## The two films

**[Sunday 64](/films/sunday-64)** is a colour slide film, modelled on a classic slide film of the 1970s to the 2000s. It goes through exposure, a first developer, re-exposure, three colour developers, and bleach and fix, and is then viewed on a light box or a projector.

**[Monday 400](/films/monday-400)** is a black-and-white negative film, modelled on a classic fast film. It goes through exposure, a developer, a stop bath and fixer, and is then enlarged on to graded paper, with optional selenium toning.

## Sunday 64, stage by stage

**1. Reading the photograph.** The raw file is decoded to linear light, with the camera's own white balance. The exposure is placed where you meant it to be, by matching the mid-tones to the camera's own rendering. Digital sensor noise, which film never recorded, is removed, strongly in colour and lightly in brightness. (Film grain is put back by the film model later.)

**2. Light on the film.** The film's three layers each respond to a different range of colours, so Dyeroom needs a light spectrum, not just three numbers. Each pixel is turned into a plausible reflectance spectrum, like those of real materials, then lit by the scene's own light, passed through the lens and any filter, and measured against each layer's sensitivity. This is the least certain step, because a camera records only three numbers per pixel, and the spectrum is a reasoned guess. Blues are the hardest, for example: a blue sky and a blue shirt can have the same three numbers and different spectra. Exposure is then chosen the way a slide photographer judged it, by the slide it gives: the film exposure is set so the finished slide is as bright as a neutral rendering of your raw. *As shot* matches the brightness the camera chose, and *Auto* places the scene from its own brightness.

**3. The latent image.** Each layer's grains catch photons by chance. Enough photons and a grain can be developed. This randomness is the origin of film grain.

**4. First developer.** A black-and-white developer makes a negative silver image in each layer. As silver forms it releases a chemical that slows development in the same layer and its neighbours, which makes colours more saturated, and a little sideways, which makes edges crisper.

**5. Reversal and colour development.** What the first developer left behind becomes the dyes: red light through the base fogs the red-sensitive layer and a developer makes cyan there; blue light from the top fogs the blue-sensitive layer and a developer makes yellow; a third developer with its own fogging agent makes magenta in the green-sensitive layer. [A full account](/guides/how-slide-film-was-developed).

**6. Bleach and fix.** All the silver is removed. What is left is three dyes on a clear base.

**7. Viewing.** Light passes through the slide on a light box or a projector, and an eye adapted to the light and to the slide sees it. Dyeroom works out how every colour would look under those conditions and rebuilds it for a monitor in a normally lit room.

## Monday 400, stage by stage

**1. Exposure.** Each pixel's spectrum, the light, the filter on the lens and the film's sensitivity give the exposure. The film responds strongly to blue and violet and falls off before deep red, so skies and reds change tone, which is why [a filter](/films/monday-400#a-filter-on-the-lens) matters.

**2. Development.** The film is developed with the maker's published characteristic curves for the developer at the time chosen, including push development at higher ratings. Light scattering in the emulsion and the developer's edge effect shape the sharpness, and grain follows silver statistics.

**3. Stop and fix.** The undeveloped halide clears.

**4. Printing.** The negative is enlarged on to graded paper. The grade sets how much of the negative's range the paper takes, and the print is exposed like a test strip, so its brightness follows the picture. [The print stage explained](/guides/black-and-white-print-look).

**5. Toning (optional).** Selenium toner deepens the blacks and, if strong, turns the shadows and mid-tones purplish brown.

## What you control

Format, from 35 mm to 6×7 on 120 film ([grain by format](/guides/film-grain-by-format)); exposure and compensation; the light and conversion filter on Sunday 64 ([filters](/guides/colour-conversion-filters)); light box or projector; exposure index, lens filter, paper grade and toning on Monday 400. After development, Colour, Tones and Crop adjust the result without developing again, with undo. Develop again with other settings and compare with the previous version. Export JPEG or 16-bit TIFF, or a whole roll in a ZIP. The camera, lens, date, location and other metadata of the original are copied to the export, except tags that would be false for the new picture.

## Measured, modelled, assumed

**Measured and checked.** The film's response to light, its dyes, its sharpness and its grain come from the maker's published technical data, and the model is checked against that data.

**Modelled.** How grains catch light, how they develop, how development in one layer holds back its neighbours, how light passes through three dyes and is seen. These are physical models whose parameters are fitted to the published curves.

**Assumed.** What the maker never published: how strongly layers hold each other back, how much speed a long exposure loses past the data sheet, the amounts of selenium toning, the shape of the paper curve, how far the eye adapts into a slide.

**Not possible to check.** Whether a given photograph, developed here, matches a real slide made of the same scene. No such pair is public. So the honest claim is that this is a model of a film's behaviour, built from the maker's data, and that you should judge it as a look.

## What is not kept

Photographs are held only while you work on them, and deleted when you close the page, after a short time without activity, or at the latest a few hours after upload. There is no gallery and no copies. The [privacy notice](/privacy) has the details.

## Standing on other people's work

The spectral reconstruction follows published work by Otsu, Yamamoto and Hachisuka (2018) and Jakob and Hanika (2019). Colour appearance is computed with CIECAM16. Another open-source film simulation, [spektrafilm](https://github.com/andreavolpato/spektrafilm) by Andrea Volpato, is a related project that also exists as a darktable module. Dyeroom credits its published history for the densitometer response it uses. Colourising uses DDColor (Kang et al., ICCV 2023, Apache-2.0). Licences are listed at [/licences](/licences).

## Where next

[Try the sample raw](/app?sample=1) · [Sunday 64](/films/sunday-64) · [Monday 400](/films/monday-400) · [About](/about)
