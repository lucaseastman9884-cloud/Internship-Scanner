"""The morning email (SPEC "MORNING EMAIL", D-005, D-009).

Builds one HTML email, with a plain-text copy, from data/internships.json, data/meta.json and the
`email:` block in config/config.yaml, and sends it with Python's own smtplib.

Credentials come only from environment variables, which GitHub Actions fills from its secrets.
Nothing here prints their values. If one is missing, the email is skipped with a warning and the
scan still counts as a success.
"""
from __future__ import annotations

import datetime as dt
import html
import os
import re
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from pathlib import Path
from typing import Optional

from . import store
from .config import load_cities, load_companies, load_config
from .location import LocationResolver, _miles
from .text import has_phrase

# Google's settings for personal Gmail accounts, checked 2026-11-03 at
# https://support.google.com/mail/answer/7104828 ("Outgoing Mail (SMTP) Server: smtp.gmail.com,
# Requires TLS: Yes (if available), Requires Authentication: Yes, Port for TLS/STARTTLS: 587").
# These are facts about Gmail, not Lucas's preferences, so they live here rather than in config.
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_TIMEOUT_SECONDS = 60
SECRET_NAMES = ("SMTP_USERNAME", "SMTP_APP_PASSWORD", "EMAIL_TO")
LOCAL_TZ = "America/Chicago"
SENDER_NAME = "Internship Scanner"
NOT_STATED = "Not stated"  # the name `email.seasons` uses for a listing with no season
REPO_URL = "https://github.com/lucaseastman9884-cloud/Internship-Scanner"


def _local_zone():
    from zoneinfo import ZoneInfo  # standard library since Python 3.9
    return ZoneInfo(LOCAL_TZ)


def local_date(now: dt.datetime) -> dt.date:
    """The subject and the deadline window use Lucas's calendar date, not UTC's."""
    return now.astimezone(_local_zone()).date()


# ---------------------------------------------------------------- choosing listings

def _date(value) -> Optional[dt.date]:
    try:
        return dt.date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def _points(reason: str) -> int:
    match = re.match(r"\s*([+-]\d+)", reason)
    return int(match.group(1)) if match else 0


def top_reasons(listing: dict, count: int = 2) -> list:
    """The reasons that added the most points. Ties keep the order scoring wrote them in."""
    return sorted(listing.get("match_reasons") or [], key=_points, reverse=True)[:count]


def by_score(listing: dict):
    return (-listing["relevance_score"], -(_date(listing.get("first_seen")) or dt.date.min).toordinal(),
            listing["company"].lower(), listing["title"].lower(), listing["id"])


def is_remote_iowa(listing: dict) -> bool:
    return "remote_iowa" in (listing.get("tags") or [])


class AreaMatcher:
    """Answers "is this listing in one of the areas named in email.areas?".

    A name is either a `target_areas` name, matched by distance from that area's center, or a
    two-letter state code. A listing without coordinates matches a target area only if its posted
    location names the area's center city, the same rule the pipeline uses (D-022)."""

    def __init__(self, cfg: dict, resolver: LocationResolver):
        wanted = cfg["email"]["areas"]
        self.all = wanted == "all"
        names = [] if self.all else list(wanted)
        self.areas = [a for a in resolver.areas if a["name"] in names]
        self.states = {n.upper() for n in names if re.fullmatch(r"[A-Za-z]{2}", n)}

    def matches(self, listing: dict) -> bool:
        if self.all:
            return True
        if (listing.get("state") or "").upper() in self.states:
            return True
        point = {"lat": listing.get("lat"), "lng": listing.get("lng")}
        for area in self.areas:
            if point["lat"] is not None and point["lng"] is not None:
                if _miles(point, area["center"]) <= area["radius"]:
                    return True
            elif has_phrase(listing.get("location_raw") or "", area["center"]["city"]):
                return True
        return False


def season_ok(listing: dict, cfg: dict) -> bool:
    wanted = cfg["email"]["seasons"]
    if wanted == "all":
        return True
    return (listing.get("season") or NOT_STATED) in wanted


