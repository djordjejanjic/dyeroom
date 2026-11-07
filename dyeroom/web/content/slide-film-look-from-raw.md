---
slug: /guides/slide-film-look-from-raw
title: "The slide film look from a raw file: three ways to get it"
description: "In-camera recipes, presets and a modelled slide process all chase the slide film look. What each gives you, where it falls short, and how to choose."
h1: "Getting the slide film look from a raw file"
subline: "In-camera recipes, presets and a modelled process, compared honestly."
updated: 2026-11-03
author: Djordje Janjic
breadcrumb: Home > Guides > The slide film look from a raw file
image: /static/og/slide-film-look-from-raw.jpg
image_alt: "A bare tree and pines under a blue sky, developed on Sunday 64"
---

[figure]
/static/guides/tree-raw.jpg | A bare tree in front of pines under a blue sky: the neutral raw. | The raw
/static/guides/tree-sunday-64.jpg | The same file developed on Sunday 64: denser colour, a deeper sky and darker shadows. | Sunday 64
Pentax K-1 Mark II. Raw file from raw.pixls.us, released CC0.
[/figure]

People who ask for the slide film look rarely mean one thing. Some mean saturated colour. Some mean contrast, with blacks that really are black. Some mean a particular feeling, the way a slide looked held up to a window or thrown on a wall in a dark room. They are all describing the same family of films, and each of them is describing it from memory.

This guide says what is behind that look, compares the three ways of getting it from a digital file, and is plain about what each one cannot do. I make Dyeroom, which is one of the three, so weigh what I say about it accordingly.

## What the look is made of

A colour slide is a positive made in the camera film, seen by light passing through it. Four things follow from that.

**It is dense.** The picture is three layers of dye. Where there is a lot of dye, very little light gets through. The mid-tones sit dense and steep, and the shadows can go properly dark. A slide usually has more contrast than a negative film printed on paper, and often more saturated colour with it.

**It is made by a process.** The dyes form during development, in several stages, each depending on the last. What comes out is not a straight reading of the scene's colours. Layers influence each other, so a strong colour in one layer subdues development in its neighbours, and that pushes colours apart. It is part of why a slide's reds and blues look deep.

**It has no safety net.** The photographer chose the exposure and the slide showed it. Overexposed highlights are gone, and underexposed shadows are black. Part of the look is the discipline it forced.

**It is seen by transmitted light.** A light table, a loupe, a projector in a dark room. Clear film glows like a lamp, and the eye adapts to it, so the picture reads brighter and cleaner than the same dye on paper.

One caution: several slide films existed, from several makers and over several decades, and they looked different from each other. The slide film look is plural. Be wary of anyone who says they have reproduced it exactly.

## Way one: an in-camera recipe

Many cameras have film-style picture modes in their JPEG engine, and a large community shares recipes for adjusting them: a set of settings for tone, colour, grain and white balance that gives a particular film-like character. Recipes are free, they work at the moment you press the shutter, and they cost nothing in workflow. Photographers who like them often shoot raw and JPEG together.

Where they fall short: they are a set of tweaks to the camera's own rendering, so the result is as good as that rendering allows. A recipe is made on one camera with one sensor and does not translate exactly to another. And because they apply to the JPEG, the raw file is not changed at all.

## Way two: a preset or a LUT

A preset is a saved set of editor settings. A LUT is a lookup table, a fixed mapping from each input colour to an output colour. Both are applied to a picture that has already been rendered, either by the editor or by the camera, and both are quick, cheap and easy to apply across a whole shoot. A good one makes a consistent set.

Where they fall short is the same for both: they are a fixed transformation of the picture you already have. A preset does not know whether the file was under- or overexposed, or lit by tungsten or by shade. It cannot do what film did, which was to respond to the light in the scene. That is why the same preset can look right on one frame and wrong on the next. The comparison is worked out in [film presets vs film simulation](/guides/film-presets-vs-film-simulation), including when a preset is the better tool.

## Way three: develop the raw through a model of the film

Dyeroom's approach is to start from the raw file, work out the light that would have reached each of the film's three layers, and run the chemistry in the order the film went through it: latent image, first developer, re-exposure, colour development, bleach and fix, then the slide seen on a light box or a projector. The [full process](/guides/how-slide-film-was-developed) is described elsewhere. The point here is that the result depends on the file the way a slide depended on the light. Exposure, the colour of the light, a filter and the viewing all feed into it.

Where it falls short:

- **A camera records three numbers per pixel, not a spectrum.** The step from those three numbers to the light the film would have seen is an educated guess, and it is a guess about every pixel. Mixed lighting is treated as one light, the one the camera balanced for.
- **It models one film.** The film Dyeroom's Sunday 64 is modelled on is a classic colour slide film of the 1970s to the 2000s. It will not match a different film that you remember.
- **Nothing has been checked against a real slide of a known scene.** The film's behaviour is checked against the maker's published data, but no pair of a real slide and the scene it recorded is public to compare against.
- **It is slower and has fewer controls than an editor.** It does its work stage by stage and returns a developed JPEG or TIFF. Colour, tones and crop can be adjusted after, but you are not editing a raw any more.

## Using Sunday 64 to get close

Take the sample raw, or one of your own, and these controls decide most of the result.

1. **Exposure.** Start with *As shot*, which gives the slide the brightness the camera chose. If the file is under- or overexposed, try *Auto*, which places the exposure from the scene instead. Slide shooters often gave a third of a stop less than the meter, and *Compensation* does the same.
2. **Light and filter.** Leave *Light* on *As it was* and *Filter* on *Chosen for the light* for a result that behaves like a photographer's choice. If you want a neutral result with no cast from lamps, choose *Daylight*. The [colour conversion filters guide](/guides/colour-conversion-filters) explains why a tungsten-lit room goes amber without a filter, and when that is the look you want.
3. **Seen on.** *Light box* gives you the slide's own density and contrast. *Projector* is softer, warmer and shows more shadow detail. Try both on the same frame.
4. **Format.** 35 mm gives the visible grain you may associate with the look. A bigger format is finer. See [film grain by format](/guides/film-grain-by-format).

[figure]
/static/guides/flowers-raw.jpg | The sample photograph as a neutral raw. | The raw
/static/guides/flowers-light-box.jpg | Developed on Sunday 64 with the exposure as shot. | As shot
/static/guides/flowers-auto.jpg | Developed on Sunday 64 with auto exposure: darker, with a deeper sky. | Auto
/static/guides/flowers-projector.jpg | Developed on Sunday 64 and seen on a projector. | Projector
Olympus E-P7. Raw file from raw.pixls.us, released CC0.
[/figure]

Then judge it the way you would judge a slide. Look at the shadows first: are they allowed to be dark? Look at a strong red or blue: does it have depth rather than just saturation? Look at a highlight: is it clean? If you want to try it on your own file, [open the sample or your raw in the lab](/app?sample=1&film=sunday64).

## If you only want a preset

That is a reasonable thing to want. If you edit a large set in a catalogue and need consistency and speed, a good preset is faster, and none of what is written here says otherwise. Pick one from someone who shows it on several cameras and in several kinds of light, and be wary of promises of an exact match. The honest version of any of these three ways is a look you like, not a measurement.

## Related

[How slide film was developed](/guides/how-slide-film-was-developed) · [Sunday 64](/films/sunday-64) · [Colour conversion filters](/guides/colour-conversion-filters) · [Film presets vs film simulation](/guides/film-presets-vs-film-simulation)
