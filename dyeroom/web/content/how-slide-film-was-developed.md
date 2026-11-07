---
slug: /guides/how-slide-film-was-developed
title: "How slide film was developed: reversal processing explained"
description: "A slide film gives a positive from the same film that caught the light. Reversal processing explained, step by step, with the dyes forming layer by layer."
h1: "How slide film was developed, step by step"
subline: "Reversal processing, and the lab-only process that added the dyes one layer at a time."
updated: 2026-11-03
author: Djordje Janjic
breadcrumb: Home > Guides > How slide film was developed
image: /static/og/how-slide-film-was-developed.jpg
image_alt: "A castle on a wooded hill, developed on Sunday 64"
---

[figure]
/static/guides/castle-sunday-64.jpg | A castle on a wooded hill above a valley of trees, developed on Sunday 64 and seen on a light box.
DJI FC4382 on Sunday 64, seen on a light box. Raw file from raw.pixls.us, released CC0.
[/figure]

A slide is the film that was in the camera. There is no negative and no print: the picture you hold up to the light is made in the same emulsion that caught the light. That is odd when you think about it, because the way film normally works gives you the opposite of what you want. The darkest parts of a negative are the parts that got the most light. To get a positive from the same piece of film, the lab has to turn the picture round while the film is still in the process. That is what reversal processing does.

This guide explains how, step by step, and then how the process was carried out for one classic colour slide film that needed an unusually demanding sequence of baths. Dyeroom models every step of that sequence in [Sunday 64](/films/sunday-64), so after each step I say what the model does with it.

## The trick: use what the light did not touch

When light hits a grain of silver halide in the film, the grain becomes developable. A black-and-white developer turns the grains that caught light into black metallic silver and leaves the others alone. If you stopped there, you would have a negative: lots of silver where the scene was bright.

For a slide, you do not stop there. What the first developer left behind is the positive image. In the shadows of your scene almost no light arrived, so almost all of the halide is still there. In the highlights the first developer used most of it up. If you could now turn the leftover halide into something that blocks light, in the right colour, and get rid of all the silver, you would have a slide: plenty of dye in the shadows, very little in the highlights, and the film shows its clear base where the scene was brightest.

That is the whole idea. Everything else is about making it work in colour.

## What colour film is made of

A colour film is a stack of layers on a transparent base. From the top, as the light enters: a layer sensitive to blue, a yellow filter layer, a layer sensitive to green, and a layer sensitive to red. The yellow filter layer exists because the green and red layers are also sensitive to blue light. It stops blue light reaching them, and it is removed in processing.

At the end of the process each layer holds a dye. The blue-sensitive layer ends up with yellow dye, the green-sensitive layer with magenta, and the red-sensitive layer with cyan. Each dye absorbs the colour its layer saw, so where the scene was blue, the film is lacking yellow dye and passes blue light. Three dyes, layered, make every colour on the slide.

[figure diagram]
/static/guides/film-layers.svg | Diagram of a colour film in cross-section. From the top: a blue-sensitive layer that becomes yellow dye, a yellow filter layer, a green-sensitive layer that becomes magenta dye, a red-sensitive layer that becomes cyan dye, then the clear base.
The layers of a colour slide film, top to bottom, and the dye each one ends up with.
[/figure]

## Why this film needed a lab of its own

Most slide films, the ones processed in the common E-6 process, have dye-forming chemicals (couplers) built into the emulsion layers. After the first developer and a single fogging step, one colour developer works on all three layers together, and the dyes appear at once.

The film modelled here worked differently. It had no couplers in the emulsion at all. The dye-forming chemical was in the developers instead: each colour developer carried the coupler for one dye. So the lab had to make the dyes one layer at a time, reaching each layer in turn, and the process was a long sequence of baths and re-exposures that few labs could run. That is a large part of why the film was tied to specialist labs.

How a colour developer forms dye is the same idea in either process. As the developing agent turns exposed (or fogged) silver halide into silver, the agent itself is used up, and its by-product reacts with a coupler to make dye in place, in the same spot as the silver. After bleaching, the silver is gone and the dye stays.

## The steps, in order

The order below follows the maker's published description of the process. Steps that Dyeroom does not model, such as the washes and the removal of a protective backing from the base, are described briefly and marked as such.

**1. Preparing the film.** The process began by removing a protective backing from the film base, then a rinse. Not modelled.

**2. First developer.** A black-and-white developer works on all three layers at once and makes a negative silver image in each of them. Grains that caught more photons develop faster, grains that caught only a few develop slowly, and unexposed grains develop barely at all, as chemical fog.

