"""Write companies.json for the web app (P8, D-045), at deploy time. It is never committed.

data/companies_status.json has each company's fetch health and counts, but not its tags,
priority, cities or a manual careers link. Those come from config/companies.yaml, and only
public-safe fields are copied: no `notes` (free text written for Lucas), nothing else.

Usage: python scripts/build_companies.py OUT_PATH
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scanner.config import ConfigError, load_companies  # noqa: E402
import site_settings  # noqa: E402
from site_settings import warn  # noqa: E402

SCHEMA_VERSION = 1
FIELDS = ("id", "name", "ats", "careers_url", "cities", "priority", "tags", "linkedin_name")


def public_entry(c: dict, warnings: list) -> dict:
    board = c.get("board")
    # A manual board is a careers URL (https only, checked by the loader). A live board's URL comes
    # from companies_status.json, so only https values are copied here. The site re-checks any link.
    url = board if isinstance(board, str) and board.startswith("https://") else None
    return {
        "id": c["company_id"],
        "name": c["name"],
        "ats": c["ats"],
        "careers_url": url,
        "cities": [x for x in c.get("cities") or [] if isinstance(x, str)],
        "priority": c["priority"],
        "tags": list(c.get("tags") or []),
        "linkedin_name": site_settings.linkedin_name(c.get("linkedin_name"), c["name"], warnings),
    }


def build(companies: list, warnings: list = None) -> dict:
    warnings = [] if warnings is None else warnings
    return {"schema_version": SCHEMA_VERSION, "companies": [public_entry(c, warnings) for c in companies]}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    if len(argv) != 1:
        print("usage: python scripts/build_companies.py OUT_PATH", file=sys.stderr)
        return 2
    warnings = []
    try:
        companies = load_companies(ROOT / "config" / "companies.yaml")
    except ConfigError as err:
        # The site still works from companies_status.json alone, so this never stops a deploy.
        warn(warnings, f"config/companies.yaml couldn't be read, so companies.json is empty: {err}")
        companies = []
    out = Path(argv[0])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build(companies, warnings), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out}" + (f" with {len(warnings)} warning(s)" if warnings else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
