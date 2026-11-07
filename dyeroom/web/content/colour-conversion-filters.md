---
slug: /guides/colour-conversion-filters
title: "80A, 81A, 85B: colour conversion filters explained"
description: "What the classic colour conversion filters did for daylight film under tungsten and shade, how mireds work, and how they translate to a digital raw."
h1: "Colour conversion filters: 80A, 81A, 85B"
subline: "Why daylight film went amber under a lamp, and what the filters were for."
updated: 2026-11-03
author: Djordje Janjic
breadcrumb: Home > Guides > Colour conversion filters
image: /static/og/colour-conversion-filters.jpg
image_alt: "A room in warm indoor light, developed on Sunday 64"
---

Colour film is made for one colour of light. Use it in a different one and the picture takes on a cast. For a photographer in the film years the cure was a coloured filter on the lens, and a small family of them, the 80, 81 and 82 series, were as familiar as a lens cap. They still explain why a tungsten-lit room turns deep orange on daylight film, and why a digital white-balance slider is not quite the same thing.

## Light has a colour

The colour of a light is described as a colour temperature, in kelvin. Low numbers are warm and orange: a candle, a domestic tungsten lamp. High numbers are cool and blue: open shade under a clear sky. Midday daylight is around 5500 K, and that is what daylight-balanced film is designed for. Electronic flash is made to match it.

Your eye does not notice the difference much, because the brain adapts. Film did not adapt. It recorded the light as it was, and the result was a picture that was too orange under tungsten, too blue in deep shade, and a little warm or cold in between. A lamp that looks pleasantly warm to you looks stark orange to the film.

## Mireds: why the numbers on filters look odd

Filters were rated in mireds rather than kelvin. A mired is a million divided by the colour temperature in kelvin, and a filter of a given strength shifts the light by the same number of mireds wherever it starts. In kelvin the same filter would shift the light by a different amount at every starting point, so mireds are the honest unit. Blue filters have negative shifts, because they make light cooler; amber ones have positive shifts, because they make it warmer.

An 80A, for example, shifts about 131 mireds blue, which is what it takes to turn the light of a 3200 K tungsten lamp into something close to daylight. Add the shifts and you get the shift of the two filters together, which is why a photographer could stack them.

## The filters

A short, practical list, as the app labels them.

**Blue filters, for warm light**

- **80A.** Blue, for tungsten lamps.
- **80B.** Blue, for photoflood lamps, slightly warmer than a standard tungsten lamp.
- **80C.** Blue, for warm lamps, a little weaker.
- **80D.** A light blue, for the early sun.
- **82C, 82B, 82A.** Pale blue, for light that is warm by a smaller amount: late sun, warm window light. 82A is the faintest.

**Amber filters, for cold light**

- **81A.** Faint amber, for cloud.
- **81B.** Light amber, for shade.
- **81C.** Amber, for deep shade.
- **81EF.** Strong amber, for cold light.

**85B.** An orange filter with a strong warm effect. It was made to let film balanced for tungsten lamps be used in daylight. On daylight film it is not a correction at all but a strong warm cast. Dyeroom has it as a manual choice for the effect, and never picks it by itself.

A blue filter costs light, and an amber one costs less. In the film years that meant an exposure adjustment. In Dyeroom the light is metered through the filter, so the lost light does not make the slide darker.

## What Dyeroom does

In Sunday 64's Develop tab, *Light* has two choices.

- **As it was.** The film sees the real light of the scene, taken from the white balance the camera recorded. *Filter* then works as it would on the lens.
- **Daylight.** Everything is treated as if it were lit by daylight. The result is neutral, with no cast from lamps, and no filter is needed.

With *As it was*, *Filter* is by default set to be chosen for the light, in the way a photographer would choose it: a blue 80-series filter for tungsten, a pale blue 82 for light that is slightly warm, an amber 81 for cold shade. Close enough to daylight, it picks nothing, and it picks nothing when the camera's flash fired, because electronic flash is daylight-balanced like the film, so the subject comes out right and the room light around it goes warm, as it did on the real thing.

Set *Filter* to *None* with *Light* on *As it was* and you get what you got on the real film in a tungsten-lit room: deep amber.

[figure]
/static/guides/interior-no-filter.jpg | A shelf with small figures in a room in warm indoor light, developed on Sunday 64 with no filter: a yellow cast. | No filter
/static/guides/interior-80d.jpg | The same with the 80D filter Dyeroom chose: whites closer to neutral. | 80D, chosen for the light
Light a little warmer than daylight. On the right, the pale blue 80D Dyeroom chose for it. Under tungsten lamps the cast without a filter is much stronger. Phase One P40+ on Sunday 64. Raw file from raw.pixls.us, released CC0.
[/figure]

## Why a white-balance slider is not the same

A white-balance slider rescales the colour channels. A filter on the lens changed the light before the film ever saw it, and the film responded to the filtered light with its own sensitivities and its own tone scale. In Dyeroom the filter is applied to the light that reaches each of the three emulsion layers, so the result comes through the film's response, not around it.

That is a modest difference, and a camera's white balance is better for most pictures. The reason to use a filter here is to get the behaviour of the film: sometimes a pure correction, and sometimes a look, such as lamp-lit rooms that go as warm as they did on a slide.

## A quick guide

| The light | A photographer's filter |
|---|---|
| Midday daylight, open sky | None |
| Electronic flash | None |
| Tungsten lamps | 80A |
| Photoflood lamps | 80B |
| Late sun, warm window light | 82 series |
| Cloudy | 81A |
| Open shade | 81B |
| Deep shade | 81C, or 81EF for the coldest |

These are rules of thumb. The app works the choice out from the white balance the camera recorded, which is more precise than the table.

## Try it

[Open the sample](/app?sample=1&film=sunday64), set *Light* to *As it was* and try *Filter* with None and with the filter Dyeroom chooses, or with *Daylight*. The other guides: [Sunday 64](/films/sunday-64), [how slide film was developed](/guides/how-slide-film-was-developed) and [the slide film look from a raw file](/guides/slide-film-look-from-raw).
