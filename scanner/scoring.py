"""Rule-based relevance score, 0 to 100. Every point change adds a readable reason.

Which keywords, places, and season weights count comes from config. The point values below are
first-pass settings, to be calibrated in the QA spot check.
"""
from __future__ import annotations

from .normalize import description_role_keyword, role_match

ROLE_IN_TITLE = 40
ROLE_ONLY_IN_DESCRIPTION = -10
NO_ROLE_SIGNAL = -15
TARGET_AREA = 20
WHOLE_STATE_OR_HOME_RADIUS = 10
SEASON_MAX = 25
SEASON_NOT_STATED = 8
ELIGIBLE = 10
INELIGIBLE = -50
EARLY_CAREER = 5


def _signed(points: int) -> str:
    return f"{points:+d}"


def score(listing: dict, place: dict, cfg: dict) -> tuple:
    total, reasons = 0, []

    def add(points: int, why: str) -> None:
        nonlocal total
        total += points
        reasons.append(f"{_signed(points)} {why}")

    role = role_match(listing["title"], cfg)
    if role["category"]:
        add(ROLE_IN_TITLE, f"role: '{role['keyword']}' in title ({role['category']})")
    else:
        keyword = description_role_keyword(listing["_description"], cfg)
        if keyword:
            add(ROLE_ONLY_IN_DESCRIPTION, f"role: '{keyword}' only in description, which may be company boilerplate")
        else:
            add(NO_ROLE_SIGNAL, "role: no target role keyword found")

    if place["tier"] == "target_area":
        add(TARGET_AREA, f"location: {place['detail']}")
    elif place["tier"] == "whole_state":
        add(WHOLE_STATE_OR_HOME_RADIUS, f"location: in {place['detail']}")
    elif place["tier"] == "home_radius":
        add(WHOLE_STATE_OR_HOME_RADIUS, f"location: {place['detail']}")
    else:
        add(0, "location: outside target locations")

    season = listing["season"]
    weights = {s["name"]: s["weight"] for s in cfg["seasons"]}
    if season in weights:
        add(round(SEASON_MAX * weights[season]), f"season: {season} (weight {weights[season]})")
    elif season:
        add(0, f"season: {season} is not in config")
    else:
        add(SEASON_NOT_STATED, "season: not stated")

    status = listing["eligibility"]["status"]
    if status == "eligible":
        add(ELIGIBLE, "eligibility: eligible")
    elif status == "ineligible":
        add(INELIGIBLE, "eligibility: ineligible")
    else:
        add(0, "eligibility: unclear")

    if role["early_signals"]:
        add(EARLY_CAREER, f"early-career signal: '{role['early_signals'][0]}'")

    final = max(0, min(100, total))
    if final != total:
        reasons.append(f"score limited to {final} (raw total {total})")
    return final, reasons
