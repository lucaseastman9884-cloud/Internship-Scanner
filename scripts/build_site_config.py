"""Write site_config.json for the web app (P7), at deploy time. It is never committed.

The app reads every config-dependent value from this file, so nothing in site/ repeats
config/config.yaml (D-020 spirit). Only display values go in: no keyword lists, no scoring
points, no profile, and no contacts settings, because the site is public.

Usage: python scripts/build_site_config.py OUT_PATH
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

SCHEMA_VERSION = 1
NOT_STATED = "Not stated"  # the email's season filter uses the same words (D-033)


def _place(cities: list, text: str) -> dict:
    """'Des Moines, IA' → its Gazetteer coordinates. load_config has already checked it's listed."""
    city, state = [p.strip() for p in text.split(",")]
    for c in cities:
        if c["city"].lower() == city.lower() and c["state"].upper() == state.upper():
            return {"lat": c["lat"], "lng": c["lng"]}
    raise ValueError(f"{text} is not in config/cities.yaml")


def build(cfg: dict, cities: list, now: datetime = None) -> dict:
    now = now or datetime.now(timezone.utc)
    home = f"{cfg['home']['city']}, {cfg['home']['state']}"
    remote_states = [s.upper() for s in cfg["remote_allowed_states"]] if cfg["remote"] == "separate" else []
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now.replace(microsecond=0).isoformat(),
        "home": {"name": home, **_place(cities, home)},
        "radius_miles": cfg["radius_miles"],
        "target_areas": [
            {"name": a["name"], "center": a["center"], **_place(cities, a["center"]), "radius_miles": a["radius_miles"]}
            for a in cfg["target_areas"]
        ],
        "seasons": [s["name"] for s in cfg["seasons"]] + [NOT_STATED],
        "role_categories": list(cfg["role_categories"]),
        "new_badge_days": cfg["new_badge_days"],
        # D-029: listings tagged like this get their own section, never mixed into the in-person list.
        "remote_sections": [{"tag": remote_tag(s), "label": f"Remote — {STATE_NAMES[s].title()}"} for s in remote_states],
        # For "(title says City, ST)" on location_conflict listings, matching scanner/location.py.
        "state_codes": sorted(STATE_CODES),
    }


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: python scripts/build_site_config.py OUT_PATH", file=sys.stderr)
        return 2
    cities = load_cities(ROOT / "config" / "cities.yaml")
    cfg = load_config(ROOT / "config" / "config.yaml", cities)
    out = Path(argv[0])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build(cfg, cities), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
