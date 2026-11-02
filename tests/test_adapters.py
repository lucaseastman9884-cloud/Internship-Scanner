import pytest

from conftest import FakeClient, load_fixture
from scanner.adapters import ADAPTERS
from scanner.adapters.ashby import AshbyAdapter
from scanner.adapters.greenhouse import GreenhouseAdapter
from scanner.adapters.lever import LeverAdapter
from scanner.adapters.smartrecruiters import SmartRecruitersAdapter
from scanner.adapters.workday import WorkdayAdapter, _job_id
from scanner.http_client import FormatChanged, HttpError

SPEC_FIELDS = {
    "id", "company_id", "title", "company", "ats", "location_raw", "city", "state", "country", "lat", "lng",
    "is_remote", "sources", "apply_url", "date_posted", "deadline", "first_seen", "last_seen", "status",
    "season", "role_category", "eligibility", "relevance_score", "match_reasons", "description_snippet",
    "recurring", "last_known_open",
}


def company(board="acme", ats="greenhouse"):
    return {"company_id": "acme", "name": "Acme", "board": board, "ats": ats}


def test_active_adapters():
    assert set(ADAPTERS) == {"greenhouse", "lever", "ashby", "workday"}


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


# --- Workday ---

WD_COMPANY = {"company_id": "wintrust-financial", "name": "Wintrust Financial", "ats": "workday",
              "board": "https://wintrust.wd1.myworkdayjobs.com/Search"}
WD_SETTINGS = {"workday": {"search_terms": ["intern"], "page_size": 20, "max_results_per_term": 200}}


def wd_client(search=None, details=None):
    search = search or load_fixture("workday_search.json")
    details = details if details is not None else load_fixture("workday_details.json")

    def route(url, payload):
        if payload is not None:
            return search
        req = url.rsplit("_", 1)[-1]
        return details.get(req, HttpError("HTTP 404", 404))
    return FakeClient({"myworkdayjobs.com": route})


def wants_interns(listing):
    return "Internship" in listing["title"] and "TX" not in listing["location_raw"]


def test_workday_posts_the_search_and_fetches_detail_only_for_wanted_jobs():
    fake = wd_client()
    listings = WorkdayAdapter(fake, WD_SETTINGS).fetch(WD_COMPANY, wants_interns)
    assert fake.posted[0] == {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": "intern"}
    assert len(listings) == 6
    gets = [u for u in fake.requested if not u.endswith("/jobs")]
    assert len(gets) == 3
    assert all(u.startswith("https://wintrust.wd1.myworkdayjobs.com/wday/cxs/wintrust/Search/job/") for u in gets)


def test_workday_detail_supplies_description_date_and_every_location():
    listings = WorkdayAdapter(wd_client(), WD_SETTINGS).fetch(WD_COMPANY, wants_interns)
    tax = next(x for x in listings if "Tax Winter" in x["title"])
    assert tax["location_raw"] == "St. Louis - Maplewood, MO; Kansas City, MO; Columbia, MO"
    bank = next(x for x in listings if x["title"].endswith("Commercial Banking"))
    assert bank["date_posted"] == "2026-10-08"
    assert "credit analysis" in bank["_description"]
    assert bank["apply_url"].startswith("https://wintrust.wd1.myworkdayjobs.com/Search/job/")
    assert bank["sources"][0]["source_job_id"] == "wintrust:261936"


def test_workday_relative_posted_text_is_never_stored_as_a_date():
    listings = WorkdayAdapter(wd_client(), WD_SETTINGS).fetch(WD_COMPANY, lambda listing: False)
    assert all(x["date_posted"] is None for x in listings)
    assert "Days Ago" not in str(listings)


def test_workday_job_ids_do_not_collide_across_tenants():
    assert _job_id("wintrust", "/job/x/Tax_1") != _job_id("umb", "/job/x/Tax_1")


def test_workday_repeat_results_across_search_terms_become_one_listing():
    settings = {"workday": {**WD_SETTINGS["workday"], "search_terms": ["intern", "summer analyst"]}}
    fake = wd_client()
    listings = WorkdayAdapter(fake, settings).fetch(WD_COMPANY, lambda listing: False)
    assert len(fake.posted) == 2 and len(listings) == 6


def test_workday_pages_using_the_first_total_because_later_pages_report_zero():
    jobs = [{"title": f"Intern {i}", "externalPath": f"/job/x/Intern_{i}", "locationsText": "Chicago, IL"} for i in range(5)]

    def route(url, payload):
        start = payload["offset"]
        return {"total": 5 if start == 0 else 0, "jobPostings": jobs[start:start + 2]}
    settings = {"workday": {"search_terms": ["intern"], "page_size": 2, "max_results_per_term": 200}}
    fake = FakeClient({"myworkdayjobs.com": route})
    adapter = WorkdayAdapter(fake, settings)
    assert len(adapter.fetch(WD_COMPANY, lambda listing: False)) == 5
    assert [p["offset"] for p in fake.posted] == [0, 2, 4]
    assert adapter.complete is True


def test_workday_cap_stops_paging_and_marks_the_fetch_incomplete():
    jobs = [{"title": f"Intern {i}", "externalPath": f"/job/x/Intern_{i}", "locationsText": "Chicago, IL"} for i in range(10)]

    def route(url, payload):
        return {"total": 10, "jobPostings": jobs[payload["offset"]:payload["offset"] + 2]}
    settings = {"workday": {"search_terms": ["intern"], "page_size": 2, "max_results_per_term": 4}}
    fake = FakeClient({"myworkdayjobs.com": route})
    adapter = WorkdayAdapter(fake, settings)
    assert len(adapter.fetch(WD_COMPANY, lambda listing: False)) == 4
    assert len(fake.posted) == 2
    assert adapter.complete is False and "stopped at 4 of 10" in adapter.warnings[0]


@pytest.mark.parametrize("reply", [{"unexpected": True}, ["list"], {"jobPostings": [{"title": "No path"}]}])
def test_workday_changed_format_raises(reply):
    with pytest.raises(FormatChanged):
        WorkdayAdapter(FakeClient({"myworkdayjobs.com": reply}), WD_SETTINGS).fetch(WD_COMPANY)


def test_workday_changed_detail_format_raises():
    fake = wd_client(details={"261936": {"nope": 1}, "261941-1": {"nope": 1}, "JR102224": {"nope": 1}})
    with pytest.raises(FormatChanged):
        WorkdayAdapter(fake, WD_SETTINGS).fetch(WD_COMPANY, wants_interns)


def test_workday_posting_removed_during_the_run_is_dropped_with_a_warning():
    adapter = WorkdayAdapter(wd_client(details={}), WD_SETTINGS)
    only_one = lambda listing: "Finance" in listing["title"]
    listings = adapter.fetch(WD_COMPANY, only_one)
    assert len(listings) == 5 and "disappeared" in adapter.warnings[0]


def test_workday_foreign_country_is_added_to_a_bare_city():
    detail = load_fixture("workday_details.json")["261936"]
    detail["jobPostingInfo"].update(location="London", country={"descriptor": "United Kingdom"})
    adapter = WorkdayAdapter(FakeClient({}), WD_SETTINGS)
    assert adapter._locations(detail["jobPostingInfo"], {}) == "London, United Kingdom"
