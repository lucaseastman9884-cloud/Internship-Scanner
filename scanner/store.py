"""Dedupe, upsert, and write the data files. Listings are never deleted."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .text import normalized_title


class StoreError(Exception):
    pass


def read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except ValueError as err:
        # Stop rather than overwrite history with an empty file.
        raise StoreError(f"{path} is damaged and was left untouched: {err}") from None


def write_json(path: Path, data) -> None:
    """Sorted keys and a fixed layout keep reruns byte-identical. Writing to a temp file first
    means a crash cannot leave half a file behind."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.chmod(tmp, 0o644)  # temp files start private; these are ordinary project files
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def public_fields(listing: dict) -> dict:
    return {k: v for k, v in listing.items() if not k.startswith("_")}


def dedupe_key(listing: dict) -> tuple:
    return (listing["company_id"], normalized_title(listing["title"]), (listing["city"] or "").lower())


def _source_key(source: dict) -> tuple:
    return (source["source_name"], str(source["source_job_id"]))


def _merge_sources(*groups) -> list:
    merged = {}
    for group in groups:
        for source in group:
            merged.setdefault(_source_key(source), source)
    return [merged[k] for k in sorted(merged)]


def dedupe(listings: list) -> list:
    """Same company, normalized title, and city becomes one listing that keeps every source link."""
    groups: dict = {}
    for listing in sorted(listings, key=lambda x: x["id"]):
        key = dedupe_key(listing)
        if key in groups:
            groups[key]["sources"] = _merge_sources(groups[key]["sources"], listing["sources"])
        else:
            groups[key] = {**listing}
    return list(groups.values())


def upsert(existing: list, incoming: list, today: str) -> tuple:
    """Merge a run's listings into history. Returns (all listings, new count, updated count)."""
    records = {r["id"]: {**r} for r in existing}
    by_source = {}
    by_key = {}
    for record in records.values():
        by_key[dedupe_key(record)] = record["id"]
        for source in record["sources"]:
            by_source[_source_key(source)] = record["id"]

    added = updated = 0
    for listing in dedupe(incoming):
        fresh = public_fields(listing)
        match = next((by_source[_source_key(s)] for s in fresh["sources"] if _source_key(s) in by_source), None)
        match = match or by_key.get(dedupe_key(fresh))
        if match:
            old = records[match]
            records[match] = {**fresh, "id": old["id"], "first_seen": old["first_seen"], "last_seen": today,
                              "sources": _merge_sources(old["sources"], fresh["sources"])}
            target = match
            updated += 1
        else:
            records[fresh["id"]] = {**fresh, "first_seen": today, "last_seen": today}
            target = fresh["id"]
            added += 1
        by_key[dedupe_key(records[target])] = target
        for source in records[target]["sources"]:
            by_source[_source_key(source)] = target

    return [records[i] for i in sorted(records)], added, updated


def update_company_status(previous: dict, company: dict, checked_at: str, ok: bool, today: str,
                          open_count: int = 0, latest_title=None, error=None) -> dict:
    """One company's permanent record. A failed fetch keeps the last known counts."""
    entry = dict(previous or {})
    entry.update(company_id=company["company_id"], company=company["name"], ats=company["ats"], last_checked=checked_at)
    entry.setdefault("last_intern_posting_seen", None)
    entry.setdefault("open_intern_count", 0)
    if ok:
        entry["open_intern_count"] = open_count
        if latest_title:
            entry["last_intern_posting_seen"] = {"title": latest_title, "seen_on": today}
        entry["fetch_health"] = {"status": "ok", "consecutive_failures": 0, "last_error": None}
    else:
        failures = (entry.get("fetch_health") or {}).get("consecutive_failures", 0) + 1
        entry["fetch_health"] = {"status": "error", "consecutive_failures": failures, "last_error": error}
    return entry
