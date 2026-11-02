"""Lever Postings API. Docs: https://github.com/lever/postings-api"""
from __future__ import annotations

import datetime as dt
from urllib.parse import quote

from ..http_client import HttpError
from ..normalize import new_listing
from ..text import html_to_text
from .base import Adapter


def _epoch_ms_to_date(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    return dt.datetime.fromtimestamp(value / 1000, dt.timezone.utc).date().isoformat()


class LeverAdapter(Adapter):
    name = "lever"

    def fetch(self, company, wants_detail=None):
        url = f"https://api.lever.co/v0/postings/{quote(company['board'])}?mode=json"
        data = self.client.get_json(url)
        if not isinstance(data, list):
            raise HttpError(f"unexpected Lever response for {company['board']}")
        return [self._listing(company, job) for job in data]

    def _listing(self, company, job):
        categories = job.get("categories") or {}
        places = categories.get("allLocations") or [categories.get("location", "")]
        lists = " ".join(f"{x.get('text', '')}. {html_to_text(x.get('content', ''))}" for x in job.get("lists") or [])
        description = " ".join(filter(None, [job.get("descriptionPlain", ""), lists, job.get("additionalPlain", "")]))
        return new_listing(
            company, self.name, job["id"], job["text"],
            "; ".join(p for p in places if p),
            job.get("hostedUrl") or job.get("applyUrl"),
            date_posted=_epoch_ms_to_date(job.get("createdAt")),
            description=description,
            is_remote=job.get("workplaceType") == "remote",
        )
