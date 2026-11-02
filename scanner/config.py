"""Load and validate the YAML files, reporting every problem at once."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from . import gazetteer
from .location import STATE_NAMES

ATS_VALUES = {"greenhouse", "lever", "ashby", "smartrecruiters", "workday", "manual"}
REMOTE_VALUES = {"include", "exclude", "separate"}
SEASON_NAME = re.compile(r"^(Spring|Summer|Fall|Winter) 20\d\d$|^Early-career program$")
SLUG = re.compile(r"^[A-Za-z0-9_.-]+$")
WORKDAY_URL = re.compile(r"^https://[\w-]+\.wd\d+\.myworkdayjobs\.com/[\w-]+$")
TOP_LEVEL_KEYS = {
    "profile", "home", "radius_miles", "target_areas", "include_whole_states", "remote", "remote_allowed_states",
    "seasons", "role_categories", "must_be_one_of", "exclude_keywords", "eligibility",
    "status", "new_badge_days", "email", "contacts", "program_title_terms", "scoring", "workday", "geocoding",
}
SCORING_KEYS = {
    "role_in_title", "role_only_in_description", "no_role_signal", "target_area", "whole_state_or_home_radius",
    "location_unknown", "season_max", "season_not_stated", "eligible", "eligibility_unclear", "ineligible",
    "early_career", "no_role_cap", "max_score",
}
COMPANY_KEYS = {"name", "ats", "board", "cities", "priority", "notes"}


class ConfigError(Exception):
    """Raised with a message that says exactly what to fix."""


def _read_yaml(path: Path):
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        raise ConfigError(f"{path}: file not found") from None
    except yaml.YAMLError as err:
        raise ConfigError(f"{path}: not valid YAML: {err}") from None


def _fail_if_any(path: Path, errors: list) -> None:
    if errors:
        raise ConfigError(f"{path} has {len(errors)} problem(s):\n" + "\n".join(f"  - {e}" for e in errors))


def _is_string_list(value) -> bool:
    return isinstance(value, list) and all(isinstance(x, str) and x.strip() for x in value)


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def company_id(name: str) -> str:
    """Stable slug: 'Cottingham & Butler' becomes 'cottingham-butler'."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def load_cities(path: Path, gaz=None) -> list:
    """Return the city list with coordinates from the Census Gazetteer (D-022)."""
    data = _read_yaml(path)
    try:
        gaz = gaz or gazetteer.default()
    except (OSError, ValueError) as err:
        raise ConfigError(f"The Census Gazetteer could not be read: {err}") from None
    errors, out = [], []
    cities = data.get("cities") if isinstance(data, dict) else None
    if not isinstance(cities, list) or not cities:
        errors.append("'cities' must be a non-empty list")
        cities = []
    for i, c in enumerate(cities):
        if not (isinstance(c, dict) and set(c) == {"city", "state"} and isinstance(c["city"], str) and isinstance(c["state"], str)):
            errors.append(f"cities[{i}]: needs exactly city and state; coordinates come from the Census Gazetteer")
            continue
        found = gaz.lookup(c["city"], c["state"])
        if found:
            out.append(found)
        else:
            errors.append(f"cities[{i}]: {c['city']}, {c['state']} is not in the Census Gazetteer")
    _fail_if_any(path, errors)
    return out


