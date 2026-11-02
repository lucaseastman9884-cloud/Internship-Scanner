"""Greenhouse Job Board API. Docs: https://docs.greenhouse.io/job-board.html"""
from __future__ import annotations

from urllib.parse import quote

from ..http_client import HttpError
from ..normalize import new_listing
from ..text import html_to_text
from .base import Adapter


class GreenhouseAdapter(Adapter):
    name = "greenhouse"

    def fetch(self, company, wants_detail=None):
        url = f"https://boards-api.greenhouse.io/v1/boards/{quote(company['board'])}/jobs?content=true"
        data = self.client.get_json(url)
        if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
            raise HttpError(f"unexpected Greenhouse response for {company['board']}")
        return [self._listing(company, job) for job in data["jobs"]]

    def _listing(self, company, job):
        return new_listing(
            company, self.name, job["id"], job["title"],
            (job.get("location") or {}).get("name", ""),
            job.get("absolute_url"),
            date_posted=job.get("first_published"),
            deadline=job.get("application_deadline"),
            description=html_to_text(job.get("content", "")),
        )
