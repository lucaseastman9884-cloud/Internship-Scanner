"""Write site_config.json for the web app (P7), at deploy time. It is never committed.

The app reads every config-dependent value from this file, so nothing in site/ repeats
config/config.yaml (D-020 spirit). Only display values go in: no keyword lists, no scoring
points, no profile, and no contacts settings, because the site is public.

This script must never be able to stop the Daily scan or break a deploy over a display value:
a place that can't be found is skipped, and a bad `site:` value falls back to its default,
with a warning, and the file is still written (P8).

Usage: python scripts/build_site_config.py OUT_PATH [--last-scan-ran ISO_TIME]
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scanner.config import load_cities, load_config  # noqa: E402  (needs the path above)
from scanner.location import STATE_CODES, STATE_NAMES, remote_tag  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
import site_settings  # noqa: E402
from site_settings import warn  # noqa: E402

SCHEMA_VERSION = 2
NOT_STATED = "Not stated"  # the email's season filter uses the same words (D-033)


def _place(cities: list, text: str):
    """'Des Moines, IA' → its Gazetteer coordinates, or None when it isn't listed."""
    parts = [p.strip() for p in str(text).split(",")]
    if len(parts) != 2:
        return None
    city, state = parts
    for c in cities:
        if c["city"].lower() == city.lower() and c["state"].upper() == state.upper():
            return {"lat": c["lat"], "lng": c["lng"]}
    return None


def parse_time(value):
    """An ISO 8601 time from the GitHub API → a normalised UTC string, or None. Never a guess."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        t = datetime.fromisoformat(text)
    except ValueError:
        return None
    if t.tzinfo is None:
        return None
    return t.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def build(cfg: dict, cities: list, now: datetime = None, last_scan_ran=None, warnings: list = None) -> dict:
    warnings = [] if warnings is None else warnings
    now = now or datetime.now(timezone.utc)

    home_name = f"{cfg['home']['city']}, {cfg['home']['state']}"
    home_place = _place(cities, home_name)
    if home_place is None:
        warn(warnings, f"home '{home_name}' isn't in config/cities.yaml, so the distance filter is off on the site")
    home = {"name": home_name, **(home_place or {"lat": None, "lng": None})}

    areas = []
    for a in cfg["target_areas"]:
        place = _place(cities, a["center"])
        if place is None:
            warn(warnings, f"target area '{a['name']}' ({a['center']}) isn't in config/cities.yaml, so the site skips it")
            continue
        areas.append({"name": a["name"], "center": a["center"], **place, "radius_miles": a["radius_miles"]})

    remote_states = [s.upper() for s in cfg["remote_allowed_states"]] if cfg["remote"] == "separate" else []
    out = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now.replace(microsecond=0).isoformat(),
        "home": home,
        "radius_miles": cfg["radius_miles"],
        "target_areas": areas,
        "seasons": [s["name"] for s in cfg["seasons"]] + [NOT_STATED],
        "role_categories": list(cfg["role_categories"]),
        "new_badge_days": cfg["new_badge_days"],
        # D-029: listings tagged like this get their own section, never mixed into the in-person list.
        "remote_sections": [{"tag": remote_tag(s), "label": f"Remote — {STATE_NAMES[s].title()}"}
                            for s in remote_states if s in STATE_NAMES],
        # For "(title says City, ST)" on location_conflict listings, matching scanner/location.py.
        "state_codes": sorted(STATE_CODES),
        # P8: the `site:` block, checked value by value (a bad one falls back to its default).
        "site": site_settings.read(cfg.get("site"), warnings),
    }
    # P8: when the latest successful Daily scan finished. Left out, never faked, when unknown.
    ran = parse_time(last_scan_ran)
    if ran:
        out["last_scan_ran"] = ran
    elif last_scan_ran:
        warn(warnings, f"--last-scan-ran '{last_scan_ran}' isn't an ISO time with a timezone, so it's left out")
    return out


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    last_scan_ran = None
    if "--last-scan-ran" in argv:
        i = argv.index("--last-scan-ran")
        if i + 1 >= len(argv):
            print("usage: python scripts/build_site_config.py OUT_PATH [--last-scan-ran ISO_TIME]", file=sys.stderr)
            return 2
        last_scan_ran = argv[i + 1]
        del argv[i:i + 2]
    if len(argv) != 1:
        print("usage: python scripts/build_site_config.py OUT_PATH [--last-scan-ran ISO_TIME]", file=sys.stderr)
        return 2
    cities = load_cities(ROOT / "config" / "cities.yaml")
    cfg = load_config(ROOT / "config" / "config.yaml", cities)
    out = Path(argv[0])
    out.parent.mkdir(parents=True, exist_ok=True)
    warnings = []
    out.write_text(json.dumps(build(cfg, cities, last_scan_ran=last_scan_ran, warnings=warnings), indent=2) + "\n",
                   encoding="utf-8")
    print(f"wrote {out}" + (f" with {len(warnings)} warning(s)" if warnings else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
