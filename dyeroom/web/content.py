"""The film pages and guides: Markdown files in content/, read once at start and served by site.py.

Each file starts with front matter between --- lines (slug, title, description, h1, subline,
updated, author, breadcrumb, image, and for /about same_as), then the body in a small part of
Markdown: ## headings, paragraphs, "- " and "1. " lists, | tables, **bold**, *italic*, `code`,
[links](...), code blocks between ``` lines (shown with a Copy button where the browser can copy),
and figures:

    [figure]                       or [figure portrait], a small square beside the opening
    /static/guides/x.jpg | alt text | a label under it (optional)
    /static/guides/y.jpg | alt text | another, for a row of pictures
    The caption, in Markdown.
    [/figure]

Each heading gets an id made from its words, so /films/sunday-64#light-box-or-projector works.
A link to a page of this site that does not exist is left as plain words, so no page links to a 404.
HTML comments are notes for whoever edits the file and are dropped.
"""
import html
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

CONTENT = Path(__file__).parent / "content"
STATIC = Path(__file__).parent / "static"
# Pages that are not content but may be linked from it
OTHER_PAGES = {"/", "/app", "/terms", "/privacy", "/licences", "/films", "/guides"}

LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
BOLD = re.compile(r"\*\*(.+?)\*\*")
CODE = re.compile(r"`([^`]+)`")
ITALIC = re.compile(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])")


@dataclass
class Page:
    slug: str
    title: str
    description: str
    h1: str
    subline: str
    updated: date
    author: str
    breadcrumb: list
    image: str             # the picture for link previews, 1200 x 630, under /static
    image_alt: str
    body: str              # the Markdown
    same_as: list = field(default_factory=list)
    headings: list = field(default_factory=list)  # (id, words) of each ## heading


def _front_matter(text):
    """The simple key: value and key: / - item pairs these files use; nothing more of YAML."""
    meta, key = {}, None
    for line in text.splitlines():
        if not line.strip():
            continue
        if line.startswith("  - ") and key:
            meta.setdefault(key, []).append(line[4:].strip())
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if value:
            meta[key] = value[1:-1] if value[:1] == value[-1:] == '"' else value
    return meta


