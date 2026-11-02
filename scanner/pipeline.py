"""The runner: fetch each company, evaluate its listings, and write the data files."""
from __future__ import annotations

import datetime as dt
from collections import Counter
from pathlib import Path

from . import eligibility, filtering, history, normalize, scoring, store
from .adapters import ADAPTERS
from .config import load_cities, load_companies, load_config
from .geocode import Geocoder
from .http_client import FormatChanged, HttpClient, HttpError, RobotsBlocked, RobotsUnreadable
from .location import LocationResolver
from .text import scrub_contact_data

MAX_UNRESOLVED_LOGGED = 50


class EmptyResponse(Exception):
    """A source that had listings suddenly returned none. Far more likely a glitch than every job closing."""


FAILED_STATUSES = ("error", "manual_fallback")
LIVE_STATUSES = ("ok",) + FAILED_STATUSES


def too_many_failures(meta: dict) -> bool:
    """More than half of live companies failing means something bigger than one source is wrong."""
    return meta["totals"]["companies_failed"] * 2 > meta["totals"]["companies_live"]


def _evaluate(listing, cfg, resolver):
    """Run a listing through normalization, eligibility, filtering, and scoring, in place."""
    # Only possible internships may use the geocoder; other jobs are dropped whatever their city.
    place = normalize.enrich(listing, cfg, resolver, allow_lookup=filtering.is_internship(listing["title"], cfg))
    listing["eligibility"] = eligibility.evaluate(listing["title"], listing["_description"], listing["season"], cfg)
    exclusions = filtering.evaluate(listing, place, cfg)
    listing["relevance_score"], listing["match_reasons"] = scoring.score(listing, place, cfg)
    return place, exclusions


def _wants_detail(cfg, resolver):
    def check(listing):
        if not filtering.is_internship(listing["title"], cfg) or filtering.title_exclude_keyword(listing["title"], cfg):
            return False
        place = resolver.resolve(listing["location_raw"], listing["is_remote"])
        if place["is_remote"]:
            return filtering.remote_allowed(place, cfg)
        return place["tier"] is not None
    return check


def _fallback(company):
    """The careers link shown under "check manually" when a company cannot be fetched."""
    board = str(company["board"] or "")
    if board.startswith("https://"):
        return board
    if not board:
        return None
    return {
        "smartrecruiters": f"https://careers.smartrecruiters.com/{board}",
        "greenhouse": f"https://job-boards.greenhouse.io/{board}",
        "lever": f"https://jobs.lever.co/{board}",
        "ashby": f"https://jobs.ashbyhq.com/{board}",
    }.get(company["ats"])


def _needs_manual_fallback(err) -> bool:
    """Blocked or changed: retrying tomorrow would not help, so a person should look (D-002).
    Server errors and timeouts are ordinary failures and stay "error"."""
    if isinstance(err, RobotsUnreadable):
        return False
    if isinstance(err, (RobotsBlocked, FormatChanged)):
        return True
    return isinstance(err, HttpError) and err.status is not None and 400 <= err.status < 500


def _base_row(company):
    return {"company": company["name"], "company_id": company["company_id"], "ats": company["ats"],
            "status": "", "fetched": 0, "kept": 0, "excluded": 0, "exclusion_reasons": {},
            "error": None, "warnings": [], "fallback_link": None}


def _listing_check(company, adapter):
    """D-025: one listing's check, whose failure proves nothing and never counts as a miss."""
    def check(record):
        try:
            return adapter.still_open(company, record)
        except Exception as err:  # deliberately broad, as with a whole company's fetch
            adapter.warnings.append(scrub_contact_data(f"could not check '{record['title']}': {type(err).__name__}: {err}"))
            return "failed"
    return check