As silver forms it releases iodide. Iodide slows down development, in the layer where it was released and in the layers next to it, and it also drifts sideways a little. The two effects have names, the interimage effect and the adjacency (or edge) effect. The first makes colours more saturated, because development in one layer holds back development in its neighbours; the second makes edges crisper. Dyeroom models both, as slowing of development by the silver that has already formed nearby. How strongly layers slow each other was never published, so that strength is assumed, set so that colours come out with the density and saturation the film is remembered for.

Giving the first developer longer, which is what pushing slide film means, develops more of the weakly exposed grains. That gains little speed and costs black density, because the shadows lose the halide that would have become dye. The film's maker advised against it.

**3. Wash.** Not modelled.

**4. Re-exposure and the cyan developer.** What is left in the red-sensitive layer is exposed to red light shining through the base from underneath. Only the red-sensitive layer responds to red light, so only its remaining halide is fogged and made ready to develop. A developer carrying the cyan coupler then makes cyan dye wherever that silver halide was.

**5. Re-exposure and the yellow developer.** The film is now exposed to blue light from the top, which fogs the blue-sensitive layer. The yellow filter layer shields the green-sensitive layer below it from that light. A developer carrying the yellow coupler makes yellow dye in the top layer.

**6. The magenta developer.** One layer's halide is still untouched: the green-sensitive layer in the middle, which neither light could reach. The third developer carries a chemical fogging agent, so it fogs and develops all the halide still there, and it carries the magenta coupler. Magenta dye forms wherever the first developer had left halide behind.

**7. Conditioner, bleach and fix.** A conditioner prepares the silver for the bleach. The bleach turns all the silver back into silver halide, which includes the silver that made the negative image and the yellow filter layer. The fixer dissolves the halide away. Each layer now holds only its dye.

**8. Wash and dry.** Not modelled. The result is a transparent slide: three dyes on a clear base.

In Dyeroom the animation follows these stages: the raw being read, the flash of exposure, the black-and-white negative forming, cyan, yellow and magenta building up under the silver, the bleach, and the slide arriving on the light box.

[figure]
/static/guides/stage-negative.jpg | The black-and-white negative forming in the first developer | First developer
/static/guides/stage-dyes.jpg | The dyes building in the colour developers | Colour developers
/static/guides/stage-slide.jpg | The finished slide in its mount on the light box | On the light box
The first developer, the colour developers and the finished slide, as the lab shows them.
[/figure]

## Why it is clever, and why it is demanding

The re-exposure steps are what make each dye go into the right layer. Red light fogs only the red-sensitive layer. Blue light fogs the blue-sensitive layer at the top, and the yellow filter layer keeps it from the green-sensitive layer beneath. The last layer is fogged chemically by the developer itself. Every step depends on the one before.

It is also unforgiving. Three developers, each with a different job, have to stay in balance, so that a neutral grey comes out grey through all three layers. The makers also balanced each emulsion batch so that a grey card came out neutral under 5000 K light.

## Looking at the result

A slide is not finished until it is seen. Light passes through the three dyes, and what reaches the eye depends on the light: a light table, a projector lamp, a bright window. The eye adapts to that light and to the slide itself, so a metered mid-grey, which is dense film that lets through only a tenth of the light, still reads as mid-grey, while clear film glows like a highlight. Dyeroom models the light box and a projector, and then rebuilds how each colour looks under them for a normally lit screen. See [light box or projector](/films/sunday-64#light-box-or-projector).

## What the simulation leaves out

It does not model the washes, the backing, or the temperature and agitation of each bath. Its chemistry is a physical model fitted to the maker's published characteristic curves, so it reproduces how the real film responded, not every bath. And the step from your photograph to the light that would have reached the film is a guess, because a camera records three numbers per pixel and not a spectrum. See the limits on [Sunday 64](/films/sunday-64#what-is-measured-what-is-modelled-what-is-assumed).

## Where to read more

- Wikipedia's [article on the process](https://en.wikipedia.org/wiki/K-14_process) has a numbered table of the steps.
- The Wikipedia article on [the E-6 process](https://en.wikipedia.org/wiki/E-6_process), for the simpler process most other slide films used.

## See it happen

Open the [sample raw on Sunday 64](/app?sample=1&film=sunday64) and watch the stages go by, or read how the whole of Dyeroom fits together in [How Dyeroom works](/how-it-works). If you want the look rather than the chemistry, [the slide film look from a raw file](/guides/slide-film-look-from-raw) compares the ways of getting there.