def eligible_pool(listings: list, cfg: dict, areas: AreaMatcher) -> list:
    """Status first (D-024): a filtered or closing listing keeps a stale score, so it must never
    reach the score check. Then min_score, seasons and areas from config."""
    out = []
    for listing in listings:
        if listing.get("status") != "open":
            continue
        if listing["relevance_score"] < cfg["email"]["min_score"]:
            continue
        if not season_ok(listing, cfg):
            continue
        # Remote listings tied to Iowa have no place on a map, so the areas filter can't apply (D-029).
        if not is_remote_iowa(listing) and not areas.matches(listing):
            continue
        out.append(listing)
    return out


def new_checker(state: Optional[dict], cfg: dict, now: dt.datetime):
    """Return a function telling whether a listing is new since the last email.

    `first_seen` is a UTC date with no time, so a timestamp alone can't split one day's listings.
    The state therefore also records which listings first seen on the send date already existed
    when that email went out. With no state yet, "new" falls back to new_badge_days."""
    if state and _date(state.get("sent_date")):
        sent = _date(state["sent_date"])
        known = set(state.get("ids_first_seen_on_sent_date") or [])

        def check(listing):
            seen = _date(listing.get("first_seen"))
            return bool(seen) and (seen > sent or (seen == sent and listing["id"] not in known))
        return check

    today = now.astimezone(dt.timezone.utc).date()
    days = cfg["new_badge_days"]

    def fallback(listing):
        seen = _date(listing.get("first_seen"))
        return bool(seen) and 0 <= (today - seen).days < days
    return fallback


def build_sections(listings: list, meta: dict, cfg: dict, companies: list, resolver: LocationResolver,
                   now: dt.datetime) -> dict:
    """Pick what goes in each section. Pure: no files, no network."""
    email_cfg = cfg["email"]
    pool = eligible_pool(listings, cfg, AreaMatcher(cfg, resolver))
    is_new = new_checker((meta or {}).get("email"), cfg, now)
    today = local_date(now)
    last_day = today + dt.timedelta(days=email_cfg["deadline_window_days"])

    on_site = sorted((x for x in pool if not is_remote_iowa(x)), key=by_score)
    remote = sorted((x for x in pool if is_remote_iowa(x)), key=by_score)
    new_all = [x for x in on_site if is_new(x)]
    new_shown = new_all[:email_cfg["max_new"]]
    shown_ids = {x["id"] for x in new_shown}

    deadlines = [x for x in pool if _date(x.get("deadline")) and today <= _date(x["deadline"]) <= last_day]
    deadlines.sort(key=lambda x: (_date(x["deadline"]), by_score(x)))
    # Listings already shown under "New" aren't repeated here.
    top_open = [x for x in on_site if x["id"] not in shown_ids][:email_cfg["max_top_open"]]

    priority = {c["name"]: c["priority"] for c in companies}
    manual = []
    for row in (meta or {}).get("check_manually", []):
        manual.append({"company": row["company"], "url": row.get("url"), "reason": row.get("reason"),
                       "priority": priority.get(row["company"], 9)})
    # Companies that failed today come first, then the always-manual ones by priority.
    manual.sort(key=lambda r: (r["reason"] == "manual", r["priority"], r["company"].lower()))

    remote_new = [x for x in remote if is_new(x)]
    return {
        "date": today.isoformat(),
        "new_total": len(new_all) + len(remote_new),
        "new_on_site_total": len(new_all),
        "new": new_shown,
        "deadlines": deadlines,
        "top_open": top_open,
        "remote_iowa": remote,
        "new_ids": {x["id"] for x in new_all + remote_new},
        "manual": manual,
        "health": health_line(meta or {}),
        "window_days": email_cfg["deadline_window_days"],
    }


