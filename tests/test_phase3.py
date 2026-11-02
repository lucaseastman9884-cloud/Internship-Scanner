"""Workday fallback, status history, recurring, geocoding, D-015 to D-021."""
import ast
import datetime as dt
import json
import shutil

import pytest
import yaml

from conftest import ROOT, FakeClient, load_fixture
from scanner import filtering, history, scoring, store
from scanner.adapters import ADAPTERS
from scanner.config import ConfigError, load_config
from scanner.geocode import Geocoder, cache_key
from scanner.http_client import FormatChanged, HttpClient, HttpError, RobotsBlocked, RobotsUnreadable
from scanner.location import LocationResolver
from scanner.normalize import new_listing
from scanner.pipeline import run

DAY = [dt.datetime(2026, 11, d, 11, 30, tzinfo=dt.timezone.utc) for d in range(2, 12)]
GOOD = {"name": "Good Co", "ats": "greenhouse", "board": "good", "cities": [], "priority": 1, "notes": "x"}
WORK = {"name": "Wintrust Financial", "ats": "workday", "board": "https://wintrust.wd1.myworkdayjobs.com/Search",
        "cities": [], "priority": 1, "notes": "x"}


def gh_job(job_id=1, title="Tax Intern", location="Des Moines, Iowa"):
    return {"id": job_id, "title": title, "absolute_url": f"https://example.org/{job_id}", "location": {"name": location},
            "first_published": None, "application_deadline": None, "content": "Prepare returns."}


@pytest.fixture
def space(tmp_path):
    config = tmp_path / "config"
    config.mkdir()
    for name in ("config.yaml", "cities.yaml"):
        shutil.copy(ROOT / "config" / name, config / name)
    (config / "companies.yaml").write_text(yaml.safe_dump({"companies": [GOOD, WORK]}), encoding="utf-8")
    return tmp_path


def board_route(**kwargs):
    return {"boards/good/": {"jobs": kwargs.get("jobs", [gh_job()])},
            "myworkdayjobs.com": kwargs.get("workday", {"total": 0, "jobPostings": []})}


def go(space, day, **kwargs):
    return run(space / "config", space / "data", client=FakeClient(board_route(**kwargs)), now=DAY[day])


def stored(space):
    return json.loads((space / "data" / "internships.json").read_text(encoding="utf-8"))


def one(space, title="Tax Intern"):
    return next(x for x in stored(space) if x["title"] == title)


def company_row(meta, name):
    return next(r for r in meta["companies"] if r["company"] == name)


# --- Status transitions ---

def test_open_to_possibly_closed_to_closed_after_n_and_m_misses(space):
    go(space, 0)
    expected = ["open", "possibly_closed", "possibly_closed", "possibly_closed", "closed"]
    for day, status in enumerate(expected, start=1):
        go(space, day, jobs=[])
        assert one(space)["status"] == status, day
    assert one(space)["missed_runs"] == 5


def test_closed_listing_stays_in_the_file_and_remembers_when_it_was_open(space):
    go(space, 0)
    for day in range(1, 6):
        go(space, day, jobs=[])
    assert one(space)["last_known_open"] == "2026-11-02"


def test_failed_fetch_is_never_a_miss(space):
    go(space, 0)
    before = one(space)
    for day in range(1, 8):
        run(space / "config", space / "data",
            client=FakeClient({"boards/good/": HttpError("HTTP 503", 503), "myworkdayjobs.com": {"total": 0, "jobPostings": []}}),
            now=DAY[day])
    after = one(space)
    assert after["status"] == "open" and after["missed_runs"] == 0 and after == before


def test_a_failure_between_misses_neither_counts_nor_resets(space):
    go(space, 0)
    go(space, 1, jobs=[])
    run(space / "config", space / "data",
        client=FakeClient({"boards/good/": OSError("reset"), "myworkdayjobs.com": {"total": 0, "jobPostings": []}}), now=DAY[2])
    assert one(space)["missed_runs"] == 1
    go(space, 3, jobs=[])
    assert one(space)["missed_runs"] == 2 and one(space)["status"] == "possibly_closed"


