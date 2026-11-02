"""Eligibility per SPEC and D-006: a season year is not a class year.

Exclude only when a posting explicitly rules Lucas out. Anything unclear stays, flagged with a reason.
"""
from __future__ import annotations

import re

from .text import canon, scrub_contact_data, sentences

_GRAD_TALK = re.compile(r"\bgraduat|\bclass of\b", re.I)
_RESTRICTIVE = re.compile(r"\b(only|must|required|requires?|between|no later than|exclusively|limited to|eligible)\b", re.I)
_YEAR = re.compile(r"\b(20\d\d)\b")
# "Graduating December 2027 or later" has no upper limit, so it cannot rule out a later graduate.
_OPEN_ENDED = re.compile(r"\b20\d\d\s*(?:or|and|&)\s*(?:later|after|beyond|onwards?)\b|\b20\d\d\s+onwards?\b", re.I)
_SEASON_START_MONTH = {"Spring": 1, "Winter": 1, "Summer": 6, "Fall": 9}


def _quote(sentence: str) -> str:
    return scrub_contact_data(sentence)[:160].strip()


def _graduation_restriction(text: str, grad_year: int, restricted: set) -> tuple:
    """Look for graduation years that leave out Lucas's year. Returns (kind, sentence) or (None, None)."""
    soft = None
    for sentence in sentences(text):
        if not _GRAD_TALK.search(sentence):
            continue
        years = {int(y) for y in _YEAR.findall(sentence)}
        # A list or range reaching his year or later does not rule him out.
        if not (years & restricted) or max(years) >= grad_year or _OPEN_ENDED.search(sentence):
            continue
        if _RESTRICTIVE.search(sentence):
            return "explicit", sentence
        soft = soft or sentence
    return ("mention", soft) if soft else (None, None)


def _rising_conflict(text: str, season: str, grad_year: int) -> str:
    """'Rising senior' for a summer when Lucas would be a rising junior, and the reverse."""
    if not season or not season.startswith("Summer"):
        return ""
    year = int(season.split()[1])
    his_standing = {grad_year - 1: "rising senior", grad_year - 2: "rising junior"}.get(year)
    lowered = canon(text)
    if his_standing is None or his_standing in lowered:
        return ""
    other = "rising junior" if his_standing == "rising senior" else "rising senior"
    return other if other in lowered else ""


def evaluate(title: str, description: str, season: str, cfg: dict) -> dict:
    grad_year, grad_month = (int(x) for x in cfg["profile"]["grad_date"].split("-"))
    restricted = set(cfg["eligibility"]["exclude_if_restricted_to_grad_years"])
    text = f"{title}. {description or ''}"

    kind, sentence = _graduation_restriction(text, grad_year, restricted)
    if kind == "explicit":
        return {"status": "ineligible", "reason": f"Posting limits graduation year: \"{_quote(sentence)}\""}

    other = _rising_conflict(text, season, grad_year)
    if other:
        return {"status": "ineligible", "reason": f"Posting asks for a {other}, but {season} is not that standing for a {grad_year} graduate"}

    if season and season != "Early-career program":
        name, year = season.split()
        if (int(year), _SEASON_START_MONTH[name]) > (grad_year, grad_month):
            return {"status": "ineligible", "reason": f"{season} starts after graduation ({cfg['profile']['grad_date']})"}

    if kind == "mention":
        return {"status": "unclear", "reason": f"Mentions an earlier graduation year without saying it is required: \"{_quote(sentence)}\""}
    if season == "Early-career program":
        return {"status": "unclear", "reason": "Early-career program; class-year requirement not confirmed"}
    if season:
        return {"status": "eligible", "reason": f"{season} fits a {grad_year} graduate, with no restriction found"}
    return {"status": "unclear", "reason": "No season or graduation year stated"}