def health_line(meta: dict) -> str:
    """One line on how the sources did, from meta.json."""
    t = meta.get("totals")
    if not t:
        return "Source health: no run summary was found."
    by_ats = {}
    for ats, counts in (meta.get("source_health") or {}).items():
        if ats != "manual":
            by_ats[ats] = counts.get("ok", 0)
    parts = ", ".join(f"{n} {ats.capitalize()}" for ats, n in sorted(by_ats.items(), key=lambda kv: (-kv[1], kv[0])) if n)
    manual = sum(1 for r in meta.get("companies", []) if r.get("status") == "manual")
    finished = meta.get("run_finished") or meta.get("run_started")
    when = ""
    if finished:
        try:
            when = " Scan finished " + dt.datetime.fromisoformat(finished).astimezone(_local_zone()).strftime("%-I:%M %p %Z") + "."
        except ValueError:
            when = ""
    return (f"Source health: {t.get('companies_fetched_ok', 0)} of {t.get('companies_live', 0)} live companies fetched"
            f"{f' ({parts})' if parts else ''}, {t.get('companies_failed', 0)} failed, {manual} manual.{when}")


# ---------------------------------------------------------------- rendering

def subject_for(n: int, date: str) -> str:
    return f"Internships — {n} new ({date})"


def _safe_url(url) -> Optional[str]:
    """Only http(s) links reach the email, so a strange value can't become a script link."""
    return url if isinstance(url, str) and re.match(r"^https?://", url) else None


def _apply_url(listing: dict) -> Optional[str]:
    return _safe_url(listing.get("apply_url")) or next(
        (u for u in (_safe_url(s.get("url")) for s in listing.get("sources") or []) if u), None)


def _place(listing: dict) -> str:
    if is_remote_iowa(listing):
        return "Remote (Iowa)"
    label = listing.get("location_label")
    if label and label != "Location unknown":
        return label
    if listing.get("city") and listing.get("state"):
        return f"{listing['city']}, {listing['state']}"
    return "Location unknown"


def _season(listing: dict) -> str:
    return listing.get("season") or "Season not stated"


SECTION_TITLES = {
    "new": "New since last email",
    "deadlines": "Deadlines in the next {days} days",
    "top_open": "Top open matches",
    "remote_iowa": "Remote — Iowa",
    "manual": "Check these manually",
}
EMPTY_TEXT = {
    "new": "Nothing new since the last email.",
    "deadlines": "No stated deadlines in this window. Most postings don't state one.",
    "top_open": "No other open listings meet the minimum score.",
}

# Inline styles only: Gmail drops <style> blocks in many clients.
S_BODY = "margin:0;padding:16px;background:#f5f5f4;font-family:Arial,Helvetica,sans-serif;color:#1c1917;"
S_WRAP = "max-width:640px;margin:0 auto;background:#ffffff;border:1px solid #e7e5e4;border-radius:6px;padding:20px;"
S_H1 = "font-size:20px;margin:0 0 4px 0;"
S_H2 = "font-size:16px;margin:24px 0 8px 0;padding-bottom:4px;border-bottom:2px solid #e7e5e4;"
S_ITEM = "padding:10px 0;border-bottom:1px solid #f0efee;"
S_TITLE = "font-size:15px;font-weight:bold;color:#1d4ed8;text-decoration:none;"
S_META = "font-size:13px;color:#57534e;margin-top:2px;"
S_REASON = "font-size:12px;color:#78716c;margin-top:2px;"
S_BADGE = "display:inline-block;font-size:11px;font-weight:bold;color:#ffffff;background:#15803d;border-radius:3px;padding:1px 5px;margin-left:6px;"
S_SCORE = "font-weight:bold;color:#1c1917;"
S_MUTED = "font-size:13px;color:#78716c;"
S_LINK = "color:#1d4ed8;"


def _listing_html(listing: dict, new_ids: set, show_deadline: bool) -> str:
    e = html.escape
    url = _apply_url(listing)
    title = e(listing["title"])
    title_html = f'<a href="{e(url)}" style="{S_TITLE}">{title}</a>' if url else f'<span style="{S_TITLE}">{title}</span>'
    badge = f'<span style="{S_BADGE}">NEW</span>' if listing["id"] in new_ids else ""
    bits = [e(listing["company"]), e(_place(listing)), e(_season(listing)),
            f'<span style="{S_SCORE}">Score {int(listing["relevance_score"])}</span>']
    if show_deadline or listing.get("deadline"):
        bits.append(f"Deadline {e(str(listing.get('deadline')))}")
    reasons = " · ".join(e(r) for r in top_reasons(listing))
    apply_link = f' · <a href="{e(url)}" style="{S_LINK}">Apply</a>' if url else ""
    return (f'<div style="{S_ITEM}">{title_html}{badge}'
            f'<div style="{S_META}">{" · ".join(bits)}{apply_link}</div>'
            f'<div style="{S_REASON}">{reasons}</div></div>')