def test_filtered_is_not_closed(space):
    go(space, 0)
    path = space / "config" / "config.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace(
        'exclude_keywords: ["senior"', 'exclude_keywords: ["tax", "senior"'), encoding="utf-8")
    for day in range(1, 8):
        go(space, day)
    record = one(space)
    assert record["status"] == "filtered" and record["missed_runs"] == 0
    assert "tax" in record["filtered_reason"]
    assert json.loads((space / "data" / "last_seen.json").read_text())[record["id"]] == "2026-11-09"


def test_filtered_listing_returns_to_open_when_config_changes_back(space):
    go(space, 0)
    path = space / "config" / "config.yaml"
    original = path.read_text(encoding="utf-8")
    path.write_text(original.replace('exclude_keywords: ["senior"', 'exclude_keywords: ["tax", "senior"'), encoding="utf-8")
    go(space, 1)
    path.write_text(original, encoding="utf-8")
    go(space, 2)
    record = one(space)
    assert record["status"] == "open" and record["filtered_reason"] is None


def test_filtered_listing_gone_from_the_board_still_closes(space):
    go(space, 0)
    path = space / "config" / "config.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace('exclude_keywords: ["senior"', 'exclude_keywords: ["tax", "senior"'), encoding="utf-8")
    go(space, 1)
    for day in range(2, 7):
        go(space, day, jobs=[])
    assert one(space)["status"] == "closed"


def test_reappearing_listing_reopens_and_keeps_first_seen(space):
    go(space, 0)
    for day in range(1, 6):
        go(space, day, jobs=[])
    go(space, 6)
    record = one(space)
    assert record["status"] == "open" and record["missed_runs"] == 0 and record["first_seen"] == "2026-11-02"


def test_partial_fetch_cannot_prove_absence():
    records = [{"id": "a", "company_id": "c", "title": "Tax Intern", "city": "Chicago", "status": "open", "missed_runs": 0,
                "last_seen": "2026-11-01", "sources": [{"source_name": "workday", "source_job_id": "t:1"}]}]
    cfg = {"status": {"possibly_closed_after_missed_runs": 1, "closed_after_missed_runs": 2}}
    history.update_statuses(records, {"c": {"kept": [], "excluded": [], "complete": False}}, "2026-11-02", cfg)
    assert records[0]["status"] == "open" and records[0]["missed_runs"] == 0


def test_rerun_with_no_changes_is_stable_across_days(space):
    go(space, 0)
    first = (space / "data" / "internships.json").read_bytes()
    go(space, 1)
    assert (space / "data" / "internships.json").read_bytes() == first


def test_old_files_with_last_seen_inside_listings_are_migrated(space):
    go(space, 0)
    records = stored(space)
    for r in records:
        r["last_seen"] = "2026-10-01"
        r.pop("filtered_reason")
    (space / "data" / "internships.json").write_text(json.dumps(records), encoding="utf-8")
    (space / "data" / "last_seen.json").unlink()
    loaded = store.load_listings(space / "data")
    assert loaded[0]["last_seen"] == "2026-10-01" and loaded[0]["filtered_reason"] is None


# --- Workday in the pipeline: fallback ---

@pytest.mark.parametrize("failure", [
    RobotsBlocked("robots.txt does not allow this request"), HttpError("HTTP 403", 403),
    HttpError("HTTP 429 after 1 retry", 429), FormatChanged("not valid JSON"),
])
def test_blocked_or_changed_workday_falls_back_to_manual(space, failure):
    meta = go(space, 0, workday=failure)
    row = company_row(meta, "Wintrust Financial")
    assert row["status"] == "manual_fallback" and row["fallback_link"] == WORK["board"]
    assert any(e["company"] == WORK["name"] for e in meta["errors"])
    assert {"company": WORK["name"], "url": WORK["board"], "reason": "manual_fallback", "detail": row["error"]} in meta["check_manually"]
    status = json.loads((space / "data" / "companies_status.json").read_text())["wintrust-financial"]
    assert status["fetch_health"]["status"] == "manual_fallback"
    assert status["careers_url"] == WORK["board"]
    assert company_row(meta, "Good Co")["status"] == "ok"  # the other company still ran


