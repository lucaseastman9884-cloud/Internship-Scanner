#!/usr/bin/env python3
"""Save a scan's results to git. GitHub Actions runs this after `python -m scanner run`.

- internships.json changed: commit everything in data/ (D-023).
- It did not change, but the last commit is a week old: commit data/meta.json alone. GitHub turns
  off scheduled workflows in public repos after 60 days with no activity. See docs/AUTOMATION.md.
- Otherwise: commit nothing.

Only files under data/ can ever be committed. This uses only git and the standard library, so it
can be tested offline against a temporary repository.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import subprocess
import sys
import time
from pathlib import Path

BOT_NAME = "github-actions[bot]"
BOT_EMAIL = "41898282+github-actions[bot]@users.noreply.github.com"
IDENTITY = ("-c", f"user.name={BOT_NAME}", "-c", f"user.email={BOT_EMAIL}")
LISTINGS = "data/internships.json"
KEEPALIVE_FILE = "data/meta.json"
KEEPALIVE_DAYS = 7
DAY_SECONDS = 86400


class CommitError(Exception):
    pass


def decide(listings_changed: bool, seconds_since_last_commit: float, keepalive_days: int = KEEPALIVE_DAYS) -> str:
    """Return "data", "keepalive", or "none"."""
    if listings_changed:
        return "data"
    return "keepalive" if seconds_since_last_commit >= keepalive_days * DAY_SECONDS else "none"


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    if done.returncode != 0:
        raise CommitError(f"git {' '.join(args)} failed: {done.stderr.strip()}")
    return done.stdout.strip()


def _push(repo: Path, branch: str, wait_seconds: float) -> None:
    """Someone may have pushed during a long scan, so catch up first. One retry covers a close race."""
    for attempt in (1, 2):
        try:
            # --autostash because a keepalive leaves the other data files changed but uncommitted.
            # A fresh runner has no git identity, and a rebase and a stash both write commits.
            _git(repo, *IDENTITY, "pull", "--rebase", "--autostash", "origin", branch)
            _git(repo, "push", "origin", f"HEAD:{branch}")
            return
        except CommitError:
            if attempt == 2:
                raise
            time.sleep(wait_seconds)


def commit_and_push(repo: Path, now: float, push: bool = True, keepalive_days: int = KEEPALIVE_DAYS, wait_seconds: float = 5) -> str:
    changed = bool(_git(repo, "status", "--porcelain", "--", LISTINGS))
    action = decide(changed, now - int(_git(repo, "log", "-1", "--format=%ct")), keepalive_days)
    if action == "none":
        return action

    _git(repo, "add", "--", "data/" if action == "data" else KEEPALIVE_FILE)
    staged = _git(repo, "diff", "--cached", "--name-only").splitlines()
    outside = [name for name in staged if not name.startswith("data/")]
    if outside:
        raise CommitError(f"refusing to commit files outside data/: {outside}")
    if not staged:
        return "none"  # a keepalive with an unchanged meta.json has nothing to say

    day = dt.datetime.fromtimestamp(now, dt.timezone.utc).date().isoformat()
    message = f"Update listings ({day})" if action == "data" else f"Weekly keepalive ({day})"
    _git(repo, *IDENTITY, "commit", "-m", message)
    if push:
        _push(repo, _git(repo, "rev-parse", "--abbrev-ref", "HEAD"), wait_seconds)
    return action


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--no-push", action="store_true")
    parser.add_argument("--keepalive-days", type=int, default=KEEPALIVE_DAYS)
    parser.add_argument("--now", type=float, default=None, help="for tests: the current time in Unix seconds")
    args = parser.parse_args(argv)
    try:
        action = commit_and_push(args.repo, args.now if args.now is not None else time.time(), not args.no_push, args.keepalive_days)
    except CommitError as err:
        print(f"::error::{err}")
        return 1
    print(f"Commit result: {action}")
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as f:
            f.write(f"action={action}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