def _listing_text(listing: dict, new_ids: set) -> str:
    url = _apply_url(listing) or "(no link)"
    new = " [NEW]" if listing["id"] in new_ids else ""
    deadline = f" | Deadline {listing['deadline']}" if listing.get("deadline") else ""
    lines = [f"- {listing['title']}{new}",
             f"  {listing['company']} | {_place(listing)} | {_season(listing)} | Score {int(listing['relevance_score'])}{deadline}"]
    reasons = top_reasons(listing)
    if reasons:
        lines.append("  " + "; ".join(reasons))
    lines.append(f"  Apply: {url}")
    return "\n".join(lines)


def _section_order(sections: dict) -> list:
    order = ["new", "deadlines", "top_open"]
    if sections["remote_iowa"]:  # D-029: only when there is something to show
        order.append("remote_iowa")
    return order


def _more_note(sections: dict) -> Optional[str]:
    hidden = sections["new_on_site_total"] - len(sections["new"])
    return f"{hidden} more new listing(s) passed the filters but are past email.max_new." if hidden > 0 else None


def render_html(sections: dict, subject: str) -> str:
    e = html.escape
    body = [f'<h1 style="{S_H1}">{e(subject)}</h1>',
            f'<div style="{S_MUTED}">Open listings only, scored {sections.get("min_score", "")} and up, '
            f'filtered by your email settings.</div>']
    for key in _section_order(sections):
        title = SECTION_TITLES[key].format(days=sections["window_days"])
        items = sections[key]
        body.append(f'<h2 style="{S_H2}">{e(title)} ({len(items)})</h2>')
        if not items:
            body.append(f'<div style="{S_MUTED}">{e(EMPTY_TEXT[key])}</div>')
        for listing in items:
            # Everything in "New" is new, so the badge is only shown in the other sections.
            badges = set() if key == "new" else sections["new_ids"]
            body.append(_listing_html(listing, badges, key == "deadlines"))
        if key == "new" and _more_note(sections):
            body.append(f'<div style="{S_MUTED};margin-top:6px;">{e(_more_note(sections))}</div>')

    body.append(f'<h2 style="{S_H2}">{SECTION_TITLES["manual"]} ({len(sections["manual"])})</h2>')
    failed = [m for m in sections["manual"] if m["reason"] != "manual"]
    always = [m for m in sections["manual"] if m["reason"] == "manual"]

    def links(rows):
        return ", ".join(f'<a href="{e(u)}" style="{S_LINK}">{e(r["company"])}</a>' if (u := _safe_url(r["url"]))
                         else e(r["company"]) for r in rows)
    if failed:
        body.append(f'<div style="font-size:13px;margin-bottom:6px;"><b>Couldn\'t be fetched today:</b> {links(failed)}</div>')
    if always:
        body.append(f'<div style="font-size:13px;line-height:1.6;"><b>No feed, check by hand:</b> {links(always)}</div>')
    if not sections["manual"]:
        body.append(f'<div style="{S_MUTED}">None today.</div>')

    body.append(f'<p style="{S_MUTED};margin-top:24px;">{e(sections["health"])}</p>')
    body.append(f'<p style="{S_MUTED}">Sent by <a href="{REPO_URL}" style="{S_LINK}">Internship Scanner</a>.</p>')
    return ('<!DOCTYPE html><html><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(subject)}</title></head>'
            f'<body style="{S_BODY}"><div style="{S_WRAP}">' + "".join(body) + "</div></body></html>\n")


