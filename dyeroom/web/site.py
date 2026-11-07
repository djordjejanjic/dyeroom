"""Dyeroom's public pages, served as finished HTML: the home page, and the film pages and guides
written in content/ (read by content.py).

The app itself is at /app and kept out of search results; these pages are what search engines
and link previews see. Each carries its title, description, canonical address, Open Graph and
Twitter tags and JSON-LD. The canonical address and the absolute links come from
DYEROOM_PUBLIC_URL; when it is not set, none is guessed (previews still get the image from the
address the request came to). Their stylesheet is static/site.css, small and apart from the
app's, so the pages load at once.

The words are the app's own: the tagline, the pitch, About's "How it works", the films'
descriptions and the privacy wording. Trademarks only in the footer's "modelled on" line.
"""
import html
import json
import os
import time
from pathlib import Path

PUBLIC_URL = os.environ.get("DYEROOM_PUBLIC_URL", "").rstrip("/")
STATIC = Path(__file__).parent / "static"

TITLE = "Dyeroom: develop your raw photos on simulated film"
DESCRIPTION = ("Develop your raw files or phone photos on simulated slide and black-and-white film, stage by stage, with the "
               "chemistry modelled. Free, no account, nothing stored.")

MARK = ('<svg width="22" height="22" viewBox="0 0 20 20" aria-hidden="true"><rect x="1" y="1" width="18" height="18" '
        'rx="3" fill="#e9e1d0"/><rect x="4" y="6" width="12" height="8" rx="1" fill="#141311"/><rect x="6" y="3" '
        'width="8" height="1.5" fill="#b52d1b"/></svg>')
ICONS = {  # the app's own, from index.html
    "cup": '<path d="M5 9.5h11v4.5a5 5 0 0 1-5 5h-1a5 5 0 0 1-5-5z"/><path d="M16 11h1.6a2.4 2.4 0 0 1 0 4.8H16"/>'
           '<path d="M9 3.8c-.6.7-.6 1.5 0 2.2M12.5 3.8c-.6.7-.6 1.5 0 2.2"/>',
    "lock": '<rect x="5" y="10.5" width="14" height="9.5" rx="2"/><path d="M8.5 10.5V8a3.5 3.5 0 0 1 7 0v2.5M12 14.4v2"/>',
    "camera": '<path d="M8.5 7.2 10 5h4l1.5 2.2"/><rect x="3" y="7.2" width="18" height="12" rx="2"/>'
              '<circle cx="12" cy="13.2" r="3.4"/>',
}


def _icon(name, size=24):
    return f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" aria-hidden="true">{ICONS[name]}</svg>'


def _stamp(asset):
    return f"/static/{asset}?v={int((STATIC / asset).stat().st_mtime)}"


def _head(title, description, path, base, image, image_alt, jsonld, robots="index,follow,max-image-preview:large"):
    """The head of a public page. `base` is the site's address for absolute links (PUBLIC_URL,
    or the request's when that is unset); the canonical address is given only from PUBLIC_URL."""
    e = html.escape
    url = f"{base}{path}"
    image_url = f"{base}{image}"
    canonical = f'<link rel="canonical" href="{e(PUBLIC_URL + path)}">\n' if PUBLIC_URL else ""
    data = "".join(f'<script type="application/ld+json">{json.dumps(item, separators=(",", ":"))}</script>\n'
                   for item in jsonld)
    return f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
{canonical}<meta name="robots" content="{robots}">
<meta property="og:site_name" content="Dyeroom">
<meta property="og:type" content="website">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{e(url)}">
<meta property="og:image" content="{e(image_url)}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{e(image_alt)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(description)}">
<meta name="twitter:image" content="{e(image_url)}">
<meta name="theme-color" content="#141311">
<link rel="icon" href="/static/icon.svg" type="image/svg+xml">
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="apple-touch-icon" href="/static/apple-touch-icon.png">
<link rel="manifest" href="/static/site.webmanifest" crossorigin="use-credentials">
<link rel="stylesheet" href="{_stamp('site.css')}">
{data}"""


def _nav():
    return ('<nav aria-label="Main"><a href="/guides">Guides</a><a href="/app?sample=1">Try a sample</a>'
            '<a class="btn small" href="/app">Open Dyeroom</a></nav>')


def _footer(accounts, donate):
    e = html.escape
    links = ['<a href="/app">Open Dyeroom</a>', '<a href="/how-it-works">How it works</a>', '<a href="/guides">Guides</a>',
             '<a href="/about">About</a>', '<a href="/terms">Terms</a>', '<a href="/privacy">Privacy</a>',
             '<a href="https://github.com/djordjejanjic/dyeroom" rel="noopener">Source code</a>']  # free software (AGPL): its source, one click away
    if accounts:
        links.append('<a href="/refunds">Refunds</a>')
    if donate and not accounts:
        links.append(f'<a class="donate-link" href="{e(donate)}" rel="noopener">{_icon("cup", 15)}Buy me a coffee</a>')
    return f"""<footer class="foot">
