"""The runner: fetch each company, evaluate its listings, and write the data files."""
from __future__ import annotations

import datetime as dt
from collections import Counter
from pathlib import Path

from . import eligibility, filtering, normalize, scoring, store
from .adapters import ADAPTERS
from .config import load_cities, load_companies, load_config
from .http_client import HttpClient, RobotsBlocked
from .location import LocationResolver
from .text import scrub_contact_data

MAX_UNRESOLVED_LOGGED = 50


def _evaluate(listing, cfg, resolver):
    """Run a listing through normalization, eligibility, filtering, and scoring, in place."""
    place = normalize.enrich(listing, cfg, resolver)
    listing["eligibility"] = eligibility.evaluate(listing["title"], listing["_description"], listing["season"], cfg)
    exclusions = filtering.evaluate(listing, place, cfg)
    listing["relevance_score"], listing["match_reasons"] = scoring.score(listing, place, cfg)
    return place, exclusions


def _wants_detail(cfg, resolver):
    def check(listing):
        if not filtering.is_internship(listing["title"], cfg):
            return False
        place = resolver.resolve(listing["location_raw"], listing["is_remote"])
        if place["is_remote"]:
            return cfg["remote"] != "exclude"
        return place["tier"] is not None
    return check


def _fallback(company):
    """The careers link shown under "check manually" when a company cannot be fetched."""
    board = str(company["board"] or "")
    if board.startswith("https://"):
        return board
    if company["ats"] == "smartrecruiters" and board:
        return f"https://careers.smartrecruiters.com/{board}"
    return None


def _base_row(company):
    return {"company": company["name"], "company_id": company["company_id"], "ats": company["ats"],
            "status": "", "fetched": 0, "kept": 0, "excluded": 0, "exclusion_reasons": {},
            "error": None, "warnings": [], "fallback_link": None}


def _process_company(company, adapter, cfg, resolver, unresolved):
    listings = adapter.fetch(company, _wants_detail(cfg, resolver))
    kept, excluded = [], []
    open_interns, latest = 0, None
    for listing in listings:
        place, exclusions = _evaluate(listing, cfg, resolver)
        codes = {code for code, _ in exclusions}
        internship = "not_internship" not in codes
        if internship and not filtering.title_exclude_keyword(listing["title"], cfg):
            open_interns += 1
            current = (listing["date_posted"] or "", listing["title"])
            latest = max(latest, current) if latest else current
        if internship and not place["resolved"] and listing["location_raw"]:
            unresolved[listing["location_raw"]] += 1
        if exclusions:
            excluded.append((listing, exclusions))
        else:
            kept.append(listing)
    return listings, kept, excluded, open_interns, latest[1] if latest else None


def run(config_dir: Path, data_dir: Path, client=None, adapters=None, now=None) -> dict:
    """Run everything. One company's failure is logged and never stops the others."""
    clock_is_fixed = now is not None  # tests pin the time so that output files can be compared
    now = now or dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    started = now.isoformat()
    today = now.date().isoformat()

    cities = load_cities(config_dir / "cities.yaml")
    cfg = load_config(config_dir / "config.yaml", cities)
    companies = load_companies(config_dir / "companies.yaml")
    resolver = LocationResolver(cfg, cities)
    client = client or HttpClient()
    adapters = ADAPTERS if adapters is None else adapters

    # Read history first, so damaged files stop the run before any network traffic.
    listings_path = data_dir / "internships.json"
    status_path = data_dir / "companies_status.json"
    existing = store.read_json(listings_path, [])
    statuses = store.read_json(status_path, {})

    rows, all_kept, excluded_report = [], [], []
    unresolved = Counter()
    for company in companies:
        row = _base_row(company)
        ats = company["ats"]
        if ats == "manual":
            row.update(status="manual", fallback_link=_fallback(company))
        elif ats not in adapters:
            row.update(status="skipped", error="adapter not built yet (Workday arrives in P3)", fallback_link=_fallback(company))
        else:
            adapter = adapters[ats](client)
            cid = company["company_id"]
            try:
                listings, kept, excluded, open_interns, latest = _process_company(company, adapter, cfg, resolver, unresolved)
            except Exception as err:  # deliberately broad: any failure stays inside this company
                blocked = isinstance(err, RobotsBlocked)
                message = scrub_contact_data(f"{type(err).__name__}: {err}")
                row.update(status="blocked_by_robots" if blocked else "error", error=message, fallback_link=_fallback(company))
                statuses[cid] = store.update_company_status(statuses.get(cid), company, started, False, today, error=message)
            else:
                reasons = Counter(code for _, ex in excluded for code, _text in ex[:1])
                row.update(status="ok", fetched=len(listings), kept=len(kept), excluded=len(excluded),
                           exclusion_reasons=dict(sorted(reasons.items())), warnings=adapter.warnings)
                all_kept.extend(kept)
                for listing, ex in excluded:
                    excluded_report.append({
                        "company": listing["company"], "title": listing["title"], "location_raw": listing["location_raw"],
                        "season": listing["season"], "eligibility": listing["eligibility"],
                        "relevance_score": listing["relevance_score"], "match_reasons": listing["match_reasons"],
                        "excluded_because": [text for _, text in ex], "primary_reason": ex[0][0],
                    })
                statuses[cid] = store.update_company_status(statuses.get(cid), company, started, True, today,
                                                            open_count=open_interns, latest_title=latest)
        rows.append(row)

    merged, added, updated = store.upsert(existing, all_kept, today)
    health = {}
    for row in rows:
        counts = health.setdefault(row["ats"], {})
        counts[row["status"]] = counts.get(row["status"], 0) + 1

    finished = (now if clock_is_fixed else dt.datetime.now(dt.timezone.utc).replace(microsecond=0)).isoformat()
    meta = {
        "run_started": started,
        "run_finished": finished,
        "totals": {
            "companies": len(rows),
            "companies_fetched_ok": sum(r["status"] == "ok" for r in rows),
            "fetched": sum(r["fetched"] for r in rows),
            "kept": sum(r["kept"] for r in rows),
            "excluded": sum(r["excluded"] for r in rows),
            "listings_before": len(existing),
            "listings_new": added,
            "listings_updated": updated,
            "listings_after": len(merged),
        },
        "source_health": dict(sorted(health.items())),
        "companies": rows,
        "errors": [{"company": r["company"], "ats": r["ats"], "status": r["status"], "error": r["error"]}
                   for r in rows if r["status"] in ("error", "blocked_by_robots")],
        "unresolved_locations": dict(unresolved.most_common(MAX_UNRESOLVED_LOGGED)),
    }

    store.write_json(listings_path, merged)
    store.write_json(status_path, dict(sorted(statuses.items())))
    store.write_json(data_dir / "meta.json", meta)
    store.write_json(data_dir / "excluded_last_run.json",
                     sorted(excluded_report, key=lambda x: (x["company"], x["title"], x["location_raw"])))
    return meta