def render_text(sections: dict, subject: str) -> str:
    out = [subject, "=" * len(subject), ""]
    for key in _section_order(sections):
        title = SECTION_TITLES[key].format(days=sections["window_days"])
        items = sections[key]
        out += [f"{title} ({len(items)})", "-" * (len(title) + 4)]
        badges = set() if key == "new" else sections["new_ids"]
        out += [_listing_text(x, badges) for x in items] or [EMPTY_TEXT[key]]
        if key == "new" and _more_note(sections):
            out.append(_more_note(sections))
        out.append("")
    out += [f"{SECTION_TITLES['manual']} ({len(sections['manual'])})", "-" * 24]
    for row in sections["manual"]:
        flag = "" if row["reason"] == "manual" else f" (couldn't be fetched today: {row['reason']})"
        out.append(f"- {row['company']}{flag}: {_safe_url(row['url']) or '(no link)'}")
    if not sections["manual"]:
        out.append("None today.")
    out += ["", sections["health"], ""]
    return "\n".join(out)


def build_email(listings, meta, cfg, companies, resolver, now) -> dict:
    sections = build_sections(listings, meta, cfg, companies, resolver, now)
    sections["min_score"] = cfg["email"]["min_score"]
    subject = subject_for(sections["new_total"], sections["date"])
    return {"subject": subject, "sections": sections,
            "html": render_html(sections, subject), "text": render_text(sections, subject)}


def counts(report: dict) -> dict:
    s = report["sections"]
    return {"new": len(s["new"]), "new_total": s["new_total"], "deadlines": len(s["deadlines"]),
            "top_open": len(s["top_open"]), "remote_iowa": len(s["remote_iowa"]), "manual": len(s["manual"])}


# ---------------------------------------------------------------- failure email

def build_failure_email(now: dt.datetime, run_url: Optional[str], outcomes: dict) -> dict:
    """Short, and reads no config or data, because those may be what broke."""
    date = local_date(now).isoformat()
    subject = f"Scan failed ({date})"
    failed = [f"{step}: {result}" for step, result in outcomes.items() if result and result not in ("success", "skipped")]
    url = _safe_url(run_url)
    lines = [subject, "", "The daily scan didn't finish cleanly, so no morning email was built from today's run."]
    if failed:
        lines.append("Steps that didn't succeed: " + ", ".join(failed) + ".")
    lines += [f"Open the run to see where it stopped: {url}" if url else "Open the Actions tab on GitHub to see the run.",
              "", "docs/AUTOMATION.md explains what a red X means."]
    text = "\n".join(lines) + "\n"
    e = html.escape
    link = f'<a href="{e(url)}" style="{S_LINK}">Open the run on GitHub</a>' if url else "Open the Actions tab on GitHub."
    body = (f'<h1 style="{S_H1}">{e(subject)}</h1>'
            f"<p>The daily scan didn't finish cleanly, so no morning email was built from today's run.</p>"
            + (f"<p>Steps that didn't succeed: {e(', '.join(failed))}.</p>" if failed else "")
            + f"<p>{link}</p><p style=\"{S_MUTED}\">docs/AUTOMATION.md explains what a red X means.</p>")
    page = (f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{e(subject)}</title></head>'
            f'<body style="{S_BODY}"><div style="{S_WRAP}">{body}</div></body></html>\n')
    return {"subject": subject, "html": page, "text": text}


# ---------------------------------------------------------------- sending

def missing_secrets(env) -> list:
    return [name for name in SECRET_NAMES if not (env.get(name) or "").strip()]


def _redact(text: str, env) -> str:
    """An SMTP error could echo back what we sent. Strip every secret before printing it."""
    out = str(text)
    for name in SECRET_NAMES:
        value = (env.get(name) or "").strip()
        if value:
            out = out.replace(value, f"[{name}]")
            out = out.replace(value.replace(" ", ""), f"[{name}]")
    return out


def compose(report: dict, sender: str, recipients: list) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = report["subject"]
    msg["From"] = formataddr((SENDER_NAME, sender))
    msg["To"] = ", ".join(recipients)
    msg["Message-ID"] = make_msgid(domain=sender.split("@")[-1] if "@" in sender else None)
    msg.set_content(report["text"])
    msg.add_alternative(report["html"], subtype="html")
    return msg


