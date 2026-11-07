# Dyeroom: developing notes

How Dyeroom works, how to run it and how to host it. For what it is and how to use it, see
[README.md](README.md); for the data, papers and licences it builds on, [SOURCES.md](SOURCES.md).

**Sunday 64** is a simulated colour slide film and its reversal process: light into three
emulsion layers, grains catching photons, a black-and-white first developer with its
development inhibitors, re-exposure and three colour developers, bleach and fix, and finally
the finished slide looked at on a light box (or projected) and rebuilt for your screen.

**Monday 400** is a black-and-white negative: developed (pushed to EI 1600 or 3200 if you
like), fixed, and enlarged onto graded silver-gelatin paper. It takes colour or
black-and-white originals. Sunday 64 needs colour: a black-and-white file is turned away with
two choices, print it on Monday 400, or colourise it first (an AI guess, below).

It is a simulation, not a preset: every step is a physical or chemical model, and the films
themselves come from their makers' published measurements (SOURCES.md).

**Note on the fitted film constants.** `data/cache/emulsion_*.npy` holds the colour film's
fitted grain parameters. Refitting them with other versions of NumPy and SciPy lands a little
elsewhere (up to about 1 % in a parameter, 0.6 % in a picture), so the file is kept in the
repository: the look stays the same everywhere. Delete it only to refit on purpose.

## Use

```sh
cd dyeroom
.venv/bin/dyeroom PHOTO.RAF                 # draft, 2400 px, into ./out
.venv/bin/dyeroom PHOTO.RAF --full --tiff   # full resolution, plus 16-bit TIFF
.venv/bin/dyeroom ~/Pictures/raws -o ~/Pictures/dyeroom
```

Any camera raw, or a JPEG/TIFF/PNG. Raws are read with LibRaw. Apple ProRAW from recent
iPhones, a linear DNG compressed with JPEG XL that LibRaw cannot read, is read by Dyeroom's
own DNG reader (`dng.py`), on every system. On a Mac, Apple's RAW engine takes over for other
cameras LibRaw does not know yet, or whose colours in LibRaw disagree with Apple's (checked
on every raw). A folder develops every photo in it, raw preferred
over the camera JPEG of the same frame. Output is a
Display P3 JPEG (`--display srgb` for sRGB), named `<photo>_sunday64.jpg`.

| Option | What it does |
|---|---|
| `--exposure camera` (default) | The slide is as bright as the camera's own rendering of the frame: the exposure you chose |
| `--exposure auto` | Exposure from the scene itself, whatever the camera was set to: corrects under- and overexposed files |
| `--ev 0.33` | More or less exposure on the film on top of that, in stops (slide shooters often gave -1/3) |
| `--light native` (default) | Daylight film sees the scene's real light, taken from the camera's white balance |
| `--light balanced` | Pretend everything was lit by 5500 K daylight (neutral, no tungsten warmth) |
| `--filter auto` (default) | With native light, the colour-conversion filter a photographer would pick: 80-series for tungsten, 82 for slightly warm light, 81 for cold shade, none within 20 mired of daylight or when the flash fired |
| `--filter none` | No filter: tungsten turns deep amber, as on real slide film indoors |
| `--view lightbox` (default) | Slide on a 5000 K light table, seen through a loupe: the slide's own density, with its contrast as the eye sees it in a dim surround |
| `--view projector` | Projected with a quartz-halogen lamp in a dark room: softer, warmer, more shadow detail |
| `--first-developer 1.5` | Longer first development (push). The film gains little speed and loses black density, which is why its maker advised against pushing it |
| `--film monday400` | Black-and-white negative, printed on paper; the options below apply to it, the slide options above do not |
| `--rating 1600` | Exposure index: 400 (box speed), 800 (one stop under, normal development), 1600 and 3200 (push-developed) |
| `--bw-filter 25` | Contrast filter on the lens: 8 yellow, 15 deep yellow, 25 red, 11 yellow-green, 58 green |
| `--grade 3` | Paper contrast grade, 1 (soft) to 5 (hard); 3 by default, 2 is the textbook match for a normal negative |
| `--toning light` | Selenium toner after printing: `light` (1+20) deepens the blacks, `strong` (1+5) turns shadows and mid-tones purplish brown |
| `--format 6x7` | The film format the picture is laid onto: `35mm` (default), `645`, `6x6` or `6x7` (120 film). On a bigger frame each pixel covers more film, so grain is finer and less detail is lost to the emulsion. The picture fills as much of the frame as its shape allows: a 4:3 photograph on 35 mm uses 32 × 24 mm |
| `--no-grain`, `--full`, `--size`, `--tiff`, `-o` | Output control |

On a 12-core Mac a 20 MP raw takes about 10 s and 2.9 GB of memory as a 2400 px draft, and
about 30 s and 6 GB at full resolution (Monday 400: 7 s and 11 s). The first run also builds
two caches (about 10 s). `tools/cost.py` measures this on any machine.

## On your own computer (`local.py`)

`dyeroom` with no photographs starts the web app on this computer and opens it; installed with
`curl -LsSf https://dyeroom.app/install.sh | sh` on macOS and Linux, or on Windows
`powershell -ExecutionPolicy ByPass -c "irm https://dyeroom.app/install.ps1 | iex"` (served from
`dyeroom/web/install.sh` and `install.ps1`), which install uv if needed, then
`uv tool install --python 3.12 dyeroom` (on Windows on Arm, Python for Intel: pi-heif has no Arm
build there), and run `dyeroom shortcut`. CI (`install` in `.github/workflows/tests.yml`) runs
the installer on all three, develops the sample through the lab and opens it from its shortcut
(`tools/smoke_local.py`).

* **Private to the computer** (`DYEROOM_LOCAL=1`, set by `local.py`): it listens on 127.0.0.1
  at a free port. The window opens `/app?key=…` with a key made at each start; the server swaps
  it for an HttpOnly, SameSite=Strict cookie that every request must carry, and refuses any
  request whose Host is not this computer, so no website can reach it through the browser
  (DNS rebinding included). `/` goes straight to the lab.
* **No service rules:** no accounts, fair-use limits (this computer is `DYEROOM_UNLIMITED`),
  legal links or deletion deadlines worth the name (24 hours); the working copies live in the
  system's cache folder and are emptied at each start. The page says photographs stay on this
  computer.
* **Fits the computer:** drafts developed at once = min(4, cores / 4, memory / 8 GB); full size
  one at a time.
* **Starts once, stops by itself:** `lab.json` in the app-data folder holds the port, key and
  process of a running lab, so a second `dyeroom` opens another window on it. An open page says
  it is there every minute (`/api/here`); with no word for 10 minutes and nothing developing,
  the lab stops (on the monotonic clock, so a sleeping computer does not count). `dyeroom stop`
  stops it now.
* **The window:** an app window (`--app=`) in Chrome, Edge, Chromium or Brave when there is one,
  else the default browser. `dyeroom shortcut` adds Dyeroom.app to `~/Applications` (macOS: a
  shell script, built on the computer, so it needs no signing; icon made with `sips` and
  `iconutil`), a desktop entry (Linux) or a Start menu shortcut (Windows: to `pythonw.exe`, so
  no console window, with an icon Pillow makes, written by PowerShell). All run the installed
  Python with `-I`, so a `dyeroom` folder where you happen to be is never imported instead.
