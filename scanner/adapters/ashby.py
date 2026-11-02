"""Ashby job posting API. Docs: https://developers.ashbyhq.com/docs/public-job-posting-api"""
from __future__ import annotations

from urllib.parse import quote

from ..http_client import HttpError
from ..normalize import new_listing
from .base import Adapter


class AshbyAdapter(Adapter):
    name = "ashby"

    def fetch(self, company, wants_detail=None):
        url = f"https://api.ashbyhq.com/posting-api/job-board/{quote(company['board'])}"
        data = self.client.get_json(url)
        if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
            raise HttpError(f"unexpected Ashby response for {company['board']}")
        return [self._listing(company, job) for job in data["jobs"] if job.get("isListed", True)]

    def _listing(self, company, job):
        places = [job.get("location", "")] + [x.get("location", "") for x in job.get("secondaryLocations") or []]
        return new_listing(
            company, self.name, job["id"], job["title"],
            "; ".join(p for p in places if p),
            job.get("jobUrl") or job.get("applyUrl"),
            date_posted=job.get("publishedAt"),
            description=job.get("descriptionPlain", ""),
            is_remote=bool(job.get("isRemote")),
        )
