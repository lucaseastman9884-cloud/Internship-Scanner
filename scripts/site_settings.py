"""The `site:` block of config/config.yaml (P8, D-045): display settings for the web app only.

Each value is checked on its own. A missing or bad value falls back to its default with a warning,
so a typo here can never break a deploy, let alone a scan. The defaults below are the fallbacks
from the P8 spec; the real values live in config.yaml (and docs/CONFIG.md).
"""
from __future__ import annotations

import re
import sys

DEFAULTS = {
    "posted_within_days": [1, 3, 7, 30],
    "default_sort": "score",
    "default_theme": "dark",
    "linkedin_school_id": "164452",
    "linkedin_school_name": "Iowa State University",
    "manual_first_tags": ["ib"],
    "deadline_window_days": 14,
}
# The sort keys site/js/lib.js knows. "newest_posted" uses date_posted, else first_seen.
SORTS = ("score", "newest_posted", "first_seen", "deadline", "company")
THEMES = ("dark", "light")
MAX_DAYS = 365


def warn(warnings: list, message: str) -> None:
    """Collect a warning and print it; on GitHub Actions it also shows as a yellow annotation."""
    warnings.append(message)
    print(f"::warning title=site_config::{message}", file=sys.stderr)


def _whole(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _check(key, value):
    """Return the cleaned value, or None if it's not acceptable."""
    if key == "posted_within_days":
        if isinstance(value, list) and value and all(_whole(v) and 1 <= v <= MAX_DAYS for v in value):
            return sorted(set(value))
        return None
    if key == "default_sort":
        return value if value in SORTS else None
    if key == "default_theme":
        return value if value in THEMES else None
    if key == "linkedin_school_id":
        # A number in LinkedIn's school filter. Quoted in YAML, but a bare number is accepted too.
        text = str(value) if _whole(value) else value
        return text if isinstance(text, str) and re.fullmatch(r"\d{1,12}", text) else None
    if key == "linkedin_school_name":
        return value.strip() if isinstance(value, str) and value.strip() and len(value) <= 120 else None
    if key == "manual_first_tags":
        if isinstance(value, list) and all(isinstance(v, str) and v.strip() for v in value):
            return [v.strip() for v in value]
        return None
    if key == "deadline_window_days":
        return value if _whole(value) and 0 <= value <= MAX_DAYS else None
    return None


def read(raw, warnings: list) -> dict:
    block_missing = raw is None or not isinstance(raw, dict)
    if raw is None:
        warn(warnings, "config.yaml has no site: block, so the site uses its defaults")
        raw = {}
    elif not isinstance(raw, dict):
        warn(warnings, "site: must be a set of settings, so the site uses its defaults")
        raw = {}
    for key in sorted(set(raw) - set(DEFAULTS)):
        warn(warnings, f"site.{key} is not a known setting and is ignored")
    out = {}
    for key, default in DEFAULTS.items():
        if key not in raw:
            if not block_missing:  # one warning for a missing block is enough
                warn(warnings, f"site.{key} is missing, so it uses {default!r}")
            out[key] = default
            continue
        clean = _check(key, raw[key])
        if clean is None:
            warn(warnings, f"site.{key} = {raw[key]!r} isn't valid, so it uses {default!r}")
            out[key] = default
        else:
            out[key] = clean
    return out


def linkedin_name(value, company: str, warnings: list):
    """An optional companies.yaml `linkedin_name`: a non-empty string, or None (with a warning if bad)."""
    if value is None:
        return None
    if isinstance(value, str) and value.strip() and len(value) <= 120:
        return value.strip()
    warn(warnings, f"{company}: linkedin_name {value!r} isn't a non-empty name, so the automatic short name is used")
    return None
