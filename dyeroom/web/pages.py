"""The pages that are not the app: terms, privacy notice and refund policy, and the owner's
admin page.

The legal texts are in legal/*.html, with {{placeholders}} filled from the app's settings and
from the environment:

  DYEROOM_LEGAL_NAME      the seller's legal name: a sole trader's registered name or a company
                            (Paddle rejects a project name in its place)
  DYEROOM_LEGAL_ADDRESS   its registered address
  DYEROOM_CONTACT_EMAIL   where customers and privacy requests write; shown in the app too
  DYEROOM_LEGAL_COUNTRY   whose law governs the terms, e.g. Serbia
  DYEROOM_HOSTING         who hosts the server, and where, e.g. "by Hetzner Online GmbH in Germany"
  DYEROOM_BACKUP_HOSTING  who keeps the off-site copy of the accounts, and where (with Litestream)
  DYEROOM_NETWORK         who carries the site's traffic in front of the server, e.g. Cloudflare, Inc.
  DYEROOM_REFUND_DAYS     days to ask for a refund, 14 to 90 (default 30; Paddle requires that range)

Passages between <!--if accounts--> and <!--end--> are for a lab with accounts and payments;
between <!--if free--> and <!--end-->, for the free one (DYEROOM_ACCOUNTS=0), where donations
go through DYEROOM_DONATE_URL.

A value that is not set shows on the page as a marked gap, and /api/health reports
legal_pages: false, so the pages are never published half filled without anyone noticing.
The texts are drafts written from what the app does; have them read by a lawyer.
"""
import html
import os
import re
import time
from pathlib import Path

from . import accounts, billing

LEGAL = Path(__file__).parent / "legal"
UPDATED = "1 November 2026"
REQUIRED = {"legal_name": "DYEROOM_LEGAL_NAME", "legal_address": "DYEROOM_LEGAL_ADDRESS",
            "contact_email": "DYEROOM_CONTACT_EMAIL", "legal_country": "DYEROOM_LEGAL_COUNTRY",
            "hosting": "DYEROOM_HOSTING"}
CONTACT = os.environ.get("DYEROOM_CONTACT_EMAIL", "").strip()
DONATE = os.environ.get("DYEROOM_DONATE_URL", "").strip()  # e.g. https://buymeacoffee.com/<name>
REFUND_DAYS = min(90, max(14, int(os.environ.get("DYEROOM_REFUND_DAYS", "30"))))
TITLES = {"terms": "Terms of use", "privacy": "Privacy notice", "refunds": "Refund policy"}


def _env(name):
    return os.environ.get(name, "").strip()


def missing():
    """The settings the legal pages still need."""
    return [env for env in REQUIRED.values() if not _env(env)]