def _process_company(company, adapter, cfg, resolver, unresolved, open_before):
    # The adapter sets "complete" during fetch, so this must run before the caller reads it.
    listings = adapter.fetch(company, _wants_detail(cfg, resolver))
    if not listings and open_before >= cfg["status"]["empty_response_min_open"]:
        raise EmptyResponse(f"returned 0 jobs but had {open_before} open listings last run, so this counts as a failed fetch")
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
    client = client or HttpClient()
    geocache_path = data_dir / "geocache.json"
    geocache = store.read_json(geocache_path, {})
    geocoder = Geocoder(client, geocache, cfg["geocoding"])
    resolver = LocationResolver(cfg, cities, geocoder)
    adapters = ADAPTERS if adapters is None else adapters

    # Read history first, so damaged files stop the run before any network traffic.
    status_path = data_dir / "companies_status.json"
    existing = store.load_listings(data_dir)
    statuses = store.read_json(status_path, {})

    rows, all_kept, excluded_report = [], [], []
    results = {}  # only companies fetched successfully; history must not touch the others
    unresolved = Counter()
    open_before = Counter(r["company_id"] for r in existing if r["status"] == "open")
    for company in companies:
        row = _base_row(company)
        ats = company["ats"]
        if ats == "manual":
            row.update(status="manual", fallback_link=_fallback(company))
            statuses[company["company_id"]] = store.update_company_status(
                statuses.get(company["company_id"]), company, started, False, today, status="manual", careers_url=_fallback(company))
        elif ats not in adapters:
            row.update(status="skipped", error=f"no {ats} adapter is active", fallback_link=_fallback(company))
        else:
            adapter = adapters[ats](client, cfg)
            cid = company["company_id"]
            try:
                listings, kept, excluded, open_interns, latest = _process_company(
                    company, adapter, cfg, resolver, unresolved, open_before[cid])
            except Exception as err:  # deliberately broad: any failure stays inside this company
                status = "manual_fallback" if _needs_manual_fallback(err) else "error"
                message = scrub_contact_data(f"{type(err).__name__}: {err}")
                row.update(status=status, error=message, fallback_link=_fallback(company), warnings=adapter.warnings)
                statuses[cid] = store.update_company_status(statuses.get(cid), company, started, False, today, error=message,
                                                            status=status, careers_url=_fallback(company))
            else:
                reasons = Counter(code for _, ex in excluded for code, _text in ex[:1])
                row.update(status="ok", fetched=len(listings), kept=len(kept), excluded=len(excluded),
                           exclusion_reasons=dict(sorted(reasons.items())), warnings=adapter.warnings)
                all_kept.extend(kept)
                results[cid] = {"kept": kept, "complete": adapter.complete, "check": _listing_check(company, adapter),
                                "excluded": [(listing, "; ".join(text for _, text in ex)) for listing, ex in excluded]}
                for listing, ex in excluded:
                    excluded_report.append({
                        "company": listing["company"], "title": listing["title"], "location_raw": listing["location_raw"],
                        "season": listing["season"], "eligibility": listing["eligibility"],
                        "relevance_score": listing["relevance_score"], "match_reasons": listing["match_reasons"],
                        "excluded_because": [text for _, text in ex], "primary_reason": ex[0][0],
                    })
                statuses[cid] = store.update_company_status(statuses.get(cid), company, started, True, today,
                                                            open_count=open_interns, latest_title=latest,
                                                            careers_url=_fallback(company), complete=adapter.complete)
        rows.append(row)

    merged, added, updated = store.upsert(existing, all_kept, today)
    changes = history.update_statuses(merged, results, today, cfg)
    history.update_recurring(merged)
    is_open = [r for r in merged if r["status"] == "open"]
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
            "companies_live": sum(r["status"] in LIVE_STATUSES for r in rows),
            "companies_failed": sum(r["status"] in FAILED_STATUSES for r in rows),
            "fetched": sum(r["fetched"] for r in rows),
            "kept": sum(r["kept"] for r in rows),
            "excluded": sum(r["excluded"] for r in rows),
            "listings_before": len(existing),
            "listings_new": added,
            "listings_updated": updated,
            "listings_after": len(merged),
            "status_changes": changes,
            "database_total": len(merged),
            "database_open": len(is_open),
            "open_at_or_above_min_score": sum(r["relevance_score"] >= cfg["email"]["min_score"] for r in is_open),
            "location_unknown_open": sum(r["location_label"] == "Location unknown" for r in is_open),
            "remote_iowa_open": sum("remote_iowa" in r["tags"] for r in is_open),
        },
        "source_health": dict(sorted(health.items())),
        "companies": rows,
        "errors": [{"company": r["company"], "ats": r["ats"], "status": r["status"], "error": r["error"]}
                   for r in rows if r["status"] in ("error", "manual_fallback")],
        # What the email's "check manually" section will list (D-002, D-011).
        "check_manually": [{"company": r["company"], "url": r["fallback_link"], "reason": r["status"], "detail": r["error"]}
                           for r in rows if r["status"] in ("manual", "manual_fallback", "skipped", "error")],
        "requests_by_host": dict(sorted(getattr(client, "request_counts", {}).items())),
        "geocoding": {"enabled": geocoder.enabled, **geocoder.stats},
        "unresolved_locations": dict(unresolved.most_common(MAX_UNRESOLVED_LOGGED)),
    }

    store.save_listings(data_dir, merged)
    store.write_json(geocache_path, geocache)
    store.write_json(status_path, dict(sorted(statuses.items())))
    store.write_json(data_dir / "meta.json", meta)
    store.write_json(data_dir / "excluded_last_run.json",
                     sorted(excluded_report, key=lambda x: (x["company"], x["title"], x["location_raw"])))
    return meta
