#!/usr/bin/env python3
"""Write a short result to the Actions run page, and a yellow warning for each failed company."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

META = "data/meta.json"
COMMIT_MEANINGS = {
    "data": "Saved: listings changed, so data/ was committed.",
    "keepalive": "Saved: no listing changed, so only the weekly keepalive was committed.",
    "none": "Nothing committed: no listing changed.",
}


def _clean(text) -> str:
    """Keep a workflow command or table cell on one line, whatever a website's error said."""
    return str(text or "").replace("\r", " ").replace("\n", " ").replace("|", "/").replace("::", ": :")


def _meta_is_fresh(repo: Path) -> bool:
    done = subprocess.run(["git", "status", "--porcelain", "--", META], cwd=repo, capture_output=True, text=True)
    return bool(done.stdout.strip())


EMAIL_MEANINGS = {
    "success": "Email step: done. The log says whether it was sent or skipped for a missing secret.",
    "failure": "**Email step failed.** The log shows Gmail's reply. The data was still saved.",
}


def build(meta, tests: str, scan: str, commit_action: str, email: str = "") -> str:
    """meta is None when this run produced none, because the tests failed or the scan crashed."""
    lines = ["## Daily scan", ""]
    if tests != "success":
        lines += [f"**Tests: {tests}.** The scan did not run, and no data was committed."]
        return "\n".join(lines) + "\n"
    if meta is None:
        lines += [f"**The scan did not finish ({scan}).** No data was committed. The log shows where it stopped."]
        return "\n".join(lines) + "\n"
    t = meta["totals"]
    rows = [("Companies fetched", f"{t['companies_fetched_ok']} of {t['companies_live']} live"),
            ("Jobs fetched", t["fetched"]),
            ("New listings", t["listings_new"]),
            ("Database total", t["database_total"]),
            ("Open", t["database_open"]),
            ("Open at or above min score", t["open_at_or_above_min_score"]),
            ("Open with unknown location", t["location_unknown_open"]),
            ("Open, remote tied to Iowa", t["remote_iowa_open"])]
    failures = [c for c in meta["companies"] if c["status"] == "error"]
    fallbacks = [c for c in meta["companies"] if c["status"] == "manual_fallback"]
    rows += [("Failures", len(failures)), ("Manual fallbacks", len(fallbacks))]
    lines += ["| Measure | Count |", "|---|---:|"] + [f"| {name} | {value} |" for name, value in rows] + [""]
    if scan != "success":
        lines += ["**Too many companies failed, so this run counts as failed and no data was committed.**", ""]
    else:
        lines += [COMMIT_MEANINGS.get(commit_action, "The commit step did not finish."), ""]
        if email in EMAIL_MEANINGS:
            lines += [EMAIL_MEANINGS[email], ""]
    for title, group in (("Failures", failures), ("Manual fallbacks", fallbacks)):
        if group:
            lines += [f"**{title}**", ""] + [f"- {_clean(c['company'])}: {_clean(c['error'])}" for c in group] + [""]
    return "\n".join(lines) + "\n"


def warnings(meta) -> list:
    return [f"::warning title={_clean(c['company'])}::{c['status']}: {_clean(c['error'])}"
            for c in (meta or {}).get("companies", []) if c["status"] in ("error", "manual_fallback")]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tests", default="")
    parser.add_argument("--scan", default="")
    parser.add_argument("--commit-action", default="")
    parser.add_argument("--email", default="")
    parser.add_argument("--repo", type=Path, default=Path("."))
    args = parser.parse_args(argv)

    # After a crash, meta.json is yesterday's, so its numbers must not be shown as today's.
    meta = None
    if args.scan == "success" or (args.scan == "failure" and _meta_is_fresh(args.repo)):
        path = args.repo / META
        if path.exists():
            meta = json.loads(path.read_text(encoding="utf-8"))
    text = build(meta, args.tests, args.scan, args.commit_action, args.email)
    print(text)
    for line in warnings(meta):
        print(line)
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if target:
        with open(target, "a", encoding="utf-8") as f:
            f.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
