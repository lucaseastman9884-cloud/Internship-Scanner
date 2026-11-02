"""Workday public career-site JSON, used politely under D-002 and D-010.

The endpoint is undocumented, so anything unexpected raises FormatChanged and the runner moves the
company to "check manually". It searches instead of paging whole boards, which keeps requests low.
"""
from __future__ import annotations

from urllib.parse import urlparse

from ..http_client import FormatChanged, HttpError
from ..normalize import new_listing
from ..text import html_to_text
from .base import Adapter

GONE_STATUS = {404, 410}
US_NAMES = {"united states of america", "united states"}


def _board_parts(board: str) -> tuple:
    parsed = urlparse(board)
    return parsed.netloc, parsed.netloc.split(".")[0], parsed.path.strip("/")


def _job_id(tenant: str, external_path: str) -> str:
    """The requisition ID ends the path. Tenants reuse numbering, so the tenant is part of the ID."""
    last = external_path.rstrip("/").rsplit("/", 1)[-1]
    return f"{tenant}:{last.rsplit('_', 1)[-1]}"


class WorkdayAdapter(Adapter):
    name = "workday"

    def fetch(self, company, wants_detail=None):
        host, tenant, site = _board_parts(company["board"])
        api = f"https://{host}/wday/cxs/{tenant}/{site}"
        settings = self.cfg["workday"]

        postings = {}  # keyed by path, because several search terms return the same job
        for term in settings["search_terms"]:
            for job in self._search(api, term, settings, company):
                postings.setdefault(job["externalPath"], job)

        listings = []
        for path in sorted(postings):
            job = postings[path]
            listing = self._listing(company, tenant, job, job.get("locationsText") or "")
            if wants_detail is None or wants_detail(listing):
                listing = self._with_detail(company, tenant, api, job, listing)
            if listing is not None:
                listings.append(listing)
        return listings

    def _search(self, api, term, settings, company):
        size, cap = settings["page_size"], settings["max_results_per_term"]
        jobs, offset, total = [], 0, None
        while True:
            data = self.client.post_json(f"{api}/jobs", {"appliedFacets": {}, "limit": size, "offset": offset, "searchText": term})
            if not isinstance(data, dict) or not isinstance(data.get("jobPostings"), list):
                raise FormatChanged(f"unexpected Workday response for {company['board']}")
            page = data["jobPostings"]
            usable = [j for j in page if isinstance(j, dict) and j.get("title") and j.get("externalPath")]
            if page and not usable:
                raise FormatChanged(f"Workday postings without title or path for {company['board']}")
            if len(usable) < len(page):
                # Live boards return the occasional blank entry. It proves nothing about the format,
                # but it is a job we could not see, so this fetch cannot prove anything is gone.
                self.complete = False
                self.warnings.append(f"search '{term}' returned {len(page) - len(usable)} posting(s) without a title or path")
            jobs.extend(usable)
            # Later pages can report a total of 0, so trust the first page's number.
            total = data.get("total") if total is None else total
            offset += len(page)
            if not page or len(page) < size or (isinstance(total, int) and offset >= total):
                return jobs
            if offset >= cap:
                # Jobs past the cap are unseen, not gone, so this run cannot count anything as missing.
                self.complete = False
                self.warnings.append(f"search '{term}' stopped at {offset} of {total} results (config cap)")
                return jobs

    def _with_detail(self, company, tenant, api, job, listing):
        try:
            detail = self.client.get_json(f"{api}{job['externalPath']}")
        except HttpError as err:
            if err.status in GONE_STATUS:  # removed between the search and this request
                self.warnings.append(f"posting {job['externalPath']} disappeared during the run")
                return None
            raise
        info = detail.get("jobPostingInfo") if isinstance(detail, dict) else None
        if not isinstance(info, dict):
            raise FormatChanged(f"unexpected Workday detail response for {company['board']}")
        return self._listing(company, tenant, job, self._locations(info, job), info)

    def _locations(self, info, job):
        names = [info.get("location")] + list(info.get("additionalLocations") or [])
        names = [n for n in names if isinstance(n, str) and n.strip()]
        country = (info.get("country") or {}).get("descriptor") or ""
        if country and country.lower() not in US_NAMES:
            names = [f"{n}, {country}" for n in names]  # a bare "London" must not look local
        return "; ".join(names) or job.get("locationsText") or ""

    def _listing(self, company, tenant, job, location, info=None):
        info = info or {}
        path = job["externalPath"]
        return new_listing(
            company, self.name, _job_id(tenant, path), job["title"], location,
            info.get("externalUrl") or f"{company['board']}{path}",
            # startDate is the date stated by the source. postedOn ("Posted 3 Days Ago") is relative,
            # and storing it would change the data file every day.
            date_posted=info.get("startDate"),
            description=html_to_text(info.get("jobDescription") or ""),
        )