def test_a_server_error_is_an_ordinary_error_not_a_fallback(space):
    meta = go(space, 0, workday=HttpError("HTTP 503 after 1 retry", 503))
    assert company_row(meta, "Wintrust Financial")["status"] == "error"


def test_an_unreadable_robots_file_is_an_outage_not_a_block(space):
    meta = go(space, 0, workday=RobotsUnreadable("could not read robots.txt"))
    assert company_row(meta, "Wintrust Financial")["status"] == "error"


def test_workday_listings_reach_the_data_file(space):
    def route(url, payload):
        if payload is not None:
            return load_fixture("workday_search.json")
        return load_fixture("workday_details.json").get(url.rsplit("_", 1)[-1], HttpError("HTTP 404", 404))
    meta = go(space, 0, workday=route)
    titles = {x["title"] for x in stored(space)}
    assert "Wintrust 2027 Summer Internship: Commercial Banking" in titles
    assert "2027 Tax Winter Internship - Missouri" not in titles  # Winter 2027, and every city is over 60 miles (D-016)
    assert "Wintrust 2027 Summer Internship: Commercial Banking (Texas)" not in titles
    assert company_row(meta, "Wintrust Financial")["status"] == "ok"


def test_no_detail_request_for_titles_or_places_that_cannot_qualify(space):
    fake = FakeClient({"boards/good/": {"jobs": []}, "myworkdayjobs.com": lambda url, payload: (
        load_fixture("workday_search.json") if payload is not None
        else load_fixture("workday_details.json").get(url.rsplit("_", 1)[-1], HttpError("HTTP 404", 404)))})
    run(space / "config", space / "data", client=fake, now=DAY[0])
    details = [u for u in fake.requested if "/job/" in u]
    assert len(details) == 3
    assert not any(word in u for u in details for word in ("Frisco", "International-Tax", "Program-Manager"))


def test_post_sends_json_identifies_itself_and_never_sends_cookies():
    calls = []

    def transport(url, headers, timeout, body=None):
        calls.append((url, headers, timeout, body))
        return (404, b"") if url.endswith("/robots.txt") else (200, b"{}")
    client = HttpClient(transport=transport, sleep=lambda s: None, clock=lambda: 0.0)
    client.post_json("https://a.test/jobs", {"limit": 20})
    url, headers, timeout, body = calls[-1]
    assert json.loads(body) == {"limit": 20} and headers["Content-Type"] == "application/json"
    assert "Internship-Scanner" in headers["User-Agent"] and timeout > 0
    assert not any(k.lower() == "cookie" for k in headers)
    assert client.request_counts["a.test"] == 2


def test_robots_are_requested_with_an_accept_header_servers_will_honor():
    """Workday answered 406 to a JSON Accept, which RFC 9309 would read as "no rules"."""
    seen = {}

    def transport(url, headers, timeout, body=None):
        seen[url] = headers["Accept"]
        return (404, b"") if url.endswith("/robots.txt") else (200, b"{}")
    HttpClient(transport=transport, sleep=lambda s: None, clock=lambda: 0.0).get_json("https://a.test/x")
    assert "text/plain" in seen["https://a.test/robots.txt"]


# --- Recurring ---

def rec(title, season, status="open", last_known=None, company="c"):
    return {"id": title, "company_id": company, "title": title, "season": season, "status": status, "last_known_open": last_known}