def _facts(privacy):
    """Every placeholder's value, as HTML."""
    out = {}
    for key, env in REQUIRED.items():
        value = _env(env)
        out[key] = html.escape(value) if value else f'<mark class="gap">{env}</mark>'
    if CONTACT:
        out["contact_email"] = f'<a href="mailto:{html.escape(CONTACT)}">{html.escape(CONTACT)}</a>'
    backup = _env("DYEROOM_BACKUP_HOSTING")
    out.update({
        "updated": UPDATED, "refund_days": str(REFUND_DAYS), "free_frames": str(accounts.FREE_FRAMES),
        "roll_frames": str(billing.ROLL_FRAMES), "plan_cap": f"{accounts.PLAN_CAP:,}",
        "fingerprint_days": f"{accounts.FINGERPRINT_DAYS:g}", "session_days": str(accounts.SESSION_SECONDS // 86400),
        "backup_days": f"{accounts.BACKUP_DAYS:g}",
        "backup_offsite": f", and a copy is kept off the server {html.escape(backup)} for up to 30 days" if backup else "",
        "network_item": (f"<li><b>{html.escape(network)}</b>, which carries the site's traffic to our server and "
                         "protects it from attacks: it handles your IP address and what your browser asks for, on our "
                         "instructions. It may do so in other countries, including the United States, under the "
                         "European Commission's standard contractual clauses.</li>" if (network := _env("DYEROOM_NETWORK"))
                         else ""),
        "network_analytics": (f"{html.escape(network)} counts visits for us (the pages seen, where visitors came from, "
                              "their country and kind of device) without cookies and without keeping who you are. "
                              if (network := _env("DYEROOM_NETWORK")) else ""),
        "donate_link": (f'<a href="{html.escape(DONATE)}" rel="noopener">Buy Me a Coffee</a>' if DONATE
                        else "Buy Me a Coffee"),
        "where_held": "in the server's memory, never on a disk," if privacy.get("in_memory") else "on the server",
        "idle_minutes": str(privacy.get("idle_minutes", 30)), "keep_hours": f"{privacy.get('keep_hours', 3):g}",
    })
    return out


def legal(name, privacy=None):
    privacy = privacy or {}
    accounts = privacy.get("accounts", True)
    body = (LEGAL / f"{name}.html").read_text(encoding="utf-8")
    keep = {"accounts": accounts, "free": not accounts}
    body = re.sub(r"<!--if (\w+)-->(.*?)<!--end-->", lambda m: m.group(2) if keep[m.group(1)] else "", body,
                  flags=re.S)
    for key, value in _facts(privacy).items():
        body = body.replace("{{" + key + "}}", value)
    return _page(TITLES[name], body, name, accounts)


def _page(title, body, current="", accounts=True):
    links = "".join(f'<a href="/{k}"{" aria-current=page" if k == current else ""}>{v}</a>'
                    for k, v in TITLES.items() if accounts or k != "refunds")  # nothing sold, nothing to refund
    contact = f'<a href="mailto:{html.escape(CONTACT)}">Contact</a>' if CONTACT else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} · Dyeroom</title>
<meta name="robots" content="{"index" if current in TITLES and not missing() else "noindex"}">
<link rel="icon" href="/static/icon.svg" type="image/svg+xml"><link rel="icon" href="/favicon.ico" sizes="48x48">
<style>{STYLE}</style></head>
<body><header><a class="brand" href="/">{MARK}Dyeroom</a></header>
<main>{body}</main>
<footer>{links}{contact}</footer></body></html>"""


MARK = ('<svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true"><rect x="1" y="1" width="18" height="18" '
        'rx="3" fill="#e9e1d0"/><rect x="4" y="6" width="12" height="8" rx="1" fill="#141311"/><rect x="6" y="3" '
        'width="8" height="1.5" fill="#b52d1b"/></svg>')
STYLE = """
:root { color-scheme: dark; --bg: #141311; --panel: #1c1a17; --ink: #ece4d4; --dim: #b3aa9b; --line: #35312b;
        --red: #ee5339; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 16px/1.6 -apple-system, BlinkMacSystemFont,
       "SF Pro Text", "Segoe UI", Roboto, system-ui, sans-serif; -webkit-font-smoothing: antialiased; }
header, main, footer { max-width: 46rem; margin: 0 auto; padding: 0 16px; }
header { padding-top: 24px; }
.brand { display: inline-flex; gap: 8px; align-items: center; color: var(--ink); text-decoration: none; font-weight: 600; }
main { padding-top: 32px; padding-bottom: 48px; }
h1 { font-size: 32px; line-height: 1.2; font-weight: 700; letter-spacing: -0.01em; margin: 0 0 4px; }
h2 { font-size: 19px; font-weight: 600; margin: 36px 0 8px; }
h3 { font-size: 16px; font-weight: 600; margin: 24px 0 4px; }
p, li { color: var(--ink); }
.updated, .note { color: var(--dim); font-size: 14px; }
a { color: var(--ink); text-decoration-color: var(--dim); text-underline-offset: 3px; }
a:hover { text-decoration-color: var(--ink); }
ul { padding-left: 20px; }
li { margin: 6px 0; }
mark.gap { background: var(--red); color: #fff; padding: 0 4px; border-radius: 3px; font-size: 14px; }
table { width: 100%; border-collapse: collapse; margin: 12px 0 4px; font-size: 15px; }
th, td { text-align: left; vertical-align: top; padding: 10px 12px 10px 0; border-top: 1px solid var(--line); }
th { color: var(--dim); font-weight: 500; font-size: 13px; }
td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; padding-right: 0; padding-left: 12px; }
.wide { overflow-x: auto; }
footer { display: flex; flex-wrap: wrap; gap: 8px 20px; padding-top: 20px; padding-bottom: 32px;
         border-top: 1px solid var(--line); font-size: 14px; }
