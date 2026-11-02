"""Decide whether a listing is kept. Keywords use whole-word matching (D-012)."""
from __future__ import annotations

import re

from .text import canon, has_phrase, sentences

# These words describe a job's level. They are checked in titles only, because descriptions
# routinely say things like "report to a senior manager" about real internships.
TITLE_ONLY_KEYWORDS = {"senior", "director", "vice president", "manager", "experienced"}
_REQUIREMENT = re.compile(r"\b(required|requires?|must|only)\b", re.I)
_UNDERGRAD_OK = re.compile(r"\b(bachelor|bachelor's|undergraduate|undergrad)\b", re.I)
# "Rising senior" names a student's class, not a job level (eligibility.py handles it).
_RISING_SENIOR = re.compile(r"\brising seniors?\b", re.I)


def is_internship(title: str, cfg: dict) -> bool:
    return any(has_phrase(title, keyword) for keyword in cfg["must_be_one_of"])


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
    if listing["is_remote"] and cfg["remote"] == "exclude":
        reasons.append(("remote", "Remote job, and config says exclude"))
    elif not listing["is_remote"] and place["tier"] is None:
        where = listing["location_raw"] or "unknown"
        reasons.append(("location", f"Outside target locations: {where} ({place['detail']})"))
    if listing["eligibility"]["status"] == "ineligible":
        reasons.append(("ineligible", listing["eligibility"]["reason"]))
    elif listing["season"] and listing["season"] not in {s["name"] for s in cfg["seasons"]}:
        reasons.append(("season", f"Season {listing['season']} is not in config"))
    return reasons