def test_same_program_across_seasons_is_recurring():
    records = [rec("Tax Intern - Summer 2027", "Summer 2027", "closed", "2026-08-01"), rec("2028 Summer Tax Internship", "Summer 2028")]
    history.update_recurring(records)
    assert all(r["recurring"] for r in records)
    assert records[1]["last_known_open"] == "2026-08-01"
    assert records[0]["last_known_open"] == "2026-08-01"


def test_one_season_or_other_company_or_other_program_is_not_recurring():
    records = [rec("Tax Intern - Summer 2027", "Summer 2027"), rec("Audit Intern - Summer 2028", "Summer 2028"),
               rec("Tax Intern - Summer 2028", "Summer 2028", company="other"), rec("Risk Intern", None)]
    history.update_recurring(records)
    assert not any(r["recurring"] for r in records)
    assert all(r["last_known_open"] is None for r in records)


def test_two_open_seasons_are_recurring_with_no_past_date():
    records = [rec("Tax Intern - Summer 2027", "Summer 2027"), rec("Tax Intern - Summer 2028", "Summer 2028")]
    history.update_recurring(records)
    assert all(r["recurring"] and r["last_known_open"] is None for r in records)


# --- Geocoding ---

SETTINGS = {"enabled": True, "min_seconds_between_requests": 15, "max_lookups_per_run": 2}
NOMINATIM = "nominatim.openstreetmap.org"


def test_geocode_cache_hit_makes_no_request():
    fake = FakeClient({})
    geocoder = Geocoder(fake, {cache_key("Lombard", "IL"): {"lat": 41.88, "lng": -88.01}}, SETTINGS)
    assert geocoder.lookup("Lombard", "IL") == {"lat": 41.88, "lng": -88.01}
    assert fake.requested == [] and geocoder.stats["cache_hits"] == 1


def test_geocode_miss_asks_once_then_uses_the_cache():
    fake = FakeClient({NOMINATIM: [{"lat": "41.88", "lon": "-88.01"}]})
    cache = {}
    geocoder = Geocoder(fake, cache, SETTINGS)
    assert geocoder.lookup("Lombard", "IL") == {"lat": 41.88, "lng": -88.01}
    geocoder.lookup("lombard", "il")
    assert len(fake.requested) == 1 and "city=Lombard" in fake.requested[0] and "state=Illinois" in fake.requested[0]
    assert cache[cache_key("Lombard", "IL")] == {"lat": 41.88, "lng": -88.01}


def test_not_found_is_cached_but_a_failure_is_not():
    fake = FakeClient({"city=Nowhere": [], "city=Flaky": HttpError("HTTP 503", 503)})
    cache = {}
    geocoder = Geocoder(fake, cache, {**SETTINGS, "max_lookups_per_run": 5})
    assert geocoder.lookup("Nowhere", "IA") is None and cache[cache_key("Nowhere", "IA")] is None
    assert geocoder.lookup("Flaky", "IA") is None and cache_key("Flaky", "IA") not in cache
    assert geocoder.available is True


def test_switched_off_means_no_request_but_the_cache_still_answers():
    fake = FakeClient({})
    geocoder = Geocoder(fake, {cache_key("Lombard", "IL"): {"lat": 1.0, "lng": 2.0}}, {**SETTINGS, "enabled": False})
    assert geocoder.lookup("Lombard", "IL") == {"lat": 1.0, "lng": 2.0}
    assert geocoder.lookup("Peoria", "IL") is None and fake.requested == []


def test_robots_block_stops_all_further_lookups():
    fake = FakeClient({NOMINATIM: RobotsBlocked("disallowed")})
    geocoder = Geocoder(fake, {}, {**SETTINGS, "max_lookups_per_run": 5})
    geocoder.lookup("Lombard", "IL")
    geocoder.lookup("Peoria", "IL")
    assert len(fake.requested) == 1 and geocoder.available is False and geocoder.stats["blocked"] is True


def test_lookup_budget_is_respected():
    fake = FakeClient({NOMINATIM: []})
    geocoder = Geocoder(fake, {}, SETTINGS)
    for city in ("A", "B", "C", "D"):
        geocoder.lookup(city, "IL")
    assert len(fake.requested) == 2