* **Windows:** the lab starts detached (`DETACHED_PROCESS`), so closing the terminal leaves it
  running; its tools run with `CREATE_NO_WINDOW`; `dyeroom stop` ends it at once (Windows has no
  gentle signal) and removes `lab.json` itself; memory comes from `GlobalMemoryStatusEx`. Text
  files are read and written as UTF-8 throughout, not in the system's code page.
* **Colourising:** the model is not in the package; `dyeroom colourise-model` fetches it from
  the GitHub release `colourise-model-1` and checks its SHA-256.
* **Releasing:** a tag `vX.Y.Z` runs `.github/workflows/release.yml`, which builds the wheel and
  publishes it to PyPI through trusted publishing (no token stored anywhere).

## Web app

**The site and the lab.** `/` is the home page (`site.py`, `static/site.css`): finished HTML
for people and search engines, with its title, description, canonical address (from
`DYEROOM_PUBLIC_URL`, never guessed), Open Graph and Twitter tags (`static/og/home.jpg`,
1200 × 630, the sample developed on Sunday 64), JSON-LD (WebSite, and WebApplication, free
when there are no accounts) and real icons (`/favicon.ico`, `static/icon.svg`, the
`apple-touch-icon` and `site.webmanifest`, which makes `/app` installable). Its words are
the app's own. The app is at `/app`, marked `noindex` (meta tag and `X-Robots-Tag`, as are
`/api/`, `/auth/`, `/admin` and `/licences`); "Try a sample" links to `/app?sample=1`, which
starts the sample at once. `robots.txt` keeps crawlers out of the API, sign-in and admin, but
not out of `/app` (they must read its noindex); `sitemap.xml` lists the home page, and the
legal pages once they have no gaps (until then they are `noindex` too). An unknown address
gets a page saying so, the API still JSON. The SEO plan is `docs/seo-strategy.md`.

**Films and guides.** `/films/…`, `/guides/…`, `/how-it-works` and `/about` are Markdown files in
`dyeroom/web/content/` (front matter, then headings, lists, tables, links and `[figure]` blocks),
rendered by `content.py` into the home page's frame with a breadcrumb, a byline, Article (or
AboutPage) and BreadcrumbList data, and a 1200 × 630 preview in `static/og/`. `/films` and
`/guides` list them, the sitemap gives each its date, and a link to a page or heading that does
not exist is left as words (the tests list any). The pictures, in `static/guides/`, are the
public-domain raws from raw.pixls.us developed by Dyeroom; the drafts they came from, with the
editors' notes, are in `docs/content-drafts/`. `/app?sample=1&film=monday400` opens the sample on
that film. Pages are read when the server starts: a changed page needs a restart (a deploy).

A workspace in the manner of a grading tool: a top bar with the film menu (each stock
with a line about it), frames left, Add photographs and an Export split button (JPEG, or
TIFF from its menu); a library of photographs on the left with their progress, the viewer
in the middle (Split, Raw, Previous and Slide comparison), an inspector on the right
(Development, Colour, Tones) and a status bar with the lab lamp, progress, keyboard
shortcuts and About. Drop photographs anywhere,
or try the bundled public-domain sample, and watch each one go through the process: the
raw being read under a safelight-red scan, the flash of exposure, the black-and-white
negative forming, cyan, yellow and magenta dye building up under the silver, the bleach,
and the slide arriving in its red Dyeroom mount on the light box. Re-develop with other
settings without uploading again, make finishing adjustments, and export a JPEG or a
16-bit TIFF.

* **Look:** a 1970s photo lab at the desk. Warm charcoal around the photograph (close to
  neutral, so colour is judged without a cast), cream lettering, navy for what is selected,
  safelight red (#ee5339) for what you act on and for anything in the darkroom. Numbered
  sections, selectors with a lit indicator strip, faders with an index line, an exposure scale ticked in thirds,
  and photographs shown as slides in cream card mounts printed in red and black. Type:
  the system's own face, set the way Apple sets its apps: San Francisco on Apple devices
  (SF Pro Display for large text, SF Pro Text for the rest), Segoe UI or Roboto elsewhere;
  sentence-case labels, hierarchy from size, weight and grey, tabular figures for numbers.
  Nothing is downloaded, so visitors' browsers never call a font service.
* **Raw** (left of the divider) is a neutral rendering of the raw file in the manner of
  Adobe's reference renderer (`neutral.py`: the DNG SDK's default tone curve, applied so
  hue is kept, and the camera's colour matrix; no in-camera picture style). "As shot"
  exposure matches the slide's brightness to it.
* **Colour and Tones** hold hue, saturation and light for eight colours and colour wheels
  with a light slider for shadows, midtones and highlights (`adjust.py`, Oklab). The page
  previews them live in WebGL (`static/grade.js`, the same arithmetic; checked to match
  pixel for pixel); exports are made by the server from the full-resolution 16-bit
  result (`POST /api/jobs/{id}/export`) with the colour profile embedded.
* **Nothing develops until asked:** photographs added to the lab come in and wait, "Ready to
  develop", so each can be set up first. Develop (or `D`) develops the frame in view; Develop
  all, in the Frames header and on a waiting frame, sends every frame not developed yet, each
  with its own settings (one still coming in goes as soon as it arrives). Only the sample
  develops at once. Until it is developed a frame shows the photograph as it came in, large,
  with Develop under it, and as its thumbnail: the server makes `preview.jpg` (2048 px) and
  `thumb.jpg` the moment it arrives (`web/preview.py`, in its own process like the developer,
  two at a time): an image file made small, or a raw's own embedded JPEG turned upright (a
  half-size decode when the camera left none of 1000 px, ExifTool's copy when LibRaw cannot open
  the file), kept under `previews/` and deleted with the photograph. `GET /api/uploads/{id}/preview.jpg`
  answers 202 while it is being made, 404 when there is none. The frames list is updated row by row, never rebuilt, so a click on a
  frame is not lost while a roll develops; frames waiting in line ask the server how they are
  doing every 2 s, the one in the developer every half second.
* **Each photograph has its own settings:** a photograph added to the lab starts from the
  defaults, never from what the frame before it was given. The Develop controls show and
  change the frame in view (choosing another frame brings its settings back); with no frame in
  view they set what the next photographs start from, as does a link such as
  `/app?film=monday400`. Settings are not kept between visits (presets are for that); a preset
  chosen applies to the frame in view, or with none in view to the photographs added next.
* **Sharpness and Clarity** (Develop, -100 to 100, `detail.py`): applied to the photograph
  before the film is exposed, on brightness only. A JPEG (or other image file) is first
  checked for the camera's own sharpening, the light and dark rims along every edge that
  phones add: across a few thousand clean edges of the file at its own resolution, the median
  overshoot. If it is sharpened, the gentlest blend towards a blurred copy that takes the rims
  out is used on it (to first order the inverse of the unsharp mask). Measured: Apple's own
  JPEG of an iPhone 12 ProRAW scene about five times the rim of the ProRAW's linear data,
  which is left alone, as are raws; Pixel 8 Pro, Galaxy S23 Ultra and iPhone 15 Pro JPEGs
  are all found sharpened. The page says so under the settings. Sharpness then softens (like
  an older lens) or sharpens on top; Clarity changes local contrast around an edge-preserving
  base (a guided filter about 2 % of the picture wide), so large edges get no halos.