def load(folder=CONTENT):
    pages = {}
    for path in sorted(folder.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        _, head, body = text.split("---\n", 2)
        m = _front_matter(head)
        page = Page(slug=m["slug"], title=m["title"], description=m["description"], h1=m["h1"],
                    subline=m.get("subline", ""), updated=date.fromisoformat(m["updated"]),
                    author=m.get("author", ""), breadcrumb=[c.strip() for c in m["breadcrumb"].split(">")],
                    image=m["image"], image_alt=m.get("image_alt", ""), body=body,
                    same_as=m.get("same_as", []))
        page.headings = [(slugify(h), h) for h in re.findall(r"^## (.+)$", body, re.M)]
        pages[page.slug] = page
    return pages


def slugify(words):
    """GitHub's way: lower case, no punctuation, a hyphen for each space."""
    return re.sub(r"[^a-z0-9 -]", "", words.lower()).strip().replace(" ", "-")


def _known(url, pages):
    """Whether a link inside this site goes to a page that exists, down to its heading."""
    path, _, anchor = url.partition("#")
    path = path.split("?")[0]
    if path in OTHER_PAGES:
        return not anchor
    page = pages.get(path)
    return bool(page) and (not anchor or anchor in {i for i, _ in page.headings})


def inline(text, pages):
    """One line of Markdown to HTML: code and links, then bold and italic, everything else escaped."""
    links, codes = [], []

    def keep(m):
        words, url = m.group(1), m.group(2)
        links.append((words, url))
        return f"\x00{len(links) - 1}\x00"

    def keep_code(m):
        codes.append(m.group(1))
        return f"\x01{len(codes) - 1}\x01"

    text = html.escape(LINK.sub(keep, CODE.sub(keep_code, text)), quote=False)
    text = ITALIC.sub(r"<em>\1</em>", BOLD.sub(r"<strong>\1</strong>", text))

    def link(m):
        words, url = links[int(m.group(1))]
        words = inline(words, pages)
        if url.startswith("/"):
            return f'<a href="{html.escape(url)}">{words}</a>' if _known(url, pages) else words
        return f'<a href="{html.escape(url)}" rel="noopener">{words}</a>'

    text = re.sub(r"\x00(\d+)\x00", link, text)
    return re.sub(r"\x01(\d+)\x01", lambda m: f"<code>{html.escape(codes[int(m.group(1))])}</code>", text)


def _figure(kind, lines, pages):
    pictures, caption = [], []
    for line in lines:
        if line.startswith("/static/") and " | " in line:
            src, alt, *label = [part.strip() for part in line.split(" | ")]
            pictures.append((src, alt, label[0] if label else ""))
        elif line.strip():
            caption.append(line.strip())
    cells = []
    for src, alt, label in pictures:
        size = _size(src)
        dims = f' width="{size[0]}" height="{size[1]}"' if size else ""
        img = f'<img src="{_stamped(src)}" alt="{html.escape(alt)}"{dims} loading="lazy">'
        cells.append(f'<div class="cell">{img}<span class="label">{html.escape(label)}</span></div>' if label else
                     f'<div class="cell">{img}</div>')
    classes = " ".join(["figure", kind or ("row" if len(pictures) > 1 else "single")])
    style = f' style="--n: {len(pictures)}"' if len(pictures) > 1 else ""
    words = f"<figcaption>{inline(' '.join(caption), pages)}</figcaption>" if caption else ""
    return f'<figure class="{classes}"{style}><div class="pictures">{"".join(cells)}</div>{words}</figure>'


def _size(src):
    path = STATIC / src.removeprefix("/static/")
    if path.suffix.lower() not in (".jpg", ".jpeg", ".png"):
        return None
    from PIL import Image
    with Image.open(path) as im:
        return im.size


def _stamped(src):
    path = STATIC / src.removeprefix("/static/")
    return f"{src}?v={int(path.stat().st_mtime)}" if path.exists() else src


def render(page, pages):
    """The body of a page as HTML."""
    text = re.sub(r"<!--.*?-->", "", page.body, flags=re.S)
    out, para, lines = [], [], text.splitlines()

    def flush():
        if para:
            out.append(f"<p>{inline(' '.join(para), pages)}</p>")
            para.clear()

    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            flush()
        elif line.startswith("## "):
            flush()
            words = line[3:].strip()
            out.append(f'<h2 id="{slugify(words)}">{inline(words, pages)}</h2>')
        elif line.startswith("```"):
            flush()
            j = lines.index("```", i + 1)
            code = html.escape("\n".join(lines[i + 1:j]))
            out.append(f'<div class="code"><pre><code>{code}</code></pre>'
                       '<button type="button" class="copy" hidden>Copy</button></div>')
            i = j
        elif line.startswith("[figure"):
            flush()
            kind = line.strip()[7:-1].strip()
            j = lines.index("[/figure]", i)
            out.append(_figure(kind, lines[i + 1:j], pages))
            i = j
        elif re.match(r"(- |\d+\. )", line):
            flush()
            ordered = not line.startswith("- ")
            items = []
            while i < len(lines) and re.match(r"(- |\d+\. )", lines[i]):
                items.append(re.sub(r"^(- |\d+\. )", "", lines[i]))
                i += 1
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{inline(t, pages)}</li>" for t in items) + f"</{tag}>")
            continue
        elif line.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            head, body = rows[0], [r for r in rows[1:] if not set("".join(r)) <= set("-: ")]
            out.append('<div class="table"><table><thead><tr>' + "".join(f"<th>{inline(c, pages)}</th>" for c in head)
                       + "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{inline(c, pages)}</td>" for c in r)
                                                          + "</tr>" for r in body) + "</tbody></table></div>")
            continue
        else:
            para.append(line.strip())
        i += 1
    flush()
    return "\n".join(out)


def broken_links(pages):
    """Every internal link that would be dropped, as (page, url): for the tests and for editing."""
    return [(page.slug, url) for page in pages.values() for _, url in LINK.findall(page.body)
            if url.startswith("/") and not _known(url, pages)]