footer a { color: var(--dim); text-decoration: none; }
footer a:hover, footer a[aria-current] { color: var(--ink); }
.warn { color: var(--red); }
"""


# --- admin ---------------------------------------------------------------------------------

def not_found():
    """For an address with nothing at it: kept out of search, with the ways back."""
    body = ('<h1>Nothing here</h1><p>There is no page at this address. Go to <a href="/">Dyeroom</a>, '
            'or straight to <a href="/app">the lab</a>.</p>')
    return _page("Not found", body, "notfound")


def _n(value, digits=0, unit=""):
    if value is None:
        return "–"
    return f"{value:,.{digits}f}{unit}"


def _ago(when):
    if not when:
        return "never"
    seconds = time.time() - when
    return f"{seconds / 3600:.1f} h ago" if seconds < 86400 * 2 else f"{seconds / 86400:.0f} days ago"


def admin(now, periods, sales, failures, alerts_sent):
    from .stats import cost_per_frame
    e = html.escape
    rows = [("Waiting for the developer", f"{now['waiting']}" + (f", oldest {now['oldest_wait'] / 60:.0f} min"
                                                                 if now["waiting"] else "")),
            ("Developing", f"{now['developing']} of {now['workers']} workers"),
            ("Photographs held", f"{now['photos_held']} ({now['held_gb']:.1f} GB)"),
            ("Photograph space free", f"{now['space_free_gb']:.1f} of {now['space_gb']:.1f} GB"
             + ("" if now["in_memory"] else ' <span class="warn">· on disk, not in memory</span>')),
            ("Daily copy of the accounts", "accounts are off" if now["last_backup"] is None
             else _ago(now["last_backup"])),
            ("Off-site copy", _ago(now["replicated"]) if now.get("replicated")
             else '<span class="warn">not running: start the backup service (DEVELOPING.md, "Backups")</span>'),
            ("Alerts", "sent to DYEROOM_ALERT_URL" if now["alerts_to"]
             else '<span class="warn">only logged: set DYEROOM_ALERT_URL</span>'),
            ("Legal pages", "complete" if not now["legal_missing"]
             else '<span class="warn">missing ' + e(", ".join(now["legal_missing"])) + "</span>")]
    body = ["<h1>The lab</h1>", f'<p class="updated">{time.strftime("%d %B %Y, %H:%M")}</p>',
            '<div class="wide"><table>', *(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in rows), "</table></div>"]

    body.append("<h2>Developments</h2>")
    body.append('<div class="wide"><table><tr><th></th>' + "".join(f'<th class="n">{e(p["title"])}</th>' for p in periods)
                + "</tr>")
    def line(label, cells):
        body.append(f"<tr><th>{label}</th>" + "".join(f'<td class="n">{c}</td>' for c in cells) + "</tr>")
    line("Developed", [_n(p["jobs"]) for p in periods])
    line("Failed", [_n(p["failed"]) + (f" ({100 * p['failed'] / p['jobs']:.1f} %)" if p["jobs"] else "")
                    for p in periods])
    line("Of them the sample", [_n(p["samples"]) for p in periods])
    line("Full size", [_n(p["full"]) for p in periods])
    for size in ("draft", "full"):
        line(f"{size.title()}: median time", [_n(p["sizes"][size]["median_s"], 1, " s") for p in periods])
        line(f"{size.title()}: 90 % within", [_n(p["sizes"][size]["p90_s"], 1, " s") for p in periods])
        line(f"{size.title()}: waited (median / 90 %)",
             [f"{_n(p['sizes'][size]['median_wait'], 0, ' s')} / {_n(p['sizes'][size]['p90_wait'], 0, ' s')}"
              for p in periods])
        line(f"{size.title()}: processor time", [_n(p["sizes"][size]["median_cpu"], 1, " s") for p in periods])
        line(f"{size.title()}: peak memory", [_n(p["sizes"][size]["peak_mb"], 0, " MB") for p in periods])
        costs = [cost_per_frame(p["sizes"][size]["median_cpu"], now["cores"]) for p in periods]
        line(f"{size.title()}: server cost per 1,000", [f"€{1000 * c:.2f}" if c else "–" for c in costs])
        line(f"{size.title()}: most in an hour", [_n(3600 / p["sizes"][size]["median_s"] * now["workers"])
                                                  if p["sizes"][size]["median_s"] else "–" for p in periods])
    line("Processor hours", [_n(p["cpu_hours"], 1) for p in periods])
    line("Exports (frames)", [f"{_n(p['exports'])} ({_n(p['exported_frames'])})" for p in periods])
    line("Exported", [_n(p["exported_gb"], 2, " GB") for p in periods])
    kinds = sorted({k for p in periods for k in p["events"]})
    for kind in kinds:
        line(e(kind[0].upper() + kind[1:]), [_n(p["events"].get(kind, 0)) for p in periods])
    body.append("</table></div>")
    body.append('<p class="note">Server cost: DYEROOM_SERVER_EUR_MONTH spread over the processor seconds the server '
                f'has in a month ({now["cores"]} cores), times a development\'s processor time; the cost with the '
                "server fully used. Most in an hour: what the workers can develop one after another at the median "
                "time, the lab's real limit.</p>")

    if sales:
        body.append("<h2>Accounts and film</h2>")
        body.append('<div class="wide"><table><tr><th></th>' + "".join(f'<th class="n">{e(t)}</th>' for t, _ in sales)
                    + "</tr>")
        line("New accounts", [_n(r["new_accounts"]) for _, r in sales])
        line("Rolls bought", [_n(r["rolls"]) for _, r in sales])
        line("Rolls refunded", [_n(r["rolls_refunded"]) for _, r in sales])
        line("Photographs paid for", [_n(r["developed"]) for _, r in sales])
        for paid in ("frame", "plan", "again"):
            line(f"&nbsp;&nbsp;with {'a frame' if paid == 'frame' else 'a plan' if paid == 'plan' else 'a free re-add'}",
                 [_n(r["paid_with"].get(paid, 0)) for _, r in sales])
        line("Frames given back (failed)", [_n(r["refunded_frames"]) for _, r in sales])
        body.append("</table></div>")
        accounts_now, plans_now = sales[0][1]["accounts"], sales[0][1]["plans"]
        body.append(f'<p class="note">{accounts_now:,} {"account" if accounts_now == 1 else "accounts"}, '
                    f'{plans_now:,} on a plan now.</p>')

    body.append("<h2>Failures, last 7 days</h2>")
    if failures:
        body.append('<div class="wide"><table><tr><th>When</th><th>File</th><th>Film</th><th>Error</th></tr>')
        for f in failures:
            body.append(f"<tr><td>{time.strftime('%d %b %H:%M', time.localtime(f['finished']))}</td>"
                        f"<td>{e(f['suffix'] or '')}</td><td>{e(f['film'] or '')} {e(f['size'] or '')}</td>"
                        f"<td>{e(f['error'] or '')}</td></tr>")
        body.append("</table></div>")
    else:
        body.append('<p class="note">None.</p>')

    body.append("<h2>Alerts</h2>")
    if alerts_sent:
        body.append('<div class="wide"><table><tr><th>When</th><th>Kind</th><th>Message</th></tr>')
        for a in alerts_sent:
            body.append(f"<tr><td>{time.strftime('%d %b %H:%M', time.localtime(a['sent']))}</td><td>{e(a['kind'])}"
                        f"{'' if a['delivered'] else ' (logged only)'}</td><td>{e(a['message'])}</td></tr>")
        body.append("</table></div>")
    else:
        body.append('<p class="note">None.</p>')
    return _page("The lab", "\n".join(body), "admin")