* **Tools one at a time:** the inspector has tabs, Develop, Colour, Tones and Crop, and shows
  one; Colour, Tones and Crop open once a frame is out of the developer (Colour stays shut for
  a black-and-white print). The tab last used is remembered.
* **Undo and redo** (the arrows above the picture, `⌘Z` / `Shift ⌘Z`, `Ctrl` elsewhere): each frame
  keeps the steps of its Colour, Tones and Crop, one per finished gesture (a slider let go, a
  crop drawn, a turn, a preset), up to 100. Developing again and the develop settings are not
  part of it, and a frame removed from the lab cannot be brought back.
* **Panel widths:** drag the inner edge of the frames or the inspector to widen or narrow it
  (arrow keys when it has focus, Shift for larger steps); a double-click puts it back. Widths
  are remembered, and give way while the window is too narrow to leave the picture 420 px.
* **Format:** a menu in Develop: 35 mm, or 6×4.5, 6×6 and 6×7 on 120 film, as `--format`
  above. Changing it lights up "Develop with these settings"; Previous then shows the two
  formats side by side.
* **Crop and straighten** (the Crop tab, or `R`): the whole picture with the crop drawn over
  it; drag inside to move it, the corners (and, for a free crop, the edges) to resize it.
  Aspect: original, free, 1:1, 5:4, 4:3, 3:2 or 16:9, with a button for portrait or landscape.
  Straighten turns the picture up to 45° either way and keeps the crop inside it (an untouched
  crop grows back to the largest that fits); Left and Right (`[` `]`) turn it a quarter.
  Done (or Return, `R` or Escape) finishes, back to the tool used before; the crop is kept as
  it is drawn. Like Colour and Tones, framing belongs to the frame, is
  applied when exporting (`adjust.frame`, the same arithmetic as the page) and needs no new
  development; it is the crop of a scan, so the grain grows with the picture. The viewer and
  the comparisons show the framed picture.
* **On a phone** (860 px and narrower) the page works like a phone photo editor: the picture
  fills the top and never scrolls away, the frames are a strip under it, the open tool sits
  below that and scrolls on its own, and the tools are tabs along the bottom. Held upright,
  the picture runs edge to edge and its area is as tall as the picture at the full width (up
  to about half the screen), the tools take the rest, and the frames leave the strip for a
  Frames tab of their own, first in the bar, as a list with each frame's name and state. The
  home page puts its buttons on the first screen: headline, one sentence, then the buttons. Messages float over the picture; the
  welcome page is set from the left. The page itself never scrolls or bounces (the app is
  pinned to the screen; iOS would otherwise let it be pushed up past the tabs to an empty
  strip), only the panels in it.
* **Looking closer:** pinch (or pinch on a trackpad) to zoom up to two screen pixels per pixel
  of the development, drag (or scroll with two fingers) to look around, double-tap or
  double-click to go in or back out. The zoom stays across Split, Raw, Previous and Slide;
  zoomed in, only the divider itself moves the split. Another frame, or the crop, starts from
  the whole picture.
* **Tablets and foldables:** a tall screen up to 1100 px (an unfolded foldable, a tablet held
  upright) uses the same stacked layout, with the button labels back and the settings in two
  columns. A touch tablet held sideways puts the picture and its frame strip on the left and
  the tools down the right. Half-folded, where the browser reports the hinge (Chrome and Edge,
  `horizontal-viewport-segments` / `vertical-viewport-segments`), each half of the layout fills
  one half of the screen: like a book, picture left and tools right; like a laptop, picture on
  top and tools below. To try it, Chrome's device toolbar has Galaxy Z Fold 5 and Asus Zenbook
  Fold with a folded posture; scripted, `Emulation.setDeviceMetricsOverride` with `mobile: true`
  and a `displayFeature` sets the hinge.
* **Export the roll:** the Export menu's "Roll as JPEG" and "Roll as TIFF" put every
  developed frame, each with its own Colour, Tones and framing, in one ZIP. The page sends the list,
  then downloads the ZIP by a plain link (`GET /api/rolls/<id>.zip`, valid ten minutes) while
  the server makes it frame by frame, so even a roll of TIFFs never sits in memory in the
  browser or on the server. Frames that already left the lab are listed in a note inside.
* **Compare:** Split puts the raw beside the result under a movable divider; Raw and
  Slide (Print for Monday 400) show one each; Previous puts the development before this
  one beside it, both under the same Colour and Tones adjustments, and names the settings
  that changed.
* **Presets:** Save… keeps the development settings and the frame's Colour and Tones
  adjustments under a name: on the account when signed in (moved there from the browser
  on first sign-in), in the browser otherwise. Choosing a preset applies it to the frame in
  view, developing it again when the development changes, and to photographs added next;
  "Apply to every frame" does all of them. Developing the same photograph again is free.
* **Raw and Slide** are a pair: clicking the one already shown switches to the other.
  The full-screen button (or `F`) gives the viewer the whole screen.