def test_real_nominatim_rules_block_the_request_in_the_shared_client():
    """The robots.txt served on 2026-11-02."""
    rules = b"User-agent: ia_archiver\nAllow: /\n\nUser-agent: *\nDisallow: /search.php\nDisallow: /search\n"
    sent = []

    def transport(url, headers, timeout):
        sent.append(url)
        return (200, rules) if url.endswith("/robots.txt") else (200, b"[]")
    client = HttpClient(transport=transport, sleep=lambda s: None, clock=lambda: 0.0)
    geocoder = Geocoder(client, {}, SETTINGS)
    assert geocoder.lookup("Lombard", "IL") is None and geocoder.stats["blocked"] is True
    assert sent == [f"https://{NOMINATIM}/robots.txt"]


def test_shipped_config_keeps_geocoding_off_and_within_the_policy(cfg):
    assert cfg["geocoding"]["enabled"] is False
    assert cfg["geocoding"]["min_seconds_between_requests"] >= 15  # 4 per minute


def test_geocoded_city_gets_coordinates_and_its_real_distance(cfg, cities):
    geocoder = Geocoder(FakeClient({}), {cache_key("Lombard", "IL"): {"lat": 41.88, "lng": -88.01}}, SETTINGS)
    place = LocationResolver(cfg, cities, geocoder).resolve("Lombard, IL")
    assert place["tier"] == "target_area" and place["lat"] == 41.88 and place["detail"] == "Chicago metro"


def test_a_lookup_that_fails_keeps_the_listing_as_location_unknown(cfg, cities):
    geocoder = Geocoder(FakeClient({NOMINATIM: []}), {}, SETTINGS)
    place = LocationResolver(cfg, cities, geocoder).resolve("Faraway, TX")
    assert place["tier"] == "unknown" and place["lat"] is None


@pytest.mark.parametrize("raw, tier", [("Lombard, IL", "unknown"), ("Peculiar, MO", "unknown"), ("Olathe, KS", "target_area"),
                                       ("Dallas, TX", None), ("Greenwood, SC", None), ("Toronto, Canada", None), ("3 Locations", "unknown")])
def test_with_geocoding_off_only_nearby_states_stay_as_unknown(cfg, cities, raw, tier):
    geocoder = Geocoder(FakeClient({}), {}, {**SETTINGS, "enabled": False})
    assert LocationResolver(cfg, cities, geocoder).resolve(raw)["tier"] == tier


def test_location_unknown_listing_is_stored_with_null_coordinates(space):
    go(space, 0, jobs=[gh_job(location="Lombard, IL")])
    record = one(space)
    assert record["lat"] is None and record["lng"] is None and record["location_label"] == "Location unknown"
    assert record["status"] == "open"


def test_only_possible_internships_may_use_the_geocoder(space):
    path = space / "config" / "config.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace("enabled: false", "enabled: true"), encoding="utf-8")
    fake = FakeClient({"boards/good/": {"jobs": [gh_job(1, "Staff Accountant", "Peoria, IL"), gh_job(2, "Tax Intern", "Lombard, IL")]},
                       "myworkdayjobs.com": {"total": 0, "jobPostings": []}, NOMINATIM: []})
    run(space / "config", space / "data", client=fake, now=DAY[0])
    lookups = [u for u in fake.requested if NOMINATIM in u]
    assert len(lookups) == 1 and "Lombard" in lookups[0]


@pytest.mark.parametrize("raw", ["Montreal", "Europe", "Southfield", "Dublin Ireland Office"])
def test_with_geocoding_off_a_bare_unlisted_name_is_not_kept(cfg, cities, raw):
    geocoder = Geocoder(FakeClient({}), {}, {**SETTINGS, "enabled": False})
    assert LocationResolver(cfg, cities, geocoder).resolve(raw)["tier"] is None


