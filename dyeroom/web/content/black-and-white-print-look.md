---
slug: /guides/black-and-white-print-look
title: "The darkroom print look: paper grades and selenium toning"
description: "How a negative becomes a print: paper grades 1 to 5, the test strip and selenium toning, and how to get the same look from a digital raw file."
h1: "The darkroom print look"
subline: "What the paper does to a negative, and how to get the same from a digital file."
updated: 2026-11-03
author: Djordje Janjic
breadcrumb: Home > Guides > The darkroom print look
image: /static/og/black-and-white-print-look.jpg
image_alt: "A garden behind a picket fence, printed on Monday 400"
---

[figure]
/static/guides/garden-untoned.jpg | A garden behind a picket fence, printed on Monday 400: deep blacks, bright whites and a full range of grey between them.
Leica M10-R on Monday 400, grade 3. Raw file from raw.pixls.us, released CC0.
[/figure]

A black-and-white negative is not the picture. It is an intermediate, flat and reversed, and the picture is made when the negative is printed. Two photographers can print the same negative and produce prints that look like different photographs, and the difference is almost all in the paper and what is done to it. This page explains that stage, for people who have never made a print and for those who miss it.

## From negative to print

In the darkroom, a negative goes in an enlarger, a lamp with a lens. The light passes through the negative and is focused on to a sheet of light-sensitive paper below. The paper is exposed, developed, stopped, fixed and washed, like film. Where the negative was dense, little light reached the paper and the print stays white. Where the negative was thin, a lot arrived and the print goes black. The two reversals give a positive.

Dyeroom's Monday 400 prints on glossy fibre-base paper through a diffusion enlarger, which is the plain, classic route. [See how the negative itself is made](/films/monday-400).

## Paper grades

A negative can hold a wide range of tones, from a bright sky to a deep shadow. Paper holds fewer. A grade tells you how the paper fits the one into the other.

A **low grade** (1, soft) takes a wide range of exposure on its way from white to black, so it fits in a contrasty negative and gives a gentle print. A **high grade** (5, hard) takes a narrow range, so it stretches a flat negative and gives a punchy print with strong blacks and whites. Grade 2 is the textbook match for a normal negative. Grade 3 is a bit harder, punchier than the textbook, and it is Dyeroom's default.

On variable-contrast papers the grade is chosen with filters in the enlarger rather than by buying a different box of paper, but the effect on the picture is the same.

The grade is a creative decision, not a correction. A grade-1 print of a bright landscape can look misty; a grade-5 print of the same negative can look graphic. Choosing a grade changes how the picture feels, because it changes how far apart the tones are.

[figure]
/static/guides/castle-grade-1.jpg | A castle on a wooded hill printed on grade 1: soft and grey. | Grade 1
/static/guides/castle-grade-3.jpg | The same on grade 3. | Grade 3
/static/guides/castle-grade-5.jpg | The same on grade 5: hard, with strong blacks and whites. | Grade 5
DJI FC4382 on Monday 400. Raw file from raw.pixls.us, released CC0.
[/figure]

## The test strip

A printer does not know the right exposure until the first print comes out. The standard method is a test strip: expose the paper in bands, each one for a different time, develop it and pick the band that looks right. The printer is looking for the brightness that suits the picture, and tests highlights and shadows.

Dyeroom does the same job automatically. It sets the print exposure so that the print's lightness matches the neutral rendering of your raw file as closely as the paper allows. The consequence is that when you change the film's rating or push it, the print's overall brightness does not change. What changes is contrast, shadows and grain. That is a design decision: a darkroom printer would adjust the print exposure to compensate, too.

## Selenium toning

Toning is done after printing, in a bath. Selenium toner turns the silver of the image into silver selenide, starting from the densest silver and working outwards. The result depends on how strong the bath is and how long the print stays in it.

A **light** bath converts the deepest shadows. The blacks become denser, a little deeper than the paper alone could give, and the colour hardly changes. A **strong** bath reaches into the mid-tones as well, and shadows and mid-tones turn a purplish brown. Toning was also used to make prints more permanent, not only for the look.

Film and paper makers describe toning in words more than in measurements. In Dyeroom the amounts are therefore assumed: how much denser the blacks get, and the exact tone of the selenide. They are chosen to look right, not measured.

[figure]
/static/guides/garden-untoned.jpg | The garden print without toning. | Untoned
/static/guides/garden-selenium-light.jpg | With light selenium toning: the blacks a little deeper. | Selenium, light
/static/guides/garden-selenium-strong.jpg | With strong selenium toning: the shadows turn purplish brown. | Selenium, strong
Leica M10-R on Monday 400, grade 3. Raw file from raw.pixls.us, released CC0.
[/figure]

## What a digital edit can and cannot do

You can get part of the way with an editor. A contrast curve does much the same job as paper grade. A split-toning control or a colour adjustment on the shadows can suggest a toned print.

What is harder to reproduce is the way the whole thing hangs together. The paper has a particular curve, with a long toe in the shadows and a short shoulder in the highlights, and it is the shape of that curve, more than the contrast alone, that gives a print its feel. And the paper can only go so black: the toning bath changes that limit, which is why the effect on the blacks is real, not just a tint. In Dyeroom the shape of the paper curve between its standard points is an assumption, and the burning and dodging that a printer does by hand, holding back light from one area and adding it to another, is not modelled. Nor is split-grade printing, where two filters are used for two exposures. Be honest with yourself about where a model stops and a darkroom begins.

## How Monday 400 does it

1. The negative is made as described on [the Monday 400 page](/films/monday-400).
2. Pick a *Paper grade* from 1 to 5.
3. Choose *Selenium*: None, Light or Strong.
4. Compare the print to the neutral raw with *Split*.

[Develop the sample raw on Monday 400](/app?sample=1&film=monday400), and try one grade lower and one higher.

## Related

[Film grain by format](/guides/film-grain-by-format) · [Monday 400](/films/monday-400) · [How Dyeroom works](/how-it-works)
