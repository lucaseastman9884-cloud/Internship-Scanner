"""Shape source data into the SPEC data model, including season and role detection."""
from __future__ import annotations

import datetime as dt
import hashlib
import re
from typing import Optional

from .text import canon, has_phrase, make_snippet, normalized_title, scrub_contact_data

_SEASON = r"(spring|summer|fall|autumn|winter)"
_YEAR = r"(20\d\d|'\d\d)"
_GAP = r"(?:\W+[\w&]+){0,2}?\W+"
_ADJACENT = [(re.compile(rf"\b{_SEASON}\W+{_YEAR}(?!\d)", re.I), 1, 2),
             (re.compile(rf"(?<![\w']){_YEAR}\W+{_SEASON}\b", re.I), 2, 1)]
# Titles may put words in between, as in the real '2027 Tax Winter Internship'. Descriptions are
# longer and noisier, so they must state the season and year side by side.
_IN_TITLE = _ADJACENT + [(re.compile(rf"\b{_SEASON}{_GAP}{_YEAR}(?!\d)", re.I), 1, 2),
                         (re.compile(rf"(?<![\w']){_YEAR}{_GAP}{_SEASON}\b", re.I), 2, 1)]
_DEADLINE = re.compile(
    r"(?:application\s+deadline|apply\s+by|applications?\s+(?:are\s+)?due(?:\s+by)?)\W+"
    r"((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+20\d\d)", re.I)


def _format_season(season: str, year: str) -> str:
    season = "Fall" if season.lower() == "autumn" else season.capitalize()
    year = "20" + year[1:] if year.startswith("'") else year
    return f"{season} {year}"


def _search_season(text: str, patterns: list) -> Optional[str]:
    hits = []
    for pattern, season_group, year_group in patterns:
        m = pattern.search(text or "")
        if m:
            hits.append((m.start(), m.group(season_group), m.group(year_group)))
    if not hits:
        return None
    _, season, year = min(hits, key=lambda h: h[0])
    return _format_season(season, year)


def title_season(title: str) -> Optional[str]:
    return _search_season(title, _IN_TITLE)


def detect_season(title: str, description: str, cfg: dict) -> tuple:
    """Return (season, where it was found). The title is trusted over the description."""
    season = title_season(title)
    if season:
        return season, "title"
    if role_match(title, cfg)["early_signals"]:
        return "Early-career program", "title"
    # A description may mention other terms ("classes begin Fall 2026"), so only a season the
    # config targets counts here. A wrong one must not exclude the listing.
    wanted = {s["name"] for s in cfg["seasons"]}
    hits = []
    for pattern, season_group, year_group in _ADJACENT:
        for m in pattern.finditer(description or ""):
            season = _format_season(m.group(season_group), m.group(year_group))
            if season in wanted:
                hits.append((m.start(), season))
    return (min(hits)[1], "description") if hits else (None, None)


def role_match(title: str, cfg: dict) -> dict:
    """Find role keywords in the title. 'accounting intern' also matches 'Intern - Accounting Majors'."""
    found, early = [], []
    is_intern = has_phrase(title, "intern")
    for category, keywords in cfg["role_categories"].items():
        for keyword in keywords:
            key = canon(keyword)
            hit = has_phrase(title, key)
            if not hit and key.endswith(" intern") and is_intern:
                hit = has_phrase(title, key[: -len(" intern")])
            if hit:
                if category == "early_career":
                    early.append(keyword)
                else:
                    found.append((category, keyword))
    if found:
        category, keyword = found[0]
    elif early:
        category, keyword = "early_career", early[0]
    else:
        category, keyword = None, None
    return {"category": category, "keyword": keyword, "early_signals": early}


def description_role_keyword(description: str, cfg: dict) -> Optional[str]:
    for category, keywords in cfg["role_categories"].items():
        if category == "early_career":
            continue  # too common in company boilerplate to count as a role signal
        for keyword in keywords:
            if has_phrase(description, keyword):
                return keyword
    return None


def listing_id(company_id: str, source_name: str, source_job_id: Optional[str], title: str, location_raw: str) -> str:
    if source_job_id:
        key = f"{source_name}|{source_job_id}"
    else:
        key = f"{company_id}|{normalized_title(title)}|{canon(location_raw)}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def iso_date(value: Optional[str]) -> Optional[str]:
    """Keep only the date a source states. Anything unparseable stays null; dates are never invented."""
    m = re.match(r"\d{4}-\d{2}-\d{2}", value or "")
    return m.group(0) if m else None


def find_deadline(description: str) -> Optional[str]:
    """Only an explicit phrase such as 'Application deadline: March 1, 2027' counts."""
    m = _DEADLINE.search(description or "")
    if not m:
        return None
    cleaned = re.sub(r"[.,]", "", m.group(1))
    month, day, year = cleaned.split()
    try:
        return dt.datetime.strptime(f"{month[:3]} {day} {year}", "%b %d %Y").date().isoformat()
    except ValueError:
        return None


def new_listing(company: dict, source_name: str, source_job_id, title: str, location_raw: str,
                apply_url: Optional[str], date_posted: Optional[str] = None, deadline: Optional[str] = None,
                description: str = "", is_remote: bool = False) -> dict:
    """Every adapter builds its results here, so all sources share one shape."""
    job_id = str(source_job_id) if source_job_id not in (None, "") else None
    return {
        "id": listing_id(company["company_id"], source_name, job_id, title, location_raw),
        "company_id": company["company_id"],
        "title": re.sub(r"\s+", " ", title or "").strip(),
        "company": company["name"],
        "ats": source_name,
        "location_raw": re.sub(r"\s+", " ", location_raw or "").strip(),
        "city": None, "state": None, "country": None,
        "lat": None, "lng": None, "location_label": "Location unknown",
        "is_remote": bool(is_remote),
        "sources": [{"source_name": source_name, "url": apply_url, "source_job_id": job_id}],
        "apply_url": apply_url,
        "date_posted": iso_date(date_posted),
        "deadline": iso_date(deadline) or find_deadline(description),
        "first_seen": None, "last_seen": None,
        "status": "open",
        "season": None, "role_category": None,
        "eligibility": {"status": "unclear", "reason": "not evaluated"},
        "relevance_score": 0, "match_reasons": [],
        "description_snippet": make_snippet(description),
        "recurring": False, "last_known_open": None,
        "missed_runs": 0, "filtered_reason": None,
        # Working field for this run only. It never reaches the data files (see store.py).
        "_description": description or "",
    }


def _location_label(place: dict) -> str:
    if place["is_remote"]:
        return "Remote"
    if place.get("lat") is None:
        return "Location unknown"  # never a map marker (SPEC QA checklist)
    return ", ".join(x for x in (place["city"], place["state"]) if x)


def enrich(listing: dict, cfg: dict, resolver, allow_lookup: bool = True) -> dict:
    """Add the fields that depend on config. Returns the location details for filtering and scoring."""
    place = resolver.resolve(listing["location_raw"], listing["is_remote"], allow_lookup)
    listing.update(city=place["city"], state=place["state"], country=place["country"], is_remote=place["is_remote"],
                   lat=place.get("lat"), lng=place.get("lng"), location_label=_location_label(place))
    listing["title"] = scrub_contact_data(listing["title"])
    season, _where = detect_season(listing["title"], listing["_description"], cfg)
    listing["season"] = season
    listing["role_category"] = role_match(listing["title"], cfg)["category"]
    return place
