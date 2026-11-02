"""The one interface every source implements.

An adapter returns normalized listings (built with normalize.new_listing) or raises. It never
filters, scores, or catches its own fatal errors: the runner isolates failures per company.
"""
from __future__ import annotations

from typing import Callable, Optional


class Adapter:
    name = ""

    def __init__(self, client):
        self.client = client
        self.warnings: list = []  # problems that did not stop this company's fetch

    def fetch(self, company: dict, wants_detail: Optional[Callable] = None) -> list:
        """Return every job on the company's board.

        wants_detail(listing) lets a source that needs one request per description ask only
        for relevant jobs, which keeps request counts low on large boards.
        """
        raise NotImplementedError
