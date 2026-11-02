"""SmartRecruiters Posting API. Docs: https://developers.smartrecruiters.com/docs/posting-api

The host's robots.txt currently disallows crawlers other than LinkedInBot, so the shared HTTP
client stops live calls before they are sent (see D-015). This adapter is tested offline.
"""
from __future__ import annotations

from urllib.parse import quote

from ..http_client import HttpError
from ..normalize import new_listing
from ..text import html_to_text
from .base import Adapter

PAGE_SIZE = 100
BASE = "https://api.smartrecruiters.com/v1/companies"


class SmartRecruitersAdapter(Adapter):
    name = "smartrecruiters"

    def fetch(self, company, wants_detail=None):
        slug = quote(company["board"])
        listings, offset = [], 0
        while True:
            data = self.client.get_json(f"{BASE}/{slug}/postings?limit={PAGE_SIZE}&offset={offset}")
            if not isinstance(data, dict) or not isinstance(data.get("content"), list):
                raise HttpError(f"unexpected SmartRecruiters response for {company['board']}")
            for job in data["content"]:
                listing = self._listing(company, job, "")
                # The list has no description or apply link, and a request per job on a board
                # of 1,400 postings would be impolite, so fetch details only for relevant jobs.
                if wants_detail is None or wants_detail(listing):
                    listing = self._with_detail(company, slug, job, listing)
                listings.append(listing)
            offset += len(data["content"])
            if not data["content"] or offset >= data.get("totalFound", 0):
                return listings

    def _with_detail(self, company, slug, job, listing):
        try:
            detail = self.client.get_json(f"{BASE}/{slug}/postings/{quote(str(job['id']))}")
        except HttpError as err:
            self.warnings.append(f"no description for posting {job['id']}: {err}")
            return listing
        sections = ((detail.get("jobAd") or {}).get("sections") or {}).values()
        description = " ".join(html_to_text(s.get("text", "")) for s in sections if isinstance(s, dict))
        return self._listing(company, job, description, detail.get("postingUrl") or detail.get("applyUrl"))

    def _listing(self, company, job, description, url=None):
        location = job.get("location") or {}
        place = location.get("fullLocation") or ", ".join(
            x for x in (location.get("city"), location.get("region"), location.get("country")) if x
        )
        return new_listing(
            company, self.name, job["id"], job["name"], place,
            url or f"https://jobs.smartrecruiters.com/{company['board']}/{job['id']}",
            date_posted=job.get("releasedDate"),
            description=description,
            is_remote=bool(location.get("remote")),
        )