@pytest.mark.parametrize("raw, city, state", [  # every shape below is real, seen on a live board
    ("IL - Chicago", "Chicago", "IL"),
    ("IL - Downers Grove", "Downers Grove", "IL"),
    ("OH - Columbus (43213)", "Columbus", "OH"),
    ("Chicago, IL – U.S.", "Chicago", "IL"),
    ("Chicago, IL, USA", "Chicago", "IL"),
    ("Pella, Iowa, USA - Corporate Office", "Pella", "IA"),
    ("Saint Paul, MN Campus", "Saint Paul", "MN"),
    ("Chicago Office", "Chicago", "IL"),
    ("Des Moines #3, Park Avenue, Des Moines, IA", "Des Moines", "IA"),
    ("Altoona,  8th St SW, Altoona, IA", "Altoona", "IA"),
    ("Kansas City MO", "Kansas City", "MO"),
    ("Ogden UT", "Ogden", "UT"),
    ("Chicago - 155 Wacker", "Chicago", "IL"),
    ("US-IL-Chicago-10 SWacker-3100", "Chicago", "IL"),
    ("USA NM Albuquerque", "Albuquerque", "NM"),
    ("Tampa Florida United States", "Tampa", "FL"),
    ("New York New York United States", "New York", "NY"),
    ("MO - Kansas City Downtown/Plaza - Kansas City - KC Downtown Bank Building (1000 Walnut) (64106)", "Kansas City", "MO"),
    ("MO - Southeast - Cape Girardeau - Cape Girardeau Main (63703)", "Cape Girardeau", "MO"),
    ("Iowa City, IA", "Iowa City", "IA"),
    ("Iowa City", "Iowa City", "IA"),
    ("Kansas City", "Kansas City", "MO"),
])
def test_real_workday_location_shapes(resolver, raw, city, state):
    place = resolver.resolve(raw)
    assert (place["city"], place["state"]) == (city, state)


def test_a_comma_list_of_two_cities_is_not_a_city_and_state(resolver):
    place = resolver.resolve("Chicago, New York City")
    assert place["city"] == "Chicago" and place["tier"] == "target_area"


# --- D-015, D-019 ---

def test_smartrecruiters_is_not_an_active_adapter():
    assert "smartrecruiters" not in ADAPTERS and "workday" in ADAPTERS


def test_registry_d015_d019():
    registry = yaml.safe_load((ROOT / "config" / "companies.yaml").read_text(encoding="utf-8"))["companies"]
    by_name = {c["name"]: c for c in registry}
    assert "BGM Group" not in by_name
    assert by_name["RR Donnelley"]["ats"] == "manual" and by_name["Northwestern Medicine"]["ats"] == "manual"
    assert not [c for c in registry if c["ats"] == "smartrecruiters"]


# --- D-016 ---

def season_listing(season):
    listing = new_listing({"company_id": "c", "name": "C"}, "greenhouse", "1", "Tax Intern", "x", "https://e.test")
    listing["season"] = season
    return listing


@pytest.mark.parametrize("season, raw, kept", [
    ("Spring 2027", "Des Moines, IA", True),     # about 31 miles from Ames
    ("Winter 2027", "Pella, IA", True),          # about 50 miles
    ("Spring 2027", "Iowa City, IA", False),     # about 100 miles
    ("Spring 2027", "Chicago, IL", False),
    ("Winter 2027", "Kansas City, MO", False),
    ("Spring 2027", "Chicago, IL; Ames, IA", True),   # closest city counts
    ("Spring 2028", "Chicago, IL", True),        # this season has no limit
    ("Summer 2027", "Kansas City, MO", True),
])
def test_season_location_limit(cfg, resolver, season, raw, kept):
    problem = filtering.season_limit_problem(season_listing(season), resolver.resolve(raw), cfg)
    assert (problem is None) is kept


