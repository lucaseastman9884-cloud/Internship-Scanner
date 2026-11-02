"""Status transitions and recurring programs. Listings are never deleted.

The rules that matter:
- A failed fetch says nothing about a listing, so it never counts as a miss.
- A partial fetch (a search that hit its cap) cannot prove absence either.
- Where the source can answer about one listing, it is asked before a miss is counted (D-025).
- A closed listing stays closed and unchanged, so the data file does not change for it every day.
- On the board but rejected by current config is "filtered", not closed.
"""
from __future__ import annotations

import re

from .store import dedupe_key, source_key
from .text import normalized_title

_SEASON_WORDS = re.compile(r"\b(spring|summer|fall|autumn|winter|20\d\d)\b")
_DATED_SEASON = re.compile(r"^(Spring|Summer|Fall|Winter) 20\d\d$")


def _keys(listings: list) -> tuple:
    sources, titles = set(), set()
    for listing in listings:
        titles.add(dedupe_key(listing))
        sources.update(source_key(s) for s in listing["sources"])
    return sources, titles


def _seen_in(record: dict, keys: tuple) -> bool:
    sources, titles = keys
    return dedupe_key(record) in titles or any(source_key(s) in sources for s in record["sources"])


def _leave_open(record: dict) -> None:
    """Remember the last day this listing was seen open, once, at the moment it stops being open."""
    if record["status"] == "open":
        record["last_known_open"] = record.get("last_seen")


def update_statuses(records: list, results: dict, today: str, cfg: dict) -> dict:
    """results holds only companies fetched successfully: {company_id: {kept, excluded, complete, check}}.

    check(record) answers about one listing: True (open), False (gone), None (no such check; the
    run's own results decide), or "failed" (proves nothing).
    """
    near, closed = cfg["status"]["possibly_closed_after_missed_runs"], cfg["status"]["closed_after_missed_runs"]
    counts = {"filtered": 0, "missed": 0, "possibly_closed": 0, "closed": 0, "verified_open": 0, "check_failed": 0}
    for record in records:
        result = results.get(record["company_id"])
        if result is None:
            continue  # failed fetch, manual, or no longer in the registry
        if _seen_in(record, _keys(result["kept"])):
            continue  # upsert already refreshed it as open
        reason = next((why for listing, why in result["excluded"] if _seen_in(record, _keys([listing]))), None)
        if reason is not None:
            _leave_open(record)
            record.update(status="filtered", filtered_reason=reason, missed_runs=0, last_seen=today)
            counts["filtered"] += 1
            continue
        if record["status"] == "closed":
            continue
        check = result.get("check")
        verdict = check(record) if check else None
        if verdict == "failed":
            counts["check_failed"] += 1
        elif verdict is True:
            # Still open, just absent from this run's search results.
            record.update(missed_runs=0, last_seen=today)
            if record["status"] == "possibly_closed":
                record["status"] = "open"
            counts["verified_open"] += 1
        elif verdict is False or result["complete"]:
            record["missed_runs"] = record.get("missed_runs", 0) + 1
            counts["missed"] += 1
            if record["missed_runs"] >= closed:
                _leave_open(record)
                record["status"] = "closed"
                counts["closed"] += 1
            elif record["missed_runs"] >= near:
                _leave_open(record)
                record["status"] = "possibly_closed"
                counts["possibly_closed"] += 1
    return counts


def program_key(record: dict) -> tuple:
    """The same program across seasons: 'Tax Intern - Summer 2027' and '2028 Summer Tax Internship'."""
    name = _SEASON_WORDS.sub(" ", normalized_title(record["title"]))
    return record["company_id"], re.sub(r"\s+", " ", name).strip()


def update_recurring(records: list) -> None:
    """recurring: the program appears in two or more dated seasons.

    last_known_open: on a listing no longer open, the last day it was seen open (set by _leave_open).
    On an open listing, the last day another season of the program was open; null if there is none.
    Both only change when a listing changes, so they do not rewrite the file every day.
    """
    groups: dict = {}
    for record in records:
        groups.setdefault(program_key(record), []).append(record)
    for group in groups.values():
        seasons = {r["season"] for r in group if r.get("season") and _DATED_SEASON.match(r["season"])}
        for record in group:
            record["recurring"] = len(seasons) >= 2
            if record["status"] == "open":
                earlier = [r["last_known_open"] for r in group if r is not record and r["status"] != "open"
                           and r.get("season") != record.get("season") and r.get("last_known_open")]
                record["last_known_open"] = max(earlier) if earlier else None