<nav aria-label="Site">{"".join(links)}</nav>
<p class="fine">Sunday 64 is modelled on Kodak Kodachrome 64, Monday 400 on Kodak Tri-X 400. Kodak, Kodachrome and Tri-X are trademarks of Eastman Kodak Company. Dyeroom is an independent project and is not affiliated with, sponsored by or endorsed by Kodak.</p>
</footer>"""


def home(base, accounts, donate, privacy, max_mb):
    """The home page. `privacy` is the app's privacy facts (in_memory, idle_minutes, keep_hours)."""
    e = html.escape
    url = (PUBLIC_URL or base) + "/"
    jsonld = [
        {"@context": "https://schema.org", "@type": "WebSite", "name": "Dyeroom", "url": url},
        {"@context": "https://schema.org", "@type": "WebApplication", "name": "Dyeroom", "url": url,
         "description": DESCRIPTION, "applicationCategory": "MultimediaApplication",
         "operatingSystem": "Any, in a web browser", "browserRequirements": "Requires JavaScript",
         "image": f"{PUBLIC_URL or base}/static/og/home.jpg",
         **({"isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "EUR"}}
            if not accounts else {})},
    ]
    where = "in the server's memory, never on a disk, and only while you work" if privacy.get("in_memory") \
        else "only while you work"
    hours = privacy.get("keep_hours", 3)
    hours = "an hour" if hours == 1 else f"{str(hours).removesuffix('.0')} hours"
    kept = "There are no copies and no backups" + ("; only your account and what you bought are kept" if accounts else "")
    stored = (f"Your photographs are never stored. They are held {where}, and deleted as soon as you close the page, "
              f"after {privacy.get('idle_minutes', 30)} minutes without activity, or {hours} after upload at the "
              f"latest. {kept}.")
    free = (f'<a class="fact fact-free" href="{e(donate)}" rel="noopener">{_icon("cup")}<span><b>Free to use</b>'
            f'<span>Support it with a coffee</span></span></a>' if donate and not accounts else
            f'<div class="fact">{_icon("cup")}<span><b>Free to use</b><span>No account needed</span></span></div>'
            if not accounts else "")
    free_part = (f"""<section class="part">
<h2>Free to use</h2>
<div><p>Every film, setting and kind of export is free for everyone, with nothing to sign up for.{
    f' If Dyeroom is useful to you, you can keep it going with a coffee: <a class="donate-link" href="{e(donate)}" rel="noopener">{_icon("cup", 15)}Buy me a coffee</a>. A donation buys nothing extra; everyone gets the same.' if donate else ''}</p></div>
</section>""" if not accounts else "")
    month = time.strftime("%b %Y").upper()
    return f"""<!doctype html>
<html lang="en">
<head>
{_head(TITLE, DESCRIPTION, "/", PUBLIC_URL or base, "/static/og/home.jpg",
       "A Sunday 64 slide developed by Dyeroom: yellow flowers and tall grass against a hazy blue sky", jsonld)}
<link rel="preload" as="image" href="/static/sample-slide.jpg">
</head>
<body>
<header class="top">
<a class="brand" href="/">{MARK}Dyeroom</a>
{_nav()}
</header>
<main>
<section class="hero">
<figure class="mount">
<span class="mount-print mount-top">Sunday 64</span>
<span class="mount-window"><img src="/static/sample-slide.jpg" alt="A developed Sunday 64 slide in its mount" width="720" height="480"></span>
<span class="mount-print mount-bottom"><span>Dyeroom</span><span>{month}</span><span>01</span></span>
</figure>
<div class="hero-text">
<h1>Developed <em>the long way.</em></h1>
<p class="lede">Dyeroom develops your raw photographs on simulated film, from the exposure to the finished slide or print.</p>
<p class="pitch">Each one is exposed on Sunday 64 and taken through the whole reversal process, from the first developer to the bleach, before it reaches the light table.</p>
<div class="actions"><a class="btn primary" href="/app">Start developing</a><a class="btn" href="/app?sample=1">Try a sample</a></div>
<div class="facts">{free}<div class="fact">{_icon("lock")}<span><b>Nothing is stored</b><span>Deleted when you leave</span></span></div><div class="fact">{_icon("camera")}<span><b>Raw or phone photos</b><span>Cameras and phones, up to {max_mb} MB</span></span></div></div>
</div>
</section>

<section class="part">
<h2>Not a preset</h2>
<div><p>Each photograph is exposed on a simulated film and taken through its chemistry step by step. Sunday 64 is a colour slide film: latent image, first developer, re-exposure, three colour developers, bleach and fix, then the slide on a light box or a projector screen. Monday 400 is a black-and-white negative: developer, stop bath and fixer, then enlarged onto paper. <a href="/how-it-works">How Dyeroom works</a>.</p></div>
</section>

<section class="part">
<h2>Two films</h2>
<div class="films">
<figure class="film"><img src="/static/og/film-sunday64.jpg" alt="The sample photograph developed on Sunday 64" width="1200" height="901" loading="lazy">
<figcaption><b><a href="/films/sunday-64">Sunday 64</a></b><span>Colour slide film, ISO 64, seen on a light box or a projector screen.</span></figcaption></figure>
<figure class="film"><img src="/static/og/film-monday400.jpg" alt="The sample photograph developed on Monday 400 and printed" width="1200" height="901" loading="lazy">
<figcaption><b><a href="/films/monday-400">Monday 400</a></b><span>Black-and-white negative, ISO 400, printed on paper, with paper grades and selenium toning.</span></figcaption></figure>
</div>
</section>

<section class="part">
<h2>Nothing is stored</h2>
<div><p>{e(stored)}</p></div>
</section>

{free_part}
</main>
{_footer(accounts, donate)}
</body>
</html>"""


AUTHOR_URL = "https://djordjejanjic.rs"
SECTIONS = {"Films": "/films", "Guides": "/guides"}


def _person(pages):
    about = pages.get("/about")
    return {"@type": "Person", "name": "Djordje Janjic", "url": AUTHOR_URL,
            **({"sameAs": about.same_as} if about and about.same_as else {})}


def _breadcrumb(crumbs, current, root):
    """Home > Films > Sunday 64, as links and as BreadcrumbList data; a crumb without a page is words."""
    e = html.escape
    paths = {"Home": "/", **SECTIONS}
    shown, items = [], []
    for position, name in enumerate(crumbs, 1):
        path = current if position == len(crumbs) else paths.get(name)
        shown.append(f'<a href="{path}">{e(name)}</a>' if path and position < len(crumbs) else f"<span>{e(name)}</span>")
        items.append({"@type": "ListItem", "position": position, "name": name, **({"item": root + path} if path else {})})
    nav = f'<nav class="crumbs" aria-label="Breadcrumb">{" <i>/</i> ".join(shown)}</nav>'
    return nav, {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": items}


def _date(d):
    return f"{d.day} {d.strftime('%B %Y')}"


def _frame(head, body, accounts, donate):
    return f"""<!doctype html>
<html lang="en">
<head>
{head}
</head>
<body>
<header class="top">
<a class="brand" href="/">{MARK}Dyeroom</a>
{_nav()}
</header>
<main>
{body}
</main>
{_footer(accounts, donate)}
</body>
</html>"""


def page(base, accounts, donate, item, pages):
    """A film page, a guide, /how-it-works or /about, from content.py."""
    from . import content
    e = html.escape
    root = PUBLIC_URL or base
    nav, crumbs = _breadcrumb(item.breadcrumb, item.slug, root)
    image = f"{root}{item.image}"
    if item.slug == "/about":
        data = {"@context": "https://schema.org", "@type": "AboutPage", "name": item.title, "url": root + item.slug,
                "description": item.description,
                "mainEntity": {**_person(pages), "image": f"{root}/static/about/djordje-janjic.jpg",
                               "jobTitle": "Software engineer and photographer"}}
        byline = ""
    else:
        data = {"@context": "https://schema.org", "@type": "Article", "headline": item.h1, "description": item.description,
                "url": root + item.slug, "mainEntityOfPage": root + item.slug, "image": image,
                "datePublished": item.updated.isoformat(), "dateModified": item.updated.isoformat(),
                "author": {**_person(pages), "url": f"{root}/about"}, "inLanguage": "en"}
        byline = (f'<p class="byline">By <a href="/about">{e(item.author)}</a> · Updated '
                  f'<time datetime="{item.updated.isoformat()}">{_date(item.updated)}</time></p>')
    head = _head(item.title, item.description, item.slug, root, item.image, item.image_alt, [data, crumbs])
    subline = f'<p class="subline">{e(item.subline)}</p>' if item.subline else ""
    body = f"""<article class="page">
{nav}
<h1>{e(item.h1)}</h1>
{subline}{byline}
<div class="prose">
{content.render(item, pages)}
</div>
</article>"""
    return _frame(head, body, accounts, donate)


def listing(base, accounts, donate, section, pages):
    """/films or /guides: each page of the section with its description."""
    e = html.escape
    root = PUBLIC_URL or base
    path = SECTIONS[section]
    found = sorted((p for p in pages.values() if p.slug.startswith(path + "/")), key=lambda p: p.slug)
    if section == "Guides":
        found += [p for p in (pages.get("/how-it-works"),) if p]
    nav, crumbs = _breadcrumb(["Home", section], path, root)
    title = ("Dyeroom's films: Sunday 64 and Monday 400" if section == "Films"
             else "Guides to film, slides and the darkroom, from Dyeroom")
    description = ("The two simulated films in Dyeroom: a colour slide film and a black-and-white negative printed on paper."
                   if section == "Films" else
                   "How slide film was developed, the slide film look from a raw file, grain, filters and the darkroom print.")
    data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": title, "url": root + path,
            "hasPart": [{"@type": "Article", "headline": p.h1, "url": root + p.slug} for p in found]}
    head = _head(title, description, path, root, "/static/og/home.jpg",
                 "A Sunday 64 slide developed by Dyeroom: yellow flowers and tall grass against a hazy blue sky", [data, crumbs])
    items = "".join(f'<li><a href="{p.slug}"><b>{e(p.h1)}</b><span>{e(p.description)}</span></a></li>' for p in found)
    body = f"""<article class="page">
{nav}
<h1>{section}</h1>
<ul class="listing">{items}</ul>
</article>"""
    return _frame(head, body, accounts, donate)