def load_config(path: Path, cities: list) -> dict:
    cfg = _read_yaml(path)
    if not isinstance(cfg, dict):
        raise ConfigError(f"{path}: the top level must be a set of settings")

    errors = []
    for key in sorted(set(cfg) - TOP_LEVEL_KEYS):
        errors.append(f"unknown setting '{key}'")
    for key in sorted(TOP_LEVEL_KEYS - set(cfg)):
        errors.append(f"missing setting '{key}'")

    grad = (cfg.get("profile") or {}).get("grad_date")
    if not (isinstance(grad, str) and re.fullmatch(r"20\d\d-(0[1-9]|1[0-2])", grad)):
        errors.append("profile.grad_date must look like \"2029-05\"")

    known = {(c["city"].lower(), c["state"].upper()) for c in cities}
    home = cfg.get("home")
    if not (isinstance(home, dict) and (str(home.get("city")).lower(), str(home.get("state")).upper()) in known):
        errors.append("home must name a city and state listed in config/cities.yaml")
    if not _is_number(cfg.get("radius_miles")) or cfg.get("radius_miles", 0) < 0:
        errors.append("radius_miles must be a number, 0 or more")

    areas = cfg.get("target_areas")
    if not isinstance(areas, list):
        errors.append("target_areas must be a list")
        areas = []
    for i, area in enumerate(areas):
        if not isinstance(area, dict) or set(area) != {"name", "center", "radius_miles"}:
            errors.append(f"target_areas[{i}]: needs exactly name, center, radius_miles")
            continue
        parts = [p.strip() for p in str(area["center"]).split(",")]
        if len(parts) != 2 or (parts[0].lower(), parts[1].upper()) not in known:
            errors.append(f"target_areas[{i}]: center '{area['center']}' must be 'City, ST' and listed in config/cities.yaml")
        if not _is_number(area["radius_miles"]) or area["radius_miles"] <= 0:
            errors.append(f"target_areas[{i}]: radius_miles must be above 0")

    if not _is_string_list(cfg.get("include_whole_states")):
        errors.append("include_whole_states must be a list of state codes")
    if cfg.get("remote") not in REMOTE_VALUES:
        errors.append(f"remote must be one of {sorted(REMOTE_VALUES)}")
    allowed = cfg.get("remote_allowed_states")
    if not (isinstance(allowed, list) and all(isinstance(s, str) and s in STATE_NAMES for s in allowed)):
        errors.append("remote_allowed_states must be a list of two-letter state codes, such as [\"IA\"]")

    seasons = cfg.get("seasons")
    if not isinstance(seasons, list) or not seasons:
        errors.append("seasons must be a non-empty list of {name, weight}")
        seasons = []
    seen = set()
    for i, season in enumerate(seasons):
        if not isinstance(season, dict) or not {"name", "weight"} <= set(season) <= {"name", "weight", "max_miles_from_home"}:
            errors.append(f"seasons[{i}]: must have exactly name and weight, plus optional max_miles_from_home, "
                          f"e.g. {{ name: \"Summer 2027\", weight: 1.0 }}")
            continue
        if "max_miles_from_home" in season and not (_is_number(season["max_miles_from_home"]) and season["max_miles_from_home"] > 0):
            errors.append(f"seasons[{i}]: max_miles_from_home must be a number above 0")
        if not (isinstance(season["name"], str) and SEASON_NAME.match(season["name"])):
            errors.append(f"seasons[{i}]: name '{season['name']}' must look like 'Summer 2027' or be 'Early-career program'")
        if not _is_number(season["weight"]) or not 0 <= season["weight"] <= 1:
            errors.append(f"seasons[{i}]: weight must be a number from 0 to 1")
        if season["name"] in seen:
            errors.append(f"seasons[{i}]: duplicate season '{season['name']}'")
        seen.add(season["name"])

    roles = cfg.get("role_categories")
    if not isinstance(roles, dict) or not roles or not all(_is_string_list(v) and v for v in roles.values()):
        errors.append("role_categories must map each category to a non-empty list of keywords")
    for key in ("must_be_one_of", "exclude_keywords", "program_title_terms"):
        if not _is_string_list(cfg.get(key)) or not cfg.get(key):
            errors.append(f"{key} must be a non-empty list of strings")

    years = (cfg.get("eligibility") or {}).get("exclude_if_restricted_to_grad_years")
    if not (isinstance(years, list) and all(isinstance(y, int) and not isinstance(y, bool) for y in years)):
        errors.append("eligibility.exclude_if_restricted_to_grad_years must be a list of years")

    status = cfg.get("status") or {}
    near, closed = status.get("possibly_closed_after_missed_runs"), status.get("closed_after_missed_runs")
    if not (isinstance(near, int) and isinstance(closed, int) and 0 < near <= closed):
        errors.append("status: possibly_closed_after_missed_runs must be above 0 and not more than closed_after_missed_runs")
    guard = status.get("empty_response_min_open")
    if not (isinstance(guard, int) and not isinstance(guard, bool) and guard > 0):
        errors.append("status.empty_response_min_open must be a whole number above 0")
    if not isinstance(cfg.get("new_badge_days"), int) or cfg.get("new_badge_days", 0) < 0:
        errors.append("new_badge_days must be a whole number, 0 or more")

    email = cfg.get("email") or {}
    if not (_is_number(email.get("min_score")) and 0 <= email["min_score"] <= 100):
        errors.append("email.min_score must be a number from 0 to 100")

    scoring = cfg.get("scoring")
    if not isinstance(scoring, dict) or set(scoring) != SCORING_KEYS:
        have = set(scoring) if isinstance(scoring, dict) else set()
        errors.append(f"scoring must have exactly these settings; missing {sorted(SCORING_KEYS - have)}, unknown {sorted(have - SCORING_KEYS)}")
    else:
        for key, value in sorted(scoring.items()):
            if not _is_number(value):
                errors.append(f"scoring.{key} must be a number")
        if _is_number(scoring["no_role_cap"]) and _is_number(scoring["max_score"]) and not 0 <= scoring["no_role_cap"] <= scoring["max_score"]:
            errors.append("scoring.no_role_cap must be from 0 to max_score")

    workday = cfg.get("workday") or {}
    if not _is_string_list(workday.get("search_terms")) or not workday.get("search_terms"):
        errors.append("workday.search_terms must be a non-empty list of strings")
    for key in ("page_size", "max_results_per_term"):
        if not (isinstance(workday.get(key), int) and not isinstance(workday.get(key), bool) and workday.get(key) > 0):
            errors.append(f"workday.{key} must be a whole number above 0")

    geocoding = cfg.get("geocoding") or {}
    if not isinstance(geocoding.get("enabled"), bool):
        errors.append("geocoding.enabled must be true or false")
    if not (_is_number(geocoding.get("min_seconds_between_requests")) and geocoding.get("min_seconds_between_requests") >= 1):
        errors.append("geocoding.min_seconds_between_requests must be 1 or more")
    if not (isinstance(geocoding.get("max_lookups_per_run"), int) and geocoding.get("max_lookups_per_run") >= 0):
        errors.append("geocoding.max_lookups_per_run must be a whole number, 0 or more")

    _fail_if_any(path, errors)
    return cfg


