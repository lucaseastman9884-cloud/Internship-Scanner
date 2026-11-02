"""Decide whether a listing is kept. Keywords use whole-word matching (D-012)."""
from __future__ import annotations

import re

from .normalize import title_season
from .text import canon, has_phrase, sentences

# These words describe a job's level. They are checked in titles only, because descriptions
# routinely say things like "report to a senior manager" about real internships.
TITLE_ONLY_KEYWORDS = {"senior", "director", "vice president", "manager", "experienced"}
_REQUIREMENT = re.compile(r"\b(required|requires?|must|only)\b", re.I)
_UNDERGRAD_OK = re.compile(r"\b(bachelor|bachelor's|undergraduate|undergrad)\b", re.I)
# "Rising senior" names a student's class, not a job level (eligibility.py handles it).
_RISING_SENIOR = re.compile(r"\brising seniors?\b", re.I)


def remote_allowed(place: dict, cfg: dict) -> bool:
    """D-029: "separate" keeps only remote jobs tied to remote_allowed_states, for their own section."""
    if cfg["remote"] == "include":
        return True
    return cfg["remote"] == "separate" and place.get("remote_state") is not None


def is_internship(title: str, cfg: dict) -> bool:
    if any(has_phrase(title, keyword) for keyword in cfg["must_be_one_of"]):
        return True
    # D-018: "Analyst Program - Summer 2027" is an internship in all but name.
    return bool(title_season(title)) and any(has_phrase(title, term) for term in cfg["program_title_terms"])


def season_limit_problem(listing: dict, place: dict, cfg: dict):
    """D-016: some seasons are realistic only close to home. Returns the reason, or None."""
    limit = next((s.get("max_miles_from_home") for s in cfg["seasons"] if s["name"] == listing["season"]), None)
    if limit is None:
        return None
    miles = place.get("miles_from_home")
    if miles is None:
        return f"{listing['season']} is kept only within {limit} miles of home, and this distance is unknown"
    if miles > limit:
        return f"{listing['season']} is kept only within {limit} miles of home; this is {miles:.0f}"
    return None


def title_exclude_keyword(title: str, cfg: dict):
    cleaned = _RISING_SENIOR.sub(" ", canon(title))
    for keyword in cfg["exclude_keywords"]:
        if has_phrase(cleaned, keyword):
            return keyword
    return None


def description_exclude_keyword(description: str, cfg: dict):
    """Degree and credential terms count only inside a stated requirement that leaves out undergrads."""
    terms = [k for k in cfg["exclude_keywords"] if canon(k) not in TITLE_ONLY_KEYWORDS]
    for sentence in sentences(description):
        for keyword in terms:
            if has_phrase(sentence, keyword):
                states_requirement = _REQUIREMENT.search(sentence) or "required" in canon(keyword)
                if states_requirement and not _UNDERGRAD_OK.search(sentence):
                    return keyword
    return None


def evaluate(listing: dict, place: dict, cfg: dict) -> list:
    """Return exclusion reasons as (code, human-readable text). An empty list means keep."""
    reasons = []
    title = listing["title"]
    if not is_internship(title, cfg):
        reasons.append(("not_internship", "Title has no internship term"))
    keyword = title_exclude_keyword(title, cfg)
    if keyword:
        reasons.append(("excluded_keyword", f"Title contains excluded keyword '{keyword}'"))
    else:
        keyword = description_exclude_keyword(listing["_description"], cfg)
        if keyword:
            reasons.append(("excluded_keyword", f"Description requires '{keyword}'"))
    where = listing["location_raw"] or "none given"
    if listing["is_remote"]:
        if cfg["remote"] == "exclude":
            reasons.append(("remote", "Remote job, and config says exclude"))
        elif not remote_allowed(place, cfg):
            reasons.append(("remote", f"Remote job not tied to {', '.join(cfg['remote_allowed_states'])}"))
    elif place.get("distance_unknown"):
        reasons.append(("location_unknown", f"location unknown: {where}"))
    elif place["tier"] is None:
        reasons.append(("location", f"Outside target locations: {where} ({place['detail']})"))
    if listing["eligibility"]["status"] == "ineligible":
        reasons.append(("ineligible", listing["eligibility"]["reason"]))
    elif listing["season"] and listing["season"] not in {s["name"] for s in cfg["seasons"]}:
        reasons.append(("season", f"Season {listing['season']} is not in config"))
    else:
        problem = season_limit_problem(listing, place, cfg)
        if problem:
            reasons.append(("season_distance", problem))
    return reasons
