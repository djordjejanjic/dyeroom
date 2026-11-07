---
slug: /films/monday-400
title: "Monday 400: black-and-white film and darkroom print"
description: "Monday 400 develops your raw as a black-and-white negative in a classic developer, then prints it on graded paper, with optional selenium toning."
h1: "Monday 400"
subline: "A black-and-white negative, printed the long way."
updated: 2026-11-03
author: Djordje Janjic
breadcrumb: Home > Films > Monday 400
image: /static/og/monday-400.jpg
image_alt: "A bare tree and pines, printed on Monday 400"
---

[figure]
/static/guides/tree-monday-400.jpg | A bare tree in front of pines, printed on Monday 400: rich blacks and a full range of grey.
Pentax K-1 Mark II on Monday 400, grade 3. Raw file from raw.pixls.us, released CC0.
[/figure]

Monday 400 is the black-and-white film in Dyeroom. A raw photograph is exposed on a simulated fast negative film, developed, fixed, and then enlarged on to graded silver-gelatin paper, with the paper grade you choose and, if you like, selenium toning. What you get back is a print, not just a negative: the contrast you see is partly the film and partly the paper.

It takes colour or black-and-white originals. Unlike [Sunday 64](/films/sunday-64), a colour file is welcome here: the film is sensitive to colour in its own way, and that is part of what makes the picture.

[Develop the sample raw on Monday 400](/app?sample=1&film=monday400), free and without an account.

## The negative

Monday 400 is modelled on a classic fast black-and-white negative film. It is panchromatic, which means it responds to most of the visible spectrum, but not equally. It is strongest in violet and blue and falls off before the deep red. In practice, reds print darker and blue skies print lighter than your eye sees them, which is a large part of the look of black-and-white pictures from film.

The developer is a widely used fast-acting one, and the model uses the film maker's published characteristic curves for it at several development times, interpolated for the time the exposure needs. A longer development raises the shadows proportionally more than the highlights, so the measured curves are used rather than one curve scaled up.

Image structure is modelled too. Light scatters inside the emulsion, which softens the exposure a little. The developer works harder at the edge of a dense area, where it is fresher, than inside it, which makes edges crisp. Silver grain follows its own statistics: it gets coarser with density and finer as the area you look at gets bigger.

## Rated at

*Rated at* is the exposure index. 400 is the film's box speed. 800 is one stop under, developed normally, as the maker advised. 1600 and 3200 are push-developed: the film is rated higher and given more development to match.

Pushing is a trade. It lifts the shadows and the contrast, and it makes the grain more visible. In Dyeroom the print is exposed afterwards the way a printer would read a test strip, so the print's overall brightness is matched to the neutral rendering of the raw. Rating and push therefore change contrast, shadows and grain, not how bright the print is.

## A filter on the lens

Black-and-white photographers put coloured filters on the lens because the film turns colour into grey, and the filter decides which greys. A filter lightens colours like its own and darkens the opposite ones.

- **8, yellow.** Darker skies, a gentle effect.
- **15, deep yellow.** Darker skies still.
- **25, red.** Dark skies and light reds, the dramatic one.
- **11, yellow-green.** Lighter foliage and good skin tones.
- **58, green.** Lighter foliage, darker reds.

A filter costs light, and the model exposes the film for that, using the maker's filter factors. [Colour conversion filters](/guides/colour-conversion-filters) cover the other kind of filter, the one for colour film.

[figure]
/static/guides/flowers-monday-400.jpg | Yellow flowers and tall grass printed on Monday 400 without a filter. | No filter
/static/guides/flowers-monday-400-red.jpg | The same with a red filter: the sky is darker and the clouds stand out. | Red filter (25)
Olympus E-P7 on Monday 400, grade 3. Raw file from raw.pixls.us, released CC0.
[/figure]

## Printing on paper

The negative is enlarged on to glossy fibre-base paper through a diffusion enlarger. The paper's grade says how much of the negative's range it can take: a low grade is soft, a high one is hard. Grades 1 to 5 are offered. Grade 2 is the textbook match for a normal negative. Dyeroom prints on grade 3 by default, which is punchier than the textbook. The print's exposure is set like a darkroom printer would with a test strip, so the print's brightness follows the picture.

The [darkroom print look](/guides/black-and-white-print-look) explains what a grade does to a picture and why it is such a strong tool.

## Selenium toning

Selenium toner is a bath after printing that turns silver into silver selenide, starting from the densest silver. A **light** bath deepens the blacks and barely changes the colour. A **strong** one reaches the mid-tones too, and shadows and mid-tones turn a purplish brown. The amounts in Dyeroom are an assumption: the film and paper makers describe toning in words, not in measurements.

[figure]
/static/guides/garden-untoned.jpg | A garden behind a picket fence, printed on Monday 400 without toning. | Untoned
/static/guides/garden-selenium-strong.jpg | The same print toned strongly: deeper shadows with a purplish brown tone. | Selenium, strong
Leica M10-R on Monday 400, grade 3. Raw file from raw.pixls.us, released CC0.
[/figure]

## Format and grain

35 mm, or 6×4.5, 6×6 and 6×7 on 120 film. On a bigger frame each pixel covers more film, so the grain is finer. See [film grain by format](/guides/film-grain-by-format).

## Colourising

A black-and-white file is fine on Monday 400. The other direction is different: a black-and-white original has no colour in it, so any colour you add is invented. Dyeroom can colourise a black-and-white photograph with an AI model before developing it on the slide film. The result is labelled as a guess in the app, and the exported file carries a metadata tag that says the colours were made with generative AI. Nothing is ever drawn on the picture.

## What is measured, what is assumed

The film's curves, spectral sensitivity, filter factors and image structure come from the maker's published data. The developer's behaviour at several times is measured, not assumed. The paper's characteristic curve is shaped between standardised points, with a long toe and a short shoulder: that shape is an assumption. So are the amounts of selenium toning, the exact tone of the paper and silver, and the precise shape of the filters. Burning and dodging, split-grade printing and other darkroom handwork are not modelled.

## Try it

[Develop the sample raw on Monday 400](/app?sample=1&film=monday400). Next, [how a darkroom print gets its look](/guides/black-and-white-print-look), or [how the whole of Dyeroom works](/how-it-works).
