"""Command line entry point: python -m scanner run"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import ConfigError
from .pipeline import run, too_many_failures
from .store import StoreError

ROOT = Path(__file__).resolve().parent.parent


def _print_summary(meta: dict) -> None:
    print(f"{'Company':38} {'ATS':16} {'Status':18} {'Fetched':>7} {'Kept':>5} {'Excl':>5}")
    print("-" * 94)
    order = {"ok": 0, "error": 1, "manual_fallback": 2, "skipped": 3, "manual": 4}
    for row in sorted(meta["companies"], key=lambda r: (order.get(r["status"], 9), r["company"])):
        print(f"{row['company'][:38]:38} {row['ats']:16} {row['status']:18} {row['fetched']:>7} {row['kept']:>5} {row['excluded']:>5}")
    t = meta["totals"]
    print("-" * 94)
    print(f"Totals: fetched {t['fetched']}, kept {t['kept']}, excluded {t['excluded']}")
    print(f"Stored listings: {t['listings_before']} before, {t['listings_new']} new, "
          f"{t['listings_updated']} updated, {t['listings_after']} after")
    print(f"Status changes: {t['status_changes']}")
    print(f"Database: {t['database_total']} total, {t['database_open']} open, "
          f"{t['open_at_or_above_min_score']} open at or above email.min_score")
    print(f"Location unknown (open): {t['location_unknown_open']}. Remote, tied to Iowa (open): {t['remote_iowa_open']}")
    print(f"Source health: {meta['source_health']}")
    print(f"Requests per host: {meta['requests_by_host']}")
    for problem in meta["errors"]:
        print(f"Problem: {problem['company']}: {problem['error']}")


def _email(args) -> int:
    # Imported here so `python -m scanner run` doesn't depend on the email code.
    from . import email_report
    if args.failure:
        outcomes = dict(item.split("=", 1) for item in args.outcome if "=" in item)
        return email_report.run_failure_email(args.run_url, outcomes,
                                              out_dir=args.out_dir if args.dry_run else None)
    try:
        return email_report.run_email(args.config_dir, args.data_dir, args.out_dir, args.dry_run)
    except (ConfigError, StoreError) as err:
        print(f"::error title=Email not built::{err}", file=sys.stderr)
        return 2


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m scanner", description="Internship Scanner pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    run_cmd = sub.add_parser("run", help="fetch, filter, score, and store listings")
    run_cmd.add_argument("--config-dir", type=Path, default=ROOT / "config")
    run_cmd.add_argument("--data-dir", type=Path, default=ROOT / "data")

    email_cmd = sub.add_parser("email", help="build and send the morning email (or a failure email)")
    email_cmd.add_argument("--dry-run", action="store_true",
                           help="write outputs/email_preview.html instead of sending; needs no secrets")
    email_cmd.add_argument("--failure", action="store_true", help="send the short 'Scan failed' email instead")
    email_cmd.add_argument("--run-url", default=None, help="with --failure: the link to the failed run")
    email_cmd.add_argument("--outcome", action="append", default=[], metavar="STEP=RESULT",
                           help="with --failure: a step's result, e.g. scan=failure (repeatable)")
    email_cmd.add_argument("--config-dir", type=Path, default=ROOT / "config")
    email_cmd.add_argument("--data-dir", type=Path, default=ROOT / "data")
    email_cmd.add_argument("--out-dir", type=Path, default=ROOT / "outputs")
    args = parser.parse_args(argv)

    if args.command == "email":
        return _email(args)

    try:
        meta = run(args.config_dir, args.data_dir)
    except (ConfigError, StoreError) as err:
        print(f"Stopped before fetching anything.\n{err}", file=sys.stderr)
        return 2
    _print_summary(meta)
    # A single company's failure is only a warning. This many means the automation should go red.
    if too_many_failures(meta):
        t = meta["totals"]
        print(f"Too many sources failed: {t['companies_failed']} of {t['companies_live']} live companies.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
