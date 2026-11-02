"""The one interface every source implements.

An adapter returns normalized listings (built with normalize.new_listing) or raises. It never
filters, scores, or catches its own fatal errors: the runner isolates failures per company.
"""
from __future__ import annotations

from typing import Callable, Optional


class Adapter:
    name = ""

    def __init__(self, client, cfg: Optional[dict] = None):
        self.client = client
        self.cfg = cfg
        self.warnings: list = []  # problems that did not stop this company's fetch
        # False when part of the board went unseen, so absence from this fetch proves nothing.
        self.complete = True

    def fetch(self, company: dict, wants_detail: Optional[Callable] = None) -> list:
        """Return the company's jobs: the whole board, or for Workday, its search results.

        wants_detail(listing) lets a source that needs one request per description ask only
        for relevant jobs, which keeps request counts low on large boards.
        """
        raise NotImplementedError

    def still_open(self, company: dict, record: dict) -> Optional[bool]:
        """D-025: ask the source about one stored listing that this run's results did not include.

        True means open, False means gone. None means this source has no such check, so the
        run's own results decide. Raising means the check failed, which proves nothing.
        """
        return None