* **Keys** (`?` lists them): arrows move through the frames, `1`–`4` choose Split, Raw,
  Previous and Slide, `\` switches between raw and result, holding Space shows the raw,
  `C` cycles the comparisons, `F` full screen, `D` develop (again), `R` crop, `[` `]` turn while
  cropping, `E` / Shift `E` export JPEG / TIFF, `O` add photographs, Delete removes the frame
  from the lab.

Locally:

```sh
.venv/bin/pip install -e ".[web]"
.venv/bin/dyeroom-web             # http://localhost:8000
```

On a Linux server (Docker, x86-64 or ARM):

```sh
docker compose up -d --build      # http://SERVER:8000, files kept in the dyeroom-data volume
```

Put it behind your usual reverse proxy for HTTPS, and allow large request bodies there
(raw files are 20-80 MB; nginx: `client_max_body_size 400m;`). `docker-compose.yml` opens the
port to that server only (`127.0.0.1:8000`) and so believes the proxy's `X-Forwarded-For`
(`DYEROOM_TRUSTED_PROXIES=*`): fair-use limits count each visitor's own address. If you
publish the port any other way, set `DYEROOM_TRUSTED_PROXIES` to the proxy's address, or
anyone could claim any address.

Each photo is developed in its own process, one at a time by default, so a huge raw
cannot take the server down and memory is returned after every job. Settings, from the
environment (see `docker-compose.yml`):

| Variable | Default | Meaning |
|---|---|---|
| `HOST`, `PORT` | 127.0.0.1, 8000 | where the app listens: this computer only, unless set to 0.0.0.0 (the Docker image does) |
| `DYEROOM_WORKERS` | 1 | photos developed at once; each needs about 3 GB for a draft, 6-7 GB at full size (20 MP), so full-size developments go one at a time while drafts use every worker |
| `DYEROOM_FULL` | 1 | `0` allows drafts only (for small servers) |
| `DYEROOM_DRAFT_EDGE` | 2400 | long edge of drafts in pixels |
| `DYEROOM_MAX_MB` | 400 | largest upload; above 32 MB a photograph goes up in 32 MB parts (see Security) |
| `DYEROOM_IDLE_MINUTES` | 30 | photographs are deleted this long after the page stops using them, at once when it closes |
| `DYEROOM_KEEP_HOURS` | 3 | and at the latest this long after upload |
| `DYEROOM_TIMEOUT` | 900 | seconds before a job is stopped |
| `DYEROOM_USER`, `DYEROOM_PASSWORD` | unset | when both are set, the site asks for them |
| `DYEROOM_DATA` | `/data` in Docker | accounts; the only thing kept |
| `DYEROOM_WORK` | `/work` in Docker (a disk volume; a tmpfs on a big server) | where photographs are held while they are worked on |
| `DYEROOM_SAMPLE` | `samples/sample-olympus-e-p7.orf` | raw behind "Try a sample" (CC0, raw.pixls.us); the button hides when the file is missing |
| `DYEROOM_TRUSTED_PROXIES` | `127.0.0.1` | the reverse proxy whose `X-Forwarded-For` is believed (`*` in docker-compose, see above) |
| `DYEROOM_ACCESS_LOG` | `0` | `1` logs every request with its address; off, the server keeps no log of visits |
| `DYEROOM_ADMIN_EMAILS`, `DYEROOM_ALERT_URL`, `DYEROOM_SERVER_EUR_MONTH` | unset | see "Running it" |
| `DYEROOM_LEGAL_*`, `DYEROOM_CONTACT_EMAIL`, `DYEROOM_HOSTING` | unset | see "Legal pages" |

Run a single server process (the job queue lives in memory); scale with
`DYEROOM_WORKERS`, not with more web processes. After a restart, jobs that were cut off
are marked failed and can be developed again.

The queue is fair: photographs wait in one line per person (account, or address without
accounts), and the developer takes one from each person in turn, so someone who drops a roll
of 36 does not hold up the next person's single frame. Each waiting frame shows how many are
ahead of it and, once that is more than a minute, about how long until it goes in (from the
median time of this server's recent developments).

### Photographs are not kept

Dyeroom is a one-time service: a photograph exists on the server only while someone works
on it. The upload, the developed files and everything else made from it are deleted

* at once when the page closes or reloads (it tells the server as it goes), or when the
  Clear button in Frames is pressed;
* after `DYEROOM_IDLE_MINUTES` (30) without the page using them, should the page vanish
  without a word (the open page says it is still working every two minutes);
* `DYEROOM_KEEP_HOURS` (3) after upload at the latest, however busy;
* when the server restarts: the photographs folder is emptied at start.

A photograph still in the developer is deleted the moment it comes out. Developing again
needs the photograph to be still there; after it is gone, it has to be added again (and
with accounts on, that counts as a new photograph).

Photographs live under `DYEROOM_WORK`, emptied at every start. On a small server (16 GB)
that is a disk volume, as `docker-compose.yml` sets it. On a server with memory to spare,
mount memory there instead (a tmpfs, 8 GB; the lines are in `docker-compose.yml`) and they
never touch a disk: uploads being received spill there too, not to the system's temporary
folder, and so do the developer's own temporary files. `/api/health` reports
`photos_in_memory`, and the page and privacy notice say "in the server's memory, never on a
disk" only when that is true. With a tmpfs, keep swap off (Hetzner Cloud servers have none),
or memory can be written out to disk. Accounts and the payment ledger in `DYEROOM_DATA` are the only
things kept; they hold random photograph ids for billing, never pictures or file names. The
page and About box say this to visitors, with the times above.

### Free, with donations

The default, and how Dyeroom launches: no accounts and nothing to buy. Every film, setting
and kind of export is open to everyone; fair use is counted per address (below). Set
`DYEROOM_DONATE_URL` (`https://buymeacoffee.com/geoyanj` in `docker-compose.yml`) and the
page shows "Free to use · Support it with a coffee" among the welcome facts, a "Free to use"
part in About and a "Buy me a coffee" link in the status bar: plain links, no script from
Buy Me a Coffee. The terms and privacy notice drop everything about accounts and payments
(`<!--if accounts-->` passages in `legal/*.html`), say that a donation buys nothing, and name
Buy Me a Coffee as the only other party, for those who give; there is no refund policy, and
the site sets no cookies. After the fifth of someone's own photographs is developed in a
browser (the sample and developing again don't count), a card in the corner asks for a
coffee, with that frame in a small mount; again at 40 and 120, then never, and never again
once they have clicked through to give. The count lives in the browser (`dyeroom-coffee`),
as the privacy notice says. The payment code stays: `DYEROOM_ACCOUNTS=1` turns it back on.

### Accounts and payments

Off by default (see above). With `DYEROOM_ACCOUNTS=1`:

* Anyone can try the sample. Developing your own photographs needs a sign-in with Apple or
  Google (`sso.py`, OpenID Connect; no passwords are stored or sent).
* A new account gets 5 photographs free (`DYEROOM_FREE_FRAMES`). A photograph costs one
  frame the first time it is developed. Developing it again with other settings, at full
  size, or exporting it costs nothing more, and if it cannot be developed the frame comes back.
  Adding the same file again later is free too, for `DYEROOM_FINGERPRINT_DAYS` (30): the
  account keeps a fingerprint of each file, an HMAC-SHA-256 of its bytes keyed with a
  secret kept in the database (taken in from `fingerprint.key` by older installs) and the
  user's id. It cannot be turned
  back into the picture or matched across accounts, and it is erased after those days or
  with the account. Out of frames, the page hashes the file itself and asks first, so a
  free one is still uploaded; the server checks the real hash before developing.
* After that: a **roll of 36** frames bought once (they do not expire), or a **monthly** or
  **yearly plan** for up to 1,000 photographs a month (`DYEROOM_PLAN_CAP`). Frames are only
  used once a plan's month is full.
* Paddle is the merchant of record (`billing.py`). It runs the checkout on the page, charges
  VAT and sales tax, sends receipts and handles refunds; customers manage plans and receipts
  in Paddle's customer portal. The server learns what was bought from signed webhooks.
* Accounts live in `DYEROOM_DATA/accounts.db` (SQLite; see "Backups"). Every change to a
  balance is a row in its ledger. For support: `python -m dyeroom.web.accounts show EMAIL`
  and `python -m dyeroom.web.accounts grant EMAIL 36 "note"` (negative to take frames back).
* Refunds: when Paddle refunds a roll (or a chargeback goes through), the webhook takes the
  frames of it not yet used back off the account. A partial refund, or a refunded plan
  payment, raises an alert instead: take frames back by hand, or cancel the plan in Paddle.
* A few new accounts a day from one address get the free frames
  (`DYEROOM_NEW_ACCOUNTS_PER_DAY`, 3); more still sign in, without them.

Setting it up:

1. **Address.** `DYEROOM_PUBLIC_URL=https://your.domain`. HTTPS is required (Apple will not
   return to plain HTTP).
2. **Google.** In the Google Cloud console, under APIs & Services, set up the OAuth consent
   screen (name, logo, privacy policy link), then create an OAuth client ID of type *Web
   application* with the redirect URI `https://your.domain/auth/google/callback`. Set
   `DYEROOM_GOOGLE_CLIENT_ID` and `DYEROOM_GOOGLE_CLIENT_SECRET`.
3. **Apple.** In the Apple Developer account: an App ID with *Sign in with Apple*; a
   Services ID (for example `app.dyeroom.signin`) with Sign in with Apple, grouped under that
   App ID, with the domain and the return URL `https://your.domain/auth/apple/callback`; and
   a key with Sign in with Apple (download the .p8 once). Set `DYEROOM_APPLE_CLIENT_ID` (the
   Services ID), `DYEROOM_APPLE_TEAM_ID`, `DYEROOM_APPLE_KEY_ID` and
   `DYEROOM_APPLE_PRIVATE_KEY_FILE` (or the key's text in `DYEROOM_APPLE_PRIVATE_KEY`).
4. **Paddle.** Start in the sandbox (sandbox-vendors.paddle.com). Make one product with three
   prices: one-time (the roll), monthly and yearly. Under Developer tools, create a
   client-side token and an API key, and a notification destination at
   `https://your.domain/api/billing/webhook` with `transaction.completed`, the
   `subscription.*` events and `adjustment.created` / `adjustment.updated` (refunds). In checkout settings, set the default payment link to
   `https://your.domain/`. Then set `DYEROOM_BILLING=paddle`, `DYEROOM_PADDLE_ENV`
   (`sandbox` or `production`), `DYEROOM_PADDLE_CLIENT_TOKEN`, `DYEROOM_PADDLE_API_KEY`,
   `DYEROOM_PADDLE_WEBHOOK_SECRET`, `DYEROOM_PADDLE_PRICE_ROLL`, `_MONTHLY`, `_YEARLY`
   (the `pri_` ids) and, so the page shows the same prices as Paddle, `DYEROOM_PRICE_ROLL`,
   `_MONTHLY`, `_YEARLY` (defaults €5, €5 a month, €45 a year). Before going live Paddle
   reviews the site: it needs visible prices and the three legal pages (see "Legal pages").
   Try the checkout in the sandbox once: the page's Content-Security-Policy allows Paddle's
   script and frames from `*.paddle.com`, and the checkout should open without errors in the
   browser console.

To try it all locally without any of those accounts:

```sh
DYEROOM_ACCOUNTS=1 DYEROOM_DEV_LOGIN=1 DYEROOM_BILLING=test .venv/bin/dyeroom-web
```

This adds "Continue as a test user" to the sign-in, and purchases succeed at once without
charging anything. The test user is refused on an `https://` public address or with Paddle
billing, whatever `DYEROOM_DEV_LOGIN` says. Tests (frames, plans, webhooks, refunds,
backups, sign-in tokens, the queue, limits, the roll ZIP, legal pages):
`.venv/bin/pip install -e ".[test]"`, then `.venv/bin/python -m unittest discover -s tests`.

### Running it

* **Admin page.** `/admin`, for the accounts in `DYEROOM_ADMIN_EMAILS`, or, without
  accounts, with `DYEROOM_ADMIN_PASSWORD` (the browser asks; user `admin`; kept in `.env` on
  the server). Without either it answers 404:
  the queue now, photograph space, backups, alerts, whether the legal pages are complete;
  developments over the last day, week and month (failures, median and 90th-percentile time,
  waiting time, processor time, peak memory, how many the workers can do in an hour, and the
  server cost per 1,000 frames from `DYEROOM_SERVER_EUR_MONTH`); accounts, rolls, plans and
  refunds; the last week's failures with their errors; recent alerts; and the steps people
  take, counted with nothing about who: tried the sample, added a photograph, opened the
  checkout, bought a roll or started a plan. Statistics
  (`DYEROOM_DATA/stats.db`, kept 90 days) never hold pictures, file names or accounts. The
  same in a terminal: `python -m dyeroom.web.stats`.
* **Alerts.** Set `DYEROOM_ALERT_URL` to an ntfy topic (`https://ntfy.sh/<a long secret
  topic>`, and the ntfy app on your phone), or a Slack or Discord webhook. You hear about:
  three failed developments within 15 minutes, a development stopped for time or memory, a
  photograph waiting more than 10 minutes, photograph space over 90 % full, a payment
  notification with a bad signature, a paid roll or plan with no account to go to, refunds
  to finish by hand, a failed daily backup, and a restart that cut developments off. One of
  each kind an hour at most. `python -m dyeroom.web.alerts "test"` sends a test.
* **Fair use** (`limits.py`, all per person, in memory only): 120 photographs added and 60
  developments an hour (a full-size one counts as four), 120 exports an hour, 40 waiting for the developer and 4 GB held in
  the lab at once; 30 sample developments an hour per address; 400 waiting in the whole lab.
  The page waits and tries again by itself when told to (HTTP 429 with Retry-After), saying
  "Waiting to go in" and why. `DYEROOM_UNLIMITED` (in the server's `.env`) lists addresses or
  account ids spared all of these but the lab-wide 400, comma-separated: the owner at work.
  The counts live in the process, so a change needs a restart, which also empties the lab.
* **Cost and size.** `python tools/cost.py --eur-month 40 --full` develops the sample (or
  your raws) exactly as the server does and prints wall time, processor time, peak memory and
  the cost per 1,000 frames. On a 12-core Mac: drafts 10 s and 2.9 GB, full size 31 s and
  6 GB; server time is about €0.01-0.04 per 1,000 frames at €40 a month. Memory, not
  processor time, decides the server: each worker needs 3-7 GB, plus the tmpfs for
  photographs. One worker does about 390 drafts or 115 full-size frames an hour.

### Backups

`accounts.db` is the only thing Dyeroom keeps: accounts, frames bought, plans, presets and
the fingerprint key (kept inside it, so a restore keeps free re-adds working).

* **Daily copy.** The server copies it to `DYEROOM_DATA/backups/accounts-<date>.db` once a
  day (SQLite's online backup, checked for integrity) and keeps the copies
  `DYEROOM_BACKUP_DAYS` (14). A copy now: `python -m dyeroom.web.accounts backup [FOLDER]`.
  This guards against mistakes, not against losing the server.
* **Off the server.** `docker compose --profile backup up -d` starts Litestream
  (`deploy/litestream.yml`), which streams every change to S3-compatible storage (Backblaze
  B2, Cloudflare R2, Hetzner Object Storage, AWS) within seconds and keeps 30 days of
  history. Fill in the `backup` service's `LITESTREAM_*` settings first. `/admin` shows when
  it last copied. Tested with Litestream 0.3.13 while a process held the database open as the
  server does, with an admin command from a second process in between: the restore had
  every change. (With nothing holding it open, SQLite removes its write-ahead log on close
  and Litestream misses changes, so run it beside the server, as the compose file does.)
* **Restore:** stop Dyeroom, then
  `docker compose run --rm backup restore -o /data/accounts.db /data/accounts.db` (move the
  damaged file away first), or copy a daily copy over `accounts.db`; start Dyeroom.

### Legal pages

`/terms`, `/privacy` and `/refunds` are public (GET and HEAD, no sign-in), linked under the
welcome screen, in About, the sign-in sheet and the Buy film sheet. They are drafts written
from what the app really does (texts in `dyeroom/web/legal/`), checked against Paddle's
requirements: the seller's legal entity, "Paddle.com is the Merchant of Record for all our
orders", a refund window of 14-90 days through paddle.net with no "all sales final", and a
privacy notice with controller, purposes and legal bases, retention, recipients, transfers,
cookies and GDPR rights answered within a month. **Have a lawyer read them before launch.**
They need, from the environment: `DYEROOM_LEGAL_NAME` (the registered business, not
"Dyeroom"), `DYEROOM_LEGAL_ADDRESS`, `DYEROOM_CONTACT_EMAIL` (also shown as Contact in the
app), `DYEROOM_LEGAL_COUNTRY` (governing law), `DYEROOM_HOSTING` (who hosts the server and
where) and optionally `DYEROOM_BACKUP_HOSTING` and `DYEROOM_REFUND_DAYS` (30). Until they
are set the pages show the missing names as red gaps, `/api/health` says
`"legal_pages": false`, and the server warns at start with Paddle billing on.

### Security

* Every response carries a Content-Security-Policy (scripts only from this server and
  Paddle, no framing of the site), `nosniff`, `X-Frame-Options: DENY`, a referrer policy,
  and HSTS on https.
* Requests with a body must state their length: chunked bodies are refused (they could fill
  the memory before any check), JSON bodies are capped at 2 MB and uploads at
  `DYEROOM_MAX_MB`.
* A photograph over 32 MB goes up in parts: `POST /api/uploads/start` (name and size,
  checked then exactly as a whole upload is before it is sent), `PUT
  /api/uploads/<id>/<n>` for each 32 MB part in order, `POST /api/uploads/<id>/finish`. Each
  request stays under the 100 MB that Cloudflare's free and Pro plans let through, and a
  dropped connection costs one part: the page sends it again, up to four times, and a part
  that arrives twice is added once. Parts count towards the space a person holds, and an
  upload abandoned half-way is swept like any idle one.
* Developments run in their own process without the server's secrets (keys, tokens and
  passwords are taken out of its environment), so a file crafted against a decoder finds
  nothing to steal. Pictures over 160 megapixels are refused before they are decoded in full.
* Finishing adjustments from the page are checked: anything not a finite number is dropped.
* Sessions are random tokens stored only as hashes; sign-in checks the provider's signed
  token (issuer, audience, expiry, nonce) and a one-time state; webhooks check Paddle's
  signature and time. Cookies are `HttpOnly`, `SameSite=Lax`, `Secure` on https.
* Uploaded file names are reduced to safe characters and can never start with `-`;
  ExifTool and the decoders get absolute paths only.
* Dependencies: `pip-audit` found no known vulnerabilities (1 November 2026). The Docker
  image installs the newest releases when it is built: rebuild it now and then.

On Linux, raws are decoded by LibRaw, and linear DNGs it cannot read (ProRAW in JPEG XL) by
`dng.py` (Apple's engine is macOS-only). Other cameras newer than LibRaw get a clear message
asking for a DNG or TIFF; Adobe DNG Converter makes DNGs LibRaw can read.

## The process, stage by stage

**1. Capture** (`capture.py`). The raw is demosaiced linear in Rec.2020 with the camera's
white balance (LibRaw; Apple Core Image via `macraw.swift` when LibRaw cannot read the file
or its colour data disagrees with Apple's by more than about 20 %). Exposure is placed where the photographer meant it: mid-tones are matched
to the camera's own embedded JPEG. Digital sensor noise, which film never saw, is removed
in a shot-noise-stabilised space (colour strongly, luminance lightly), with the strength
measured from each image. The light the camera balanced for is turned into a colour
temperature. An image file (JPEG, HEIC, TIFF, PNG; HEIC through pi-heif, decode only, turned
upright as the file says) is read as Display P3 when its ICC profile is named so (Apple's
spells the name in UTF-16) or a HEIF's colour primaries say P3, otherwise as sRGB; HDR
HEIFs (PQ or HLG) are refused. It already carries the camera's tone curve, an S
nearly as steep as the film's: laid on film as it was, its shadows went black (phone JPEGs:
mid-tone contrast 1.4-1.7 times the file's, up to 12 % of the frame black). So its pixels are
turned back into scene light first (`neutral.unrender`): each pixel's luminance through the
typical camera curve (`TYPICAL_CAMERA`, 28 photographs from 15 makers) backwards, flattened by
the film's extra steepness (`FLATTER`, 0.85), with the pixel's colour (its channel ratios)
kept as the file has it. The slide then keeps the file's contrast (0.94-1.08 times) and its
colour comes out a little richer than the file's, as the film's (chroma 1.1-1.3 times; flattening
each channel instead dulled it to 0.7-0.95). Monday 400 prints come close to what a raw gets. An image file's own sharpening is
measured here and taken out just before the
film is exposed, with the photographer's Sharpness and Clarity (`detail.py`, see the web
app above); the Raw side of the comparison keeps the file as it was.

**2. Light on the film** (`spectra.py`, `process.layer_exposure`). Each pixel becomes a
reflectance spectrum like those of real materials (Otsu, Yamamoto & Hachisuka 2018: basis
spectra learned from measured reflectances, per region of chromaticity). Real blue
materials keep rising into the far red, where the film's red layer still sees, and real
reds stay out of the green layer; with the smoothest-possible spectra used before, blues
came out cyan and reds orange. A camera cannot tell a blue sky (no deep red) from blue
paint or cloth, so blues take a mix that is mostly the smooth spectrum (Jakob & Hanika
2019, kept from rising into the violet, where saturated reds would otherwise turn pink).
Colours beyond what real surfaces reflect also fall back to the smooth spectrum, and very
bright ones borrow the spectral shape of the same colour at a reflectance of at most 0.6
(near 1 the only spectra that still reach a saturated blue grow a red tail, and bright
skies turned purple). Each surface is recovered as it looks under the scene's own light
(black body below 4000 K, CIE daylight above): the white-balanced colour is what the
surface shows in that light, not under daylight, which halves the colour error of
lamplit scenes (from about 5 to about 2.5 ΔE2000 on 68 measured surfaces at 2700-3200 K;
lattices are solved at 2400-4500 K and blended in mired). The spectrum is lit by that
light, passes the conversion filter and the lens, and is integrated against the spectral
sensitivity of each film layer:
`H_k = ∫ R(λ) E(λ) F(λ) S_k(λ) dλ`.
Metering follows the reversal-film ISO speed method: the speed point is the geometric
mean of the exposures giving density 0.2 and 2.0 above minimum, `S = 10 / H_m`, and a
reflected-light meter (K = 12.5) puts a metered grey at `0.81 H_m`. Emulsion batches are
balanced so that grey reproduces neutral under 5000 K, as its maker did.

**Exposure** (`exposure.py`). A slide photographer judged exposure by the slides it gave.
Here the film exposure is chosen so that the finished slide, as seen, is as bright as a
neutral rendering of the raw file (`neutral.py`, in the manner of Adobe's reference
renderer), as closely as the film allows: least squares in CIE lightness over the whole
frame, through the film's tone scale and the chosen viewing. With `--exposure camera` the
reference has the brightness the camera chose (its metered grey shown where Camera Raw
shows it, about half a stop lighter than the camera's own JPEG); with `--exposure auto` the
scene is placed like a centre-weighted averaging meter would place it: its mean log
luminance about 0.65 stop below a grey card (12 % grey, the classic average scene, and
where the cameras we tested put it on average). Auto gives the same slide whether the file
was two stops under or over. A JPEG or TIFF file is its own reference. On 39 test frames
from 16 makers the chosen exposure is within 0.3 stop of the meter.

**3. Reciprocity and irradiation.** Long exposures lose speed per layer (the data sheet: nothing
to 1/100 s, +1/3 stop and CC05R at 1/10 s; the maker calls 1 s and longer "not recommended",
and the loss is continued at the same rate per decade, a guess that turns long exposures
cyan-green). Light scattering inside the emulsion blurs the exposure with a roughly
exponential spread (MTF `1 / (1 + (f / 26.7 c/mm)²)`), fitted together with the
first developer's edge effects to the data sheet's MTF (`tools/mtf.py`: within 0.06 from 2.5 to
80 cycles/mm, 123 % near 10 cycles/mm, 31 % at 50).

**4. Latent image** (`film.py`). Silberstein's quantum (hit) theory: a grain of
cross-section `a` absorbs `n` photons with Poisson probability
`P(n) = λⁿ e^-λ / n!`, `λ = a H`. Each layer is a blend of two emulsions with
log-normal grain sizes, fitted so the model reproduces the data sheet's characteristic curves to
within 0.004 in developed fraction.

**5. First developer** (`process.first_developer`). First-order kinetics: a grain carrying
`n` photons develops at rate `k(n) = k_latent · r^(4-n)`, so after time `t` it has
developed with probability `1 - e^(-k(n) t)`; unexposed grains only fog, after an
induction period. Developing silver releases iodide, which slows development in the same
layer and its neighbours (interimage effect: more saturated colour) and diffuses
sideways about 40 µm (adjacency effect: crisper edges). Inhibition shifts the effective
exposure, `log H_eff = log H - Σ_j M_jk Ag_j`. Because the data sheet's curves are measured on
grey scales where inhibition already acts, the intrinsic curves are recovered first.

**6. Reversal and colour development** (`process.reversal_and_dyes`). What the first
developer left behind becomes dye: red light through the base fogs the red layer and the
cyan developer couples it; blue light from the top fogs the blue layer (the yellow filter
layer shields the green) and the yellow developer couples it; the magenta developer
carries a fogging agent and dyes whatever is left. Grain is the binomial statistics of
the remaining grains, `σ = √(R(1-R)/N)`, with `N` set so that the slide matches the data sheet's
RMS granularity of 10 (48 µm aperture, Selwyn's law for other areas).

**7. Bleach and fix.** All silver, including the yellow filter layer, is removed. The
slide is three dyes on a base: `D(λ) = Σ c_k ε_k(λ) + D_base(λ)`.

**8. Viewing** (`viewing.py`). Light through the slide, `T(λ) = 10^-D(λ)`, under the light
table (D50, the slide surrounded by the table's light) or the projector lamp (3350 K
quartz-halogen behind a KG3 heat filter, dark room); stray light; the eye's adaptation to
the light's colour (CAT16) and to the slide itself. A metered grey card sits near density
1 on the slide, where only a tenth of the light gets through, yet looking at a slide the
eye settles on its mid-tones and that grey reads as mid-grey while clear film glows like a
highlight. So the slide's light is scaled until a metered grey on a normally processed
slide looks as light as the neutral raw rendering shows a grey card, and whatever is brighter than half of
the screen's white rolls off smoothly so clear film still meets it. That keeps the film's
steep, dense mid-tones (the slide film's contrast) instead of lifting the picture by
overexposing the film into its soft toe. The appearance of every colour (CIECAM16
lightness, chroma, hue) under the slide's viewing conditions is rebuilt for a monitor in
a normally lit room. The projector's room is dark; the light box's surround counts as dim
for lightness (`viewing.SURROUNDS["Light box"]`): Hunt's appearance model puts large
transparencies on light boxes with television in a dim room for brightness induction, and a
loupe or a masked viewer shows the slide against dark. The data sheet's curves are steep (gradient 1.8
at a metered grey, 2.1-2.2 a stop or two under), and with the room's surround the screen
showed all of it: mid-tones 1.18-1.36 times as steep as the neutral rendering on seven CC0
raws, with up to 15 % of a frame black. With the dim surround they are 1.05-1.19 times as
steep and no shadow is crushed; colour induction is kept at the average room's, so colour is
unchanged. Lightness and chroma are matched relative to the viewing light, as a
viewer adapts to a light box or a screen: carrying over the light box's absolute
colourfulness (Hunt effect) would add about 16 % colour that no scan or print of a slide
shows, so it is not done. Colours beyond Display P3 keep their hue; those
lighter than the display's most colourful colour of that hue give up some lightness
along with chroma, so bright yellows stay vivid instead of washing out toward white.

## What is measured, what is modelled, what is assumed

* **Measured (the data sheets, SOURCES.md):** layer spectral sensitivities, characteristic
  curves (Status A), dye spectral densities and MTF, digitised from the data sheet's vector
  drawings (`tools/digitise_sunday64.py`); RMS granularity 10; daylight balance and filter
  recommendations; reciprocity behaviour; the process's step order. The curves are split into
  the three dye amounts by solving, at every exposure, for the dyes that give the data sheet's three
  Status A readings through the measured dye spectra; the base is a smooth density meeting
  the data sheet's minimum densities.
* **Checked against the data sheets:** the film reproduces the data sheet's Status A curves
  within 0.03, rates ISO 64 on its lux-second axis, reaches a visual Dmax of 3.18 (the maker's
  IT8 target on this film: 3.22), its three dyes can make every one of the 264 colours
  measured on that target (mean 0.24 ΔE2000), and its MTF follows the data sheet's within 0.06
  (`tests/test_film.py`, `tools/mtf.py`). Not settled: the maker's 1999 target shows green
  light greys and magenta shadows that its data-sheet curves do not; the film keeps a
  neutral mid-grey (5000 K) and follows the data sheet.
* **Physics with fitted parameters:** grain populations and development kinetics (fitted
  to the curves), grain count (fitted to RMS 10), grey balance (fitted to 5000 K neutral).
* **Assumed, documented in code:** interimage strength (the maker never published it; set so
  colours reach the film's familiar density and saturation, see `tools/chart.py`;
  stronger coupling for reds or blues dulls yellows, because greys are kept neutral),
  the mix of smooth and natural spectra for blues,
  dye-cloud size, viewing luminances, the reciprocity loss beyond 1/10 s. Nothing checks
  the scene-to-slide step against a real slide of a known scene: no such pair is public.
* **Calibrated:** how far the eye adapts into the slide (a metered grey card on a normal
  slide looks as light as the neutral raw rendering shows it, L* 57.5, matched to Camera
  Raw on the owner's Fujifilm files) and where auto exposure puts an average scene (from
  the embedded JPEGs of 28 photographs from 15 camera makers).
* **Limits:** a camera records three numbers per pixel, not a spectrum, so the spectral
  reconstruction is a plausible guess. Against measured reflectances (ColorChecker, CIE
  and NIST test colours) the layer exposures are off by 0.06 log on average and up to
  0.24 in the red layer for a few saturated colours. Mixed lighting
  is treated as the single light the camera balanced for.
* **Flash** is read from the file's EXIF (DNG, NEF, ARW, CR2, PEF, ORF, and the camera
  JPEG inside RAF and RW2; not recorded in the CR3, 3FR and IIQ samples). Electronic flash is
  daylight-balanced like the film, so no conversion filter is chosen and room light around
  the subject goes warm, as on the real film. The flash-lit subject gets a burst of about
  1/1000 s, so long-exposure reciprocity loss is not applied. Exposure needs no special case:
  matching the camera's rendering keeps flash-lit subjects at its brightness, and auto
  exposure scales the whole frame, so the fall-off between subject and background stays.

## Monday 400, stage by stage (`mono.py`)

Data: the maker's data sheet (SOURCES.md). The curves were digitised from its vector
drawings (`tools/digitise_monday400.py`, into `data/monday400.json`); the digitised contrast
index at 6 3/4 minutes is 0.557, where the data sheet's text says 0.56.

1. **Exposure.** Each pixel's reflectance spectrum (as for Sunday 64) times the light, the
   lens filter and the film's spectral sensitivity: strong in violet and blue, cut off near
   660 nm. A metered grey card gets 8.125 / EI lux seconds. Per unit of luminance, tungsten
   light exposes the film 0.78 as much as daylight; the maker rated it 320 in tungsten against
   400 in daylight (0.80). Filters are gels shaped so their daylight factors on this film
   are the data sheet's (8: 2, 15: 2.5, 25: 8, 11: 4, 58: 6); the tungsten factors that follow (1.5,
   1.7, 4.6, 3.4, 5.4) agree with the data sheet's (1.5, 1.5, 5, 3, 6). Long exposures lose speed as
   the data sheet tabulates (+1 stop at 1 s, +2 at 10 s, +3 at 100 s).
2. **Developer.** The data sheet's characteristic curves in the standard developer after 6, 8, 10 and 12 minutes (large
   tank, 20 C), interpolated for the time used: 7 3/4 min for EI 400 and 800, 10 3/4 for
   EI 1600, 12.4 for EI 3200 (the data sheet gives 3200 only for the small tank; scaled by its
   ratio). Longer development lifts shadows proportionally more than highlights, so the
   measured curves are used rather than one curve scaled. Light spreads in the emulsion
   (3.8 um) and the developer works harder at edges next to thin areas (adjacency effect,
   0.16 over 46 um): both fitted to the data sheet's MTF, including its 110 % response near
   8 cycles/mm. Silver grain: RMS granularity 17, variance growing with density (Nutting)
   and falling with area (Selwyn).
3. **Stop and fix.** The characteristic curves are of fixed film, so the undeveloped
   halide is already gone; the animation shows it clearing.
4. **Printing.** The negative is enlarged onto glossy fibre paper (density 0.05 to 2.10)
   through a diffusion enlarger. The grade is the log exposure range the paper accepts
   (ISO 6846 mid-points: grade 2 about 1.05). The print exposure is chosen like a test
   strip: the print's lightness matches the neutral rendering of the raw as closely as the
   paper allows, so rating and push change contrast, shadows and grain, not brightness.
   Compensation shifts both the film exposure and the print's brightness. Grade 3 is the
   default (punchier than the textbook grade 2).
5. **Selenium toning** (optional), after the print is made. Selenium turns silver into
   silver selenide, densest silver first. `light` (a 1+20 bath) converts the deepest
   shadows: blacks get denser, colour barely changes. `strong` (1+5) reaches the
   mid-tones, which turn purplish brown. the makers describe this only in words; the
   amounts are assumed (Dmax +0.12 fully toned, selenide tone Lab a* +5, b* +1).

Assumed rather than measured: the selenium amounts, the paper curve's shape between the ISO points (long toe,
short shoulder), the paper and silver tone (barely warm), the shoulder beyond the data sheet's
plotted range, and the filter gels' exact shapes (their factors are the data sheet's).

## Metadata (`metadata.py`)

Every file you download (the slide or print as developed, and adjusted JPEG and 16-bit TIFF
exports, from the web app and the command line) carries the original's metadata unchanged:
camera, lens, exposure, dates, GPS, copyright, captions, keywords and maker notes, copied
with [ExifTool](https://exiftool.org) from the raw or image you uploaded. The original is
only read. Left out are only the tags that describe the original's pixels and would be
false for the developed picture: orientation (it is already upright), pixel dimensions,
embedded thumbnails and previews, the colour profile and colour-space tags (the export
carries its own profile), and Camera Raw settings. Nothing is ever drawn on the picture.

A colourised photograph also gets one machine-readable tag, IPTC Digital Source Type
`compositeWithTrainedAlgorithmicMedia` ("Edited using Generative AI"), in its XMP, so
software can tell the colours were made by AI. Install ExifTool (`brew install exiftool`;
the Docker image includes it); without it exports carry no copied metadata.

## Colourising black-and-white originals (`colourise.py`)

A black-and-white file has no colour in it, so any colour is invented: this is an AI guess,
labelled as such in the app ("Colours guessed by DDColor") and in the exported file's
metadata (above). DDColor (Kang et al., ICCV 2023;
code and weights Apache-2.0, so usable commercially), tiny model, run by ONNX Runtime on
the CPU: it sees the picture at 512 x 512 and predicts CIELab a* and b*. The colours are
enlarged and laid under the photograph's own luminance, so tones and detail stay the
original's; the result then goes onto Sunday 64 like any colour photograph. The comparison
still shows the black-and-white original.

The model has to be converted once (it needs PyTorch, which the server does not):

```sh
pip install torch onnx onnxruntime huggingface_hub       # in a separate environment
git clone https://github.com/piddnad/DDColor && git -C DDColor checkout 2adb63f
python tools/export_ddcolor.py DDColor dyeroom/data/cache/ddcolor_paper_tiny.onnx
```

The script checks the converted model against PyTorch's output. The server needs
`pip install -e ".[web,colourise]"` (ONNX Runtime) and finds the file there, or wherever
`DYEROOM_COLOURISE_MODEL` points (in Docker: mount the file and set that variable).
Without the file the option is simply not offered.

## Diagnostics

* `tools/chart.py [--view lightbox] [--inhibition-scale 1]` puts a grey scale and a
  ColorChecker (measured spectra) through the film and prints tone and colour numbers.
* `tools/trace.py PHOTO.RAF [lightbox|projector] [camera|auto]` prints every stage's
  statistics for one photo, including the exposure chosen.
* `tools/probe.py PHOTO.RAF 0.5,0.5` follows chosen pixels through exposure.
* `tools/sample_raws.txt`: 17 public-domain raws (raw.pixls.us, CC0) used for testing.

## Tested cameras

Fujifilm X100S and X-T50, Canon EOS R6 Mark III, Nikon Z fc, Sony A7 V, Panasonic FZ83,
OM System OM-5 II, Olympus E-P7, Pentax K-1 II, Ricoh GR IIIx, Leica M10-R, Hasselblad
CFV-50c, Phase One P40+, Sigma fp, iPhone XS, Pixel 7 Pro, Samsung Galaxy S22 (SM-S901E), DJI FC4382 drone.
The Sony and Samsung files are read by Apple's engine; Canon and Sigma colours were taken
from Apple's engine after LibRaw's disagreed.

## Credits and licences

The data, papers and software Dyeroom builds on, and their licences: [SOURCES.md](SOURCES.md).
Licences of the bundled data and model are also served at `/licences` (from
`dyeroom/data/LICENSE-*.txt`).