def test_limited_season_with_unknown_distance_is_not_kept(cfg, resolver):
    problem = filtering.season_limit_problem(season_listing("Spring 2027"), resolver.resolve("Lombard, IL"), cfg)
    assert "unknown" in problem


def test_season_limit_is_applied_by_the_pipeline(space):
    go(space, 0, jobs=[gh_job(1, "Spring 2027 Tax Intern", "Chicago, IL"), gh_job(2, "Spring 2027 Audit Intern", "Ames, IA")])
    assert {x["title"] for x in stored(space)} == {"Spring 2027 Audit Intern"}
    excluded = json.loads((space / "data" / "excluded_last_run.json").read_text())
    assert excluded[0]["primary_reason"] == "season_distance"


# --- D-017 ---

@pytest.mark.parametrize("title", ["2027 Summer Claims Adjuster Internship", "Claims Intern", "Underwriting Intern"])
def test_claims_and_underwriting_are_insurance_roles(cfg, title):
    from scanner.normalize import role_match
    assert role_match(title, cfg)["category"] == "insurance_risk"


# --- D-018 ---

WILLIAM_BLAIR_REAL = [
    "Working in Technology (WiT) Application Development - Summer 2027",
    "Working in Technology (WiT) Data Science - Summer 2027",
    "Working in Technology (WiT) Platform Engineering - Summer 2027",
    "Working in Technology (WiT) Software Engineering - Summer 2027",
]


@pytest.mark.parametrize("title", WILLIAM_BLAIR_REAL)
def test_william_blair_real_titles_have_no_d018_word_and_stay_out(cfg, title):
    """Recorded on purpose: they have a season and year, but not analyst, program, or scholar. See STATUS."""
    assert filtering.is_internship(title, cfg) is False


def test_william_blair_titles_would_count_if_their_program_name_is_added_to_config(cfg):
    wider = {**cfg, "program_title_terms": cfg["program_title_terms"] + ["working in technology"]}
    assert all(filtering.is_internship(t, wider) for t in WILLIAM_BLAIR_REAL)


@pytest.mark.parametrize("title, expected", [
    ("Investment Banking Analyst Program - Summer 2027", True),
    ("2028 Summer Analyst", True),
    ("Summer 2028 Associate Program", True),
    ("Summer 2027 Scholar", True),
    ("2027 Summer Leadership Program", True),
    ("Fall 2027 Credit Analyst", True),
    ("Research Analyst - U.S. Growth & Core Equity (Generalist)", False),  # real, no season
    ("Analyst, PWM Private Capital", False),                               # real, no season
    ("Leadership Program", False),
    ("2027 Investment Banking Full-Time MBA Associate", False),            # real, no term
    ("Summer 2027 Software Engineer", False),
])
def test_d018_season_plus_program_word(cfg, title, expected):
    assert filtering.is_internship(title, cfg) is expected


# --- D-020, D-021 ---

def scored(cfg, resolver, title="Tax Intern", location="Des Moines, IA", season="Summer 2027", status="eligible"):
    listing = new_listing({"company_id": "c", "name": "C"}, "greenhouse", "1", title, location, "https://e.test")
    listing["season"] = season
    listing["eligibility"] = {"status": status, "reason": "test"}
    return scoring.score(listing, resolver.resolve(location), cfg)


def test_scoring_file_holds_no_numbers_except_zero():
    tree = ast.parse((ROOT / "scanner" / "scoring.py").read_text(encoding="utf-8"))
    numbers = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)]
    assert set(numbers) <= {0}


