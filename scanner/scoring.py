"""Rule-based relevance score. Every point change adds a readable reason.

Every number comes from the scoring block in config (D-020). None may be written in this file;
tests/test_location_and_scoring.py checks that.
"""
from __future__ import annotations

from .normalize import description_role_keyword, role_match


def _signed(points) -> str:
    return f"{points:+g}"


def score(listing: dict, place: dict, cfg: dict) -> tuple:
    points = cfg["scoring"]
    total, reasons = 0, []

    def add(value, why: str) -> None:
        nonlocal total
        total += value
        reasons.append(f"{_signed(value)} {why}")

    role = role_match(listing["title"], cfg)
    if role["category"]:
        add(points["role_in_title"], f"role: '{role['keyword']}' in title ({role['category']})")
    else:
        keyword = description_role_keyword(listing["_description"], cfg)
        if keyword:
            add(points["role_only_in_description"], f"role: '{keyword}' only in description, which may be company boilerplate")
        else:
            add(points["no_role_signal"], "role: no target role keyword found")

    if place["is_remote"] and place.get("remote_state"):
        add(points["whole_state_or_home_radius"], f"location: remote, tied to {place['remote_state']}")
    elif place["tier"] == "target_area":
        add(points["target_area"], f"location: {place['detail']}")
    elif place["tier"] == "whole_state":
        add(points["whole_state_or_home_radius"], f"location: in {place['detail']}")
    elif place["tier"] == "home_radius":
        add(points["whole_state_or_home_radius"], f"location: {place['detail']}")
    elif place["tier"] in ("unknown", "placeholder"):
        add(points["location_unknown"], "location: unknown")
    else:
        add(0, "location: outside target locations")

    season = listing["season"]
    weights = {s["name"]: s["weight"] for s in cfg["seasons"]}
    if season in weights:
        add(round(points["season_max"] * weights[season]), f"season: {season} (weight {weights[season]})")
    elif season:
        add(0, f"season: {season} is not in config")
    else:
        add(points["season_not_stated"], "season: not stated")

    status = listing["eligibility"]["status"]
    if status == "eligible":
        add(points["eligible"], "eligibility: eligible")
    elif status == "ineligible":
        add(points["ineligible"], "eligibility: ineligible")
    else:
        add(points["eligibility_unclear"], "eligibility: unclear")

    if role["early_signals"]:
        add(points["early_career"], f"early-career signal: '{role['early_signals'][0]}'")

    final = max(0, min(points["max_score"], total))
    if final != total:
        reasons.append(f"score limited to {final} (raw total {total})")
    if not role["category"] and final > points["no_role_cap"]:
        final = points["no_role_cap"]
        reasons.append(f"score capped at {final}: no role category matched (raw total {total})")
    return final, reasons
