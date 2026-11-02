import pytest

from conftest import FakeClient, load_fixture
from scanner.adapters import ADAPTERS
from scanner.adapters.ashby import AshbyAdapter
from scanner.adapters.greenhouse import GreenhouseAdapter
from scanner.adapters.lever import LeverAdapter
from scanner.adapters.smartrecruiters import SmartRecruitersAdapter
from scanner.http_client import HttpError

SPEC_FIELDS = {
    "id", "company_id", "title", "company", "ats", "location_raw", "city", "state", "country", "lat", "lng",
    "is_remote", "sources", "apply_url", "date_posted", "deadline", "first_seen", "last_seen", "status",
    "season", "role_category", "eligibility", "relevance_score", "match_reasons", "description_snippet",
    "recurring", "last_known_open",
}


def company(board="acme", ats="greenhouse"):
    return {"company_id": "acme", "name": "Acme", "board": board, "ats": ats}


def test_no_workday_adapter_yet():
    assert set(ADAPTERS) == {"greenhouse", "lever", "ashby", "smartrecruiters"}


def test_greenhouse_maps_the_real_response_shape():
    client = FakeClient({"boards-api.greenhouse.io/v1/boards/acme/jobs?content=true": load_fixture("greenhouse_board.json")})
    jobs = GreenhouseAdapter(client).fetch(company())
    assert len(jobs) == 5
    job = jobs[0]
    assert SPEC_FIELDS <= set(job)
    assert job["title"] == "Accounting Intern"
    assert job["location_raw"] == "Des Moines, Iowa, United States"
    assert job["date_posted"] == "2026-09-03"
    assert "month-end close" in job["description_snippet"]
    assert "<p>" not in job["description_snippet"]
    assert job["sources"][0]["source_job_id"] == "5228997007"


def test_greenhouse_never_invents_dates():
    client = FakeClient({"boards-api": load_fixture("greenhouse_board.json")})
    tax = GreenhouseAdapter(client).fetch(company())[4]
    assert tax["date_posted"] is None
    assert tax["deadline"] == "2027-02-15"  # stated by the source


def test_lever_maps_the_real_response_shape():
    client = FakeClient({"api.lever.co/v0/postings/acme?mode=json": load_fixture("lever_postings.json")})
    job = LeverAdapter(client).fetch(company(ats="lever"))[0]
    assert SPEC_FIELDS <= set(job)
    assert job["title"] == "Wealth Management Intern - Summer 2028"
    assert job["location_raw"] == "Chicago, Illinois; Atlanta, Georgia"
    assert job["date_posted"] == "2026-08-31"
    assert "Coursework in finance" in job["_description"]
    assert job["is_remote"] is False


def test_ashby_maps_the_real_response_and_skips_unlisted_jobs():
    client = FakeClient({"api.ashbyhq.com/posting-api/job-board/acme": load_fixture("ashby_board.json")})
    jobs = AshbyAdapter(client).fetch(company(ats="ashby"))
    assert [j["title"] for j in jobs] == ["Corporate Finance Intern"]
    assert SPEC_FIELDS <= set(jobs[0])
    assert jobs[0]["location_raw"] == "Kansas City, Missouri; Remote - European Union"
    assert jobs[0]["date_posted"] == "2026-10-04"


def sr_client():
    return FakeClient({
        "postings/744000158084730": load_fixture("smartrecruiters_detail.json"),
        "postings?limit=100&offset=0": load_fixture("smartrecruiters_list.json"),
    })


def test_smartrecruiters_requests_detail_only_for_wanted_jobs():
    client = sr_client()
    jobs = SmartRecruitersAdapter(client).fetch(company("RRDonnelley", "smartrecruiters"), lambda x: "Intern" in x["title"])
    assert len(jobs) == 2
    assert sum("postings/" in url for url in client.requested) == 1
    tax = jobs[0]
    assert SPEC_FIELDS <= set(tax)
    assert tax["location_raw"] == "Chicago, IL, United States"
    assert tax["apply_url"].endswith("744000158084730-tax-intern")
    assert "corporate tax team" in tax["_description"]


def test_smartrecruiters_follows_pages():
    first = {"totalFound": 2, "content": [load_fixture("smartrecruiters_list.json")["content"][0]]}
    second = {"totalFound": 2, "content": [load_fixture("smartrecruiters_list.json")["content"][1]]}
    client = FakeClient({"offset=0": first, "offset=1": second})
    jobs = SmartRecruitersAdapter(client).fetch(company("RRDonnelley", "smartrecruiters"), lambda x: False)
    assert len(jobs) == 2


def test_smartrecruiters_missing_detail_warns_and_keeps_the_listing():
    client = FakeClient({
        "postings/744000158084730": HttpError("HTTP 404", 404),
        "postings/744000159154090": HttpError("HTTP 404", 404),
        "postings?limit=100&offset=0": load_fixture("smartrecruiters_list.json"),
    })
    adapter = SmartRecruitersAdapter(client)
    jobs = adapter.fetch(company("RRDonnelley", "smartrecruiters"))
    assert len(jobs) == 2 and len(adapter.warnings) == 2


@pytest.mark.parametrize("adapter_class, response", [
    (GreenhouseAdapter, {"unexpected": True}),
    (LeverAdapter, {"unexpected": True}),
    (AshbyAdapter, []),
    (SmartRecruitersAdapter, {"unexpected": True}),
])
def test_unexpected_response_raises(adapter_class, response):
    client = FakeClient({"https://": response})
    with pytest.raises(HttpError, match="unexpected"):
        adapter_class(client).fetch(company())