@pytest.mark.parametrize("key, value, title, season, status, expected", [
    ("role_in_title", 1, "Tax Intern", "Summer 2027", "eligible", 1 + 20 + 25 + 10),
    ("target_area", 2, "Tax Intern", "Summer 2027", "eligible", 40 + 2 + 25 + 10),
    ("season_max", 10, "Tax Intern", "Summer 2027", "eligible", 40 + 20 + 10 + 10),
    ("season_not_stated", 3, "Tax Intern", None, "eligible", 40 + 20 + 3 + 10),
    ("eligible", 0, "Tax Intern", "Summer 2027", "eligible", 40 + 20 + 25),
    ("eligibility_unclear", 7, "Tax Intern", "Summer 2027", "unclear", 40 + 20 + 25 + 7),
    ("ineligible", -5, "Tax Intern", "Summer 2027", "ineligible", 40 + 20 + 25 - 5),
    ("max_score", 50, "Tax Intern", "Summer 2027", "eligible", 50),
    ("no_role_signal", -1, "IT Intern", None, "eligible", 35),
])
def test_every_scoring_value_comes_from_config(cfg, resolver, key, value, title, season, status, expected):
    changed = {**cfg, "scoring": {**cfg["scoring"], key: value}}
    assert scored(changed, resolver, title=title, season=season, status=status)[0] == expected


def test_no_role_listing_is_capped_and_says_so(cfg, resolver):
    uncapped = {**cfg, "scoring": {**cfg["scoring"], "no_role_cap": 100, "no_role_signal": 40}}
    capped = {**uncapped, "scoring": {**uncapped["scoring"], "no_role_cap": 35}}
    high, _ = scored(uncapped, resolver, title="Sales Intern")
    low, why = scored(capped, resolver, title="Sales Intern")
    assert high > 35 and low == 35
    assert any("capped at 35" in r for r in why)


def test_default_cap_stays_below_the_email_threshold(cfg):
    assert cfg["scoring"]["no_role_cap"] == 35 < cfg["email"]["min_score"]


def test_listing_with_a_role_is_not_capped(cfg, resolver):
    assert scored(cfg, resolver)[0] == 95


def test_claims_adjuster_now_clears_the_email_threshold(cfg, resolver):
    value, _ = scored(cfg, resolver, title="2027 Summer Claims Adjuster Internship", location="Dubuque, IA")
    assert value == 95 >= cfg["email"]["min_score"]


@pytest.mark.parametrize("change, expected", [
    (lambda d: d["scoring"].pop("eligible"), "scoring must have exactly"),
    (lambda d: d["scoring"].update(eligible="many"), "scoring.eligible must be a number"),
    (lambda d: d["scoring"].update(no_role_cap=500), "no_role_cap"),
    (lambda d: d["seasons"][0].update(max_miles_from_home=-5), "max_miles_from_home"),
    (lambda d: d["workday"].update(page_size=0), "workday.page_size"),
    (lambda d: d["geocoding"].update(enabled="yes"), "geocoding.enabled"),
])
def test_new_settings_are_validated(tmp_path, cities, change, expected):
    data = yaml.safe_load((ROOT / "config" / "config.yaml").read_text(encoding="utf-8"))
    change(data)
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ConfigError, match=expected):
        load_config(path, cities)


# --- companies_status.json and meta.json ---

def test_status_file_covers_manual_companies_without_claiming_a_check(space):
    path = space / "config" / "companies.yaml"
    manual = {"name": "Manual Co", "ats": "manual", "board": "https://example.com/careers", "cities": [], "priority": 1, "notes": "x"}
    path.write_text(yaml.safe_dump({"companies": [GOOD, WORK, manual]}), encoding="utf-8")
    go(space, 0)
    entry = json.loads((space / "data" / "companies_status.json").read_text())["manual-co"]
    assert entry["fetch_health"]["status"] == "manual" and entry["last_checked"] is None
    assert entry["careers_url"] == "https://example.com/careers"


def test_meta_holds_run_times_and_counts_and_the_data_file_does_not(space):
    meta = go(space, 0)
    assert meta["run_started"] and meta["totals"]["database_total"] == 1
    assert meta["totals"]["database_open"] == 1
    assert meta["totals"]["open_at_or_above_min_score"] == 1
    assert "requests_by_host" in meta and "check_manually" in meta
    assert set(stored(space)[0]) & {"run_started", "run_finished", "last_seen"} == set()