def load_companies(path: Path) -> list:
    data = _read_yaml(path)
    companies = data.get("companies") if isinstance(data, dict) else None
    if not isinstance(companies, list) or not companies:
        raise ConfigError(f"{path}: 'companies' must be a non-empty list")

    errors, ids, out = [], set(), []
    for i, c in enumerate(companies):
        if not isinstance(c, dict):
            errors.append(f"companies[{i}]: must be a set of fields")
            continue
        label = c.get("name", f"companies[{i}]")
        if set(c) != COMPANY_KEYS:
            problems = sorted(COMPANY_KEYS - set(c)) + [f"unknown:{k}" for k in sorted(set(c) - COMPANY_KEYS)]
            errors.append(f"{label}: wrong fields {problems}")
            continue
        ats, board = c["ats"], c["board"]
        if ats not in ATS_VALUES:
            errors.append(f"{label}: ats '{ats}' must be one of {sorted(ATS_VALUES)}")
        elif ats == "workday":
            if not (isinstance(board, str) and WORKDAY_URL.match(board)):
                errors.append(f"{label}: workday board must be a https://tenant.wdN.myworkdayjobs.com/site URL")
        elif ats == "manual":
            if board is not None and not (isinstance(board, str) and board.startswith("https://")):
                errors.append(f"{label}: manual board must be a https:// URL or null")
        elif not (isinstance(board, str) and SLUG.match(board)):
            errors.append(f"{label}: {ats} board must be a slug with no spaces")
        if not (isinstance(c["cities"], list) and all(isinstance(x, str) for x in c["cities"])):
            errors.append(f"{label}: cities must be a list of strings")
        if c["priority"] not in (1, 2, 3):
            errors.append(f"{label}: priority must be 1, 2, or 3")
        if not (isinstance(c["notes"], str) and c["notes"].strip()):
            errors.append(f"{label}: notes must not be empty")
        cid = company_id(str(c["name"]))
        if cid in ids:
            errors.append(f"{label}: duplicate company")
        ids.add(cid)
        out.append({**c, "company_id": cid})

    _fail_if_any(path, errors)
    return out