class SendError(Exception):
    pass


def send(report: dict, env=None, smtp_class=None, log=print) -> bool:
    """Send the email. Returns False, after a warning, when a secret is missing.
    Raises SendError, with secrets removed from the message, when Gmail refuses."""
    env = os.environ if env is None else env
    smtp_class = smtp_class or smtplib.SMTP  # looked up at call time, so tests can replace it
    missing = missing_secrets(env)
    if missing:
        # GitHub shows ::warning:: lines as yellow notes on the run page. Names only, never values.
        log(f"::warning title=Email not sent::Missing secret(s): {', '.join(missing)}. "
            "The scan itself is fine. docs/AUTOMATION.md shows how to add them.")
        return False
    sender = env["SMTP_USERNAME"].strip()
    # Google shows app passwords in groups of four with spaces; the spaces aren't part of it.
    password = re.sub(r"\s+", "", env["SMTP_APP_PASSWORD"])
    recipients = [a.strip() for a in env["EMAIL_TO"].split(",") if a.strip()]
    msg = compose(report, sender, recipients)
    try:
        with smtp_class(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT_SECONDS) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(sender, password)
            smtp.send_message(msg, from_addr=sender, to_addrs=recipients)
    except (smtplib.SMTPException, OSError) as err:
        raise SendError(_redact(f"{type(err).__name__}: {err}", env)) from None
    log(f"Email sent: {report['subject']}")
    return True


def record_send(meta: dict, listings: list, now: dt.datetime) -> dict:
    """What "new since last email" needs next time. Listing ids and a time only, no personal data."""
    sent_date = now.astimezone(dt.timezone.utc).date().isoformat()
    meta = dict(meta)
    meta["email"] = {
        "last_sent_at": now.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "sent_date": sent_date,
        "ids_first_seen_on_sent_date": sorted(x["id"] for x in listings if x.get("first_seen") == sent_date),
    }
    return meta


# ---------------------------------------------------------------- command line

def load_inputs(config_dir: Path, data_dir: Path):
    cities = load_cities(config_dir / "cities.yaml")
    cfg = load_config(config_dir / "config.yaml", cities)
    companies = load_companies(config_dir / "companies.yaml")
    resolver = LocationResolver(cfg, cities)
    listings = store.load_listings(data_dir)
    meta = store.read_json(data_dir / "meta.json", {})
    return cfg, companies, resolver, listings, meta


def run_email(config_dir: Path, data_dir: Path, out_dir: Path, dry_run: bool, env=None,
              smtp_class=None, now=None, log=print) -> int:
    now = now or dt.datetime.now(dt.timezone.utc)
    cfg, companies, resolver, listings, meta = load_inputs(config_dir, data_dir)
    report = build_email(listings, meta, cfg, companies, resolver, now)
    log(f"Subject: {report['subject']}")
    log("Section counts: " + ", ".join(f"{k} {v}" for k, v in counts(report).items()))
    if dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "email_preview.html").write_text(report["html"], encoding="utf-8")
        (out_dir / "email_preview.txt").write_text(report["text"], encoding="utf-8")
        log(f"Dry run: wrote {out_dir / 'email_preview.html'} and email_preview.txt. Nothing was sent.")
        return 0
    try:
        sent = send(report, env, smtp_class, log)
    except SendError as err:
        log(f"::error title=Email failed::{err}")
        return 1
    if sent:
        store.write_json(data_dir / "meta.json", record_send(meta, listings, now))
    return 0


def run_failure_email(run_url: Optional[str], outcomes: dict, env=None, smtp_class=None,
                      now=None, log=print, out_dir: Optional[Path] = None) -> int:
    now = now or dt.datetime.now(dt.timezone.utc)
    report = build_failure_email(now, run_url, outcomes)
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "failure_preview.html").write_text(report["html"], encoding="utf-8")
        log(f"Dry run: wrote {out_dir / 'failure_preview.html'}. Nothing was sent.")
        return 0
    try:
        send(report, env, smtp_class, log)
    except SendError as err:
        log(f"::error title=Failure email failed::{err}")
        return 1
    return 0
