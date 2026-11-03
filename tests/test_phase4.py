"""Phase 4: Gazetteer coordinates, unknown-location rules, the empty-response guard, D-025 to D-029,
and the automation scripts. Git runs against temporary local repositories, never the network."""
import datetime as dt
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from scanner import filtering, history, normalize
from scanner.__main__ import main
from scanner.adapters.workday import WorkdayAdapter
from scanner.config import ConfigError, load_cities, load_companies
from scanner.gazetteer import DEFAULT_PATH, Gazetteer, default
from scanner.http_client import HttpError
from scanner.location import LocationResolver, _miles, remote_tag
from scanner.pipeline import run, too_many_failures
from tests.conftest import FakeClient

ROOT = Path(__file__).resolve().parent.parent
DAY = [dt.datetime(2026, 11, d, 11, 30, tzinfo=dt.timezone.utc) for d in range(2, 12)]
WORK = {"name": "Wintrust Financial", "ats": "workday", "board": "https://w.wd1.myworkdayjobs.com/Site", "cities": [], "priority": 1, "notes": "x"}
GOOD = {"name": "Good Co", "ats": "greenhouse", "board": "good", "cities": [], "priority": 1, "notes": "x"}


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


commit_data = load_script("commit_data")
run_summary = load_script("run_summary")


# --- D-022: Gazetteer lookup ---

@pytest.mark.parametrize("city, state, lat, lng", [
    ("Cape Girardeau", "MO", 37.309389, -89.558359),
    ("Springfield", "IL", 39.791063, -89.644572),
    ("Bloomington", "IL", 40.475777, -88.969912),
    ("West Des Moines", "IA", 41.549937, -93.781351),
])
def test_gazetteer_finds_the_exact_census_coordinates(city, state, lat, lng):
    assert default().lookup(city, state) == {"city": city, "state": state, "lat": lat, "lng": lng}


def test_same_city_name_in_two_states_gets_two_places():
    assert default().lookup("Springfield", "IL")["lng"] != default().lookup("Springfield", "MO")["lng"]


@pytest.mark.parametrize("asked, state, same_as", [
    ("Saint Louis", "MO", "St. Louis"), ("ST LOUIS", "MO", "St. Louis"), ("New York City", "NY", "New York"),
    ("Lees Summit", "MO", "Lee's Summit"), ("Mt Prospect", "IL", "Mount Prospect"),
])
def test_gazetteer_accepts_common_spellings(asked, state, same_as):
    found = default().lookup(asked, state)
    assert found and found["lat"] == default().lookup(same_as, state)["lat"]


def test_kansas_city_keeps_the_word_city():
    assert default().lookup("Kansas City", "MO") and default().lookup("Kansas City", "KS")


@pytest.mark.parametrize("city", ["Nashville", "Louisville", "Honolulu", "Indianapolis"])
def test_gazetteer_handles_consolidated_city_names(city):
    state = {"Nashville": "TN", "Louisville": "KY", "Honolulu": "HI", "Indianapolis": "IN"}[city]
    assert default().lookup(city, state)


def test_gazetteer_unknown_place_is_none():
    assert default().lookup("Tinytown", "IA") is None


def test_an_incorporated_place_beats_a_cdp_with_the_same_name(tmp_path):
    path = tmp_path / "g.txt"
    head = "USPS|NAME|FUNCSTAT|ALAND|INTPTLAT|INTPTLONG\n"
    path.write_text(head + "IA|Twin CDP|S|999|1.0|2.0\nIA|Twin city|A|5|3.0|4.0\n", encoding="utf-8")
    assert Gazetteer(path).lookup("Twin", "IA")["lat"] == 3.0


def test_a_changed_file_format_stops_with_a_clear_error(tmp_path):
    path = tmp_path / "g.txt"
    path.write_text("A|B\n1|2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing columns"):
        Gazetteer(path)


def test_reference_readme_records_source_year_and_the_files_real_hash():
    readme = (ROOT / "data" / "reference" / "README.md").read_text(encoding="utf-8")
    assert "www2.census.gov/geo/docs/maps-data/data/gazetteer/2026_Gazetteer/2026_Gaz_place_national.zip" in readme
    assert "**Year:** 2026" in readme
    assert hashlib.sha256(DEFAULT_PATH.read_bytes()).hexdigest() in readme


def test_cities_file_holds_no_memory_based_coordinates():
    entries = yaml.safe_load((ROOT / "config" / "cities.yaml").read_text(encoding="utf-8"))["cities"]
    assert entries and all(set(e) == {"city", "state"} for e in entries)


def test_every_listed_city_is_in_the_gazetteer_with_its_coordinates(cities):
    assert all(c == default().lookup(c["city"], c["state"]) for c in cities)


@pytest.mark.parametrize("body, message", [
    ('cities:\n  - { city: "Atlantis", state: "IA" }\n', "not in the Census Gazetteer"),
    ('cities:\n  - { city: "Ames", state: "IA", lat: 1.0, lng: 2.0 }\n', "coordinates come from the Census Gazetteer"),
])
def test_bad_city_entries_are_reported(tmp_path, body, message):
    path = tmp_path / "cities.yaml"
    path.write_text(body, encoding="utf-8")
    with pytest.raises(ConfigError, match=message):
        load_cities(path)


def test_shipped_config_keeps_nominatim_off(cfg):
    assert cfg["geocoding"]["enabled"] is False


# --- D-022: unknown-location rules ---

def listing_for(raw, title="Commercial Banking Intern", is_remote=False):
    return normalize.new_listing({"company_id": "a", "name": "A"}, "greenhouse", "1", title, raw, "https://x.test", is_remote=is_remote)


def codes_for(cfg, resolver, raw, **kwargs):
    listing = listing_for(raw, **kwargs)
    place = normalize.enrich(listing, cfg, resolver)
    listing["eligibility"] = {"status": "eligible", "reason": "test"}
    return [code for code, _ in filtering.evaluate(listing, place, cfg)], listing, place


@pytest.mark.parametrize("raw", [  # the real Commerce Bank strings from Phase 3, then plain forms
    "MO - Southeast - Cape Girardeau - Cape Girardeau Main",
    "MO - Springfield Area - Springfield - Springfield Main",
    "IL - Central Illinois - Bloomington - Bloomington Main",
    "Cape Girardeau, MO", "Springfield, IL", "Bloomington, IL",
])
def test_far_cities_are_now_measured_and_excluded(cfg, resolver, raw):
    codes, listing, place = codes_for(cfg, resolver, raw)
    assert codes == ["location"]
    assert place["lat"] is not None and place["miles_from_home"] > cfg["radius_miles"]


@pytest.mark.parametrize("raw", ["Iowa", "Tinytown, Iowa", "Greater Chicago Area", "Kansas City Area", "Des Moines Metro", "Dubuque County"])
def test_unknown_distance_stays_when_in_iowa_or_naming_a_target_metro(cfg, resolver, raw):
    codes, listing, _ = codes_for(cfg, resolver, raw)
    assert codes == [] and listing["location_label"] == "Location unknown" and listing["lat"] is None


@pytest.mark.parametrize("raw", ["Illinois", "Kansas", "Atlantis, IL", "Hong Kong Hong Kong", "Europe", "4 Locations", ""])
def test_any_other_unknown_distance_is_excluded_with_that_reason(cfg, resolver, raw):
    listing = listing_for(raw)
    place = normalize.enrich(listing, cfg, resolver)
    listing["eligibility"] = {"status": "eligible", "reason": "test"}
    reasons = filtering.evaluate(listing, place, cfg)
    assert reasons[0][0] == "location_unknown" and reasons[0][1].startswith("location unknown")


def test_a_listing_outside_the_us_is_a_location_exclusion(cfg, resolver):
    assert codes_for(cfg, resolver, "Toronto, Canada")[0] == ["location"]


def test_a_placeholder_still_earns_a_look_at_the_detail_page(cfg, resolver):
    assert resolver.resolve("3 Locations")["tier"] is not None


@pytest.mark.parametrize("raw", ["Iowa", "Greater Chicago Area"])
def test_unknown_distance_never_passes_the_season_distance_check(cfg, resolver, raw):
    listing = {"season": "Spring 2027"}
    assert "unknown" in filtering.season_limit_problem(listing, resolver.resolve(raw), cfg)


def test_multi_city_posting_counts_by_its_measured_near_city(cfg, resolver):
    assert codes_for(cfg, resolver, "Cape Girardeau, MO; Ames, IA")[0] == []


def test_real_distance_uses_gazetteer_points(cities):
    by = {c["city"]: c for c in cities}
    assert 25 < _miles(by["Ames"], by["West Des Moines"]) < 35


# --- D-029: remote listings ---

@pytest.mark.parametrize("raw", ["Iowa - Work From Home", "Remote - Iowa", "Remote, IA", "Work From Home - IA", "US-IA-Remote", "Remote in Iowa"])
def test_remote_tied_to_iowa_is_kept_and_tagged(cfg, resolver, raw):
    codes, listing, _ = codes_for(cfg, resolver, raw)
    assert codes == []
    assert listing["is_remote"] is True and listing["tags"] == ["remote_iowa"]
    assert listing["state"] == "IA" and listing["lat"] is None


def test_source_remote_flag_with_an_iowa_city_is_tied_to_iowa(cfg, resolver):
    codes, listing, _ = codes_for(cfg, resolver, "Des Moines, IA", is_remote=True)
    assert codes == [] and listing["tags"] == ["remote_iowa"]


@pytest.mark.parametrize("raw", ["Remote", "Remote in US", "Remote - Illinois", "Remote - European Union", "Work From Home"])
def test_all_other_remote_is_excluded(cfg, resolver, raw):
    codes, listing, _ = codes_for(cfg, resolver, raw)
    assert codes == ["remote"] and listing["tags"] == []


def test_source_remote_flag_with_a_chicago_city_is_excluded(cfg, resolver):
    assert codes_for(cfg, resolver, "Chicago, IL", is_remote=True)[0] == ["remote"]


def test_in_person_listing_has_no_tag(cfg, resolver):
    codes, listing, _ = codes_for(cfg, resolver, "Ames, IA")
    assert codes == [] and listing["tags"] == [] and listing["is_remote"] is False


def test_lowercase_ia_inside_other_words_does_not_tie_a_job_to_iowa(cfg, resolver):
    assert codes_for(cfg, resolver, "Remote - Media and Asia")[0] == ["remote"]


def test_exclude_mode_still_drops_iowa_remote(cfg, resolver):
    assert codes_for({**cfg, "remote": "exclude"}, resolver, "Iowa - Work From Home")[0] == ["remote"]


def test_include_mode_keeps_all_remote(cfg, resolver):
    assert codes_for({**cfg, "remote": "include"}, resolver, "Remote")[0] == []


def test_allowed_states_come_from_config(cfg, cities):
    other = {**cfg, "remote_allowed_states": ["IL"]}
    resolver = LocationResolver(other, cities)
    codes, listing, _ = codes_for(other, resolver, "Remote - Illinois")
    assert codes == [] and listing["tags"] == ["remote_illinois"]
    assert codes_for(other, resolver, "Iowa - Work From Home")[0] == ["remote"]


def test_tag_name():
    assert remote_tag("IA") == "remote_iowa" and remote_tag("NY") == "remote_new_york"


def test_shipped_remote_settings(cfg):
    assert cfg["remote"] == "separate" and cfg["remote_allowed_states"] == ["IA"]


# --- Pipeline helpers ---

@pytest.fixture
def space(tmp_path):
    config = tmp_path / "config"
    config.mkdir()
    for name in ("config.yaml", "cities.yaml"):
        shutil.copy(ROOT / "config" / name, config / name)
    (config / "companies.yaml").write_text(yaml.safe_dump({"companies": [GOOD, WORK]}), encoding="utf-8")
    return tmp_path


def gh_job(job_id, title="Tax Intern", location="Des Moines, IA"):
    return {"id": job_id, "title": title, "absolute_url": f"https://example.org/{job_id}", "location": {"name": location},
            "first_published": None, "application_deadline": None, "content": "Prepare returns."}


def wd_posting(req, title="Tax Intern"):
    return {"title": title, "externalPath": f"/job/Chicago-IL/Tax-Intern_{req}", "locationsText": "Chicago, IL"}


def wd_detail(req, posted=True, can_apply=True, location="Chicago, IL", title="Tax Intern"):
    return {"jobPostingInfo": {"title": title, "location": location, "startDate": "2026-10-01", "jobDescription": "x", "posted": posted,
                               "canApply": can_apply, "country": {"descriptor": "United States of America"},
                               "externalUrl": f"https://w.wd1.myworkdayjobs.com/Site/job/Chicago-IL/Tax-Intern_{req}"}}


def go(space, day, gh=None, wd_jobs=(), detail=None):
    """detail maps a requisition to a reply or an exception. Searches return wd_jobs."""
    wd_jobs = list(wd_jobs)
    detail = detail or {}

    def search(url, payload):
        return {"total": len(wd_jobs) if payload["searchText"] == "intern" else 0,
                "jobPostings": wd_jobs if payload["searchText"] == "intern" else []}

    def one(url, payload):
        req = url.rsplit("_", 1)[-1]
        return detail.get(req, wd_detail(req))
    routes = {"boards/good/": {"jobs": [gh_job(1)] if gh is None else gh}, "/jobs": search, "myworkdayjobs.com": one}
    fake = FakeClient(routes)
    meta = run(space / "config", space / "data", client=fake, now=DAY[day])
    return meta, fake


def stored(space):
    return json.loads((space / "data" / "internships.json").read_text(encoding="utf-8"))


def row(meta, name):
    return next(r for r in meta["companies"] if r["company"] == name)


# --- Empty-response guard ---

def test_empty_response_after_three_open_is_a_failed_fetch(space):
    go(space, 0, gh=[gh_job(i, f"Tax Intern {i}") for i in range(3)])
    before = stored(space)
    meta, _ = go(space, 1, gh=[])
    assert row(meta, "Good Co")["status"] == "error"
    assert "returned 0 jobs" in row(meta, "Good Co")["error"]
    assert meta["totals"]["status_changes"]["missed"] == 0
    assert stored(space) == before
    assert any(e["company"] == "Good Co" for e in meta["errors"])


def test_empty_response_guard_applies_to_workday_too(space):
    reqs = [f"R{i}" for i in range(3)]
    go(space, 0, wd_jobs=[wd_posting(r, f"Tax Intern {r}") for r in reqs],
       detail={r: wd_detail(r, title=f"Tax Intern {r}") for r in reqs})
    meta, fake = go(space, 1, wd_jobs=[], detail={r: HttpError("gone", status=404) for r in reqs})
    assert row(meta, "Wintrust Financial")["status"] == "error"
    assert meta["totals"]["status_changes"]["missed"] == 0
    assert not any("_R" in u for u in fake.requested)  # a failed fetch does not go on to check listings


def test_empty_response_below_three_open_counts_as_missing(space):
    go(space, 0, gh=[gh_job(i, f"Tax Intern {i}") for i in range(2)])
    meta, _ = go(space, 1, gh=[])
    assert row(meta, "Good Co")["status"] == "ok"
    assert meta["totals"]["status_changes"]["missed"] == 2


def test_guard_counts_only_open_listings(space):
    jobs = [gh_job(i, f"Tax Intern {i}") for i in range(3)]
    go(space, 0, gh=jobs)
    go(space, 1, gh=jobs[:1])
    go(space, 2, gh=jobs[:1])  # two now possibly closed, one open
    assert sum(x["status"] == "open" for x in stored(space)) == 1
    meta, _ = go(space, 3, gh=[])
    assert row(meta, "Good Co")["status"] == "ok"


def test_guard_threshold_comes_from_config(space):
    path = space / "config" / "config.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace("empty_response_min_open: 3", "empty_response_min_open: 1"), encoding="utf-8")
    go(space, 0)
    assert row(go(space, 1, gh=[])[0], "Good Co")["status"] == "error"


# --- D-025: result cap, and checking one listing before a miss ---

def test_workday_cap_is_500(cfg):
    assert cfg["workday"]["max_results_per_term"] == 500


def seen_once(space):
    go(space, 0, wd_jobs=[wd_posting("R1")])
    return next(x for x in stored(space) if x["ats"] == "workday")


def wd_record(space):
    return next(x for x in stored(space) if x["ats"] == "workday")


def test_listing_absent_from_search_but_still_open_is_not_a_miss(space):
    seen_once(space)
    meta, fake = go(space, 1, wd_jobs=[wd_posting("OTHER", "Audit Intern")])
    assert any(u.endswith("Tax-Intern_R1") for u in fake.requested)
    assert meta["totals"]["status_changes"]["verified_open"] == 1 and meta["totals"]["status_changes"]["missed"] == 0
    assert wd_record(space)["status"] == "open" and wd_record(space)["missed_runs"] == 0
    last_seen = json.loads((space / "data" / "last_seen.json").read_text())
    assert last_seen[wd_record(space)["id"]] == DAY[1].date().isoformat()


@pytest.mark.parametrize("reply", [HttpError("x", status=403), HttpError("x", status=404), HttpError("x", status=410),
                                   wd_detail("R1", posted=False), wd_detail("R1", can_apply=False)])
def test_listing_the_source_says_is_gone_counts_as_a_miss(space, reply):
    seen_once(space)
    meta, _ = go(space, 1, wd_jobs=[wd_posting("OTHER", "Audit Intern")], detail={"R1": reply})
    assert meta["totals"]["status_changes"]["missed"] == 1 and wd_record(space)["missed_runs"] == 1


@pytest.mark.parametrize("reply", [HttpError("x", status=500), HttpError("x"), {"unexpected": True}])
def test_a_failed_check_is_never_a_miss(space, reply):
    seen_once(space)
    meta, _ = go(space, 1, wd_jobs=[wd_posting("OTHER", "Audit Intern")], detail={"R1": reply})
    changes = meta["totals"]["status_changes"]
    assert changes["missed"] == 0 and changes["check_failed"] == 1 and wd_record(space)["missed_runs"] == 0
    assert row(meta, "Wintrust Financial")["status"] == "ok"
    assert any("could not check" in w for w in row(meta, "Wintrust Financial")["warnings"])


def test_a_capped_search_can_now_close_a_listing_that_is_really_gone(space):
    path = space / "config" / "config.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace("page_size: 20", "page_size: 1").replace(
        "max_results_per_term: 500", "max_results_per_term: 1"), encoding="utf-8")
    seen_once(space)
    jobs = [wd_posting("A", "Audit Intern"), wd_posting("B", "Audit Intern 2")]
    meta, _ = go(space, 1, wd_jobs=jobs, detail={"R1": HttpError("x", status=404)})
    assert meta["totals"]["status_changes"]["missed"] == 1


def test_possibly_closed_listing_found_open_returns_to_open(space):
    seen_once(space)
    other = [wd_posting("OTHER", "Audit Intern")]
    for day in (1, 2):
        go(space, day, wd_jobs=other, detail={"R1": HttpError("x", status=403)})
    assert wd_record(space)["status"] == "possibly_closed"
    go(space, 3, wd_jobs=other)
    assert wd_record(space)["status"] == "open" and wd_record(space)["missed_runs"] == 0


def test_listing_seen_in_the_search_needs_no_extra_check(space):
    seen_once(space)
    meta, fake = go(space, 1, wd_jobs=[wd_posting("R1")])
    assert meta["totals"]["status_changes"]["verified_open"] == 0
    assert sum(u.endswith("Tax-Intern_R1") for u in fake.requested) == 1  # only the normal detail request


def test_whole_board_sources_decide_from_the_board(space):
    go(space, 0, gh=[gh_job(1), gh_job(2, "Audit Intern")])
    meta, fake = go(space, 1, gh=[gh_job(2, "Audit Intern")])
    assert meta["totals"]["status_changes"]["missed"] == 1
    assert sum("/jobs" in u and "boards/good" in u for u in fake.requested) == 1


def test_still_open_without_a_usable_url_defers_to_the_run():
    adapter = WorkdayAdapter(FakeClient({}), {})
    assert adapter.still_open({"board": WORK["board"]}, {"apply_url": "https://elsewhere.test/posting"}) is None


def test_closed_listing_is_not_rechecked_and_does_not_change_the_file(space):
    seen_once(space)
    other = [wd_posting("OTHER", "Audit Intern")]
    for day in range(1, 6):
        go(space, day, wd_jobs=other, detail={"R1": HttpError("x", status=404)})
    assert wd_record(space)["status"] == "closed"
    before = (space / "data" / "internships.json").read_bytes()
    meta, fake = go(space, 6, wd_jobs=other, detail={"R1": HttpError("x", status=404)})
    assert not any(u.endswith("Tax-Intern_R1") for u in fake.requested)
    assert (space / "data" / "internships.json").read_bytes() == before
    assert meta["totals"]["status_changes"]["closed"] == 0


def test_closed_listing_that_returns_reopens(space):
    go(space, 0, gh=[gh_job(1), gh_job(2, "Audit Intern")])
    for day in range(1, 6):
        go(space, day, gh=[gh_job(2, "Audit Intern")])
    assert next(x for x in stored(space) if x["title"] == "Tax Intern")["status"] == "closed"
    go(space, 6, gh=[gh_job(1), gh_job(2, "Audit Intern")])
    record = next(x for x in stored(space) if x["title"] == "Tax Intern")
    assert record["status"] == "open" and record["missed_runs"] == 0


# --- D-023, D-024: accepted behavior still holds ---

def test_unchanged_listings_leave_the_file_byte_identical(space):
    go(space, 0)
    before = (space / "data" / "internships.json").read_bytes()
    go(space, 1)
    assert (space / "data" / "internships.json").read_bytes() == before


def test_location_rule_change_moves_a_stored_listing_to_filtered(space):
    """How the Commerce Bank listings leave the open list: still on the board, now excluded."""
    go(space, 0, gh=[gh_job(1, "Tax Intern", "Ames, IA")])
    meta, _ = go(space, 1, gh=[gh_job(1, "Tax Intern", "Cape Girardeau, MO")])
    record = stored(space)[0]
    assert record["status"] == "filtered" and "Cape Girardeau" in record["filtered_reason"]
    assert meta["totals"]["status_changes"]["filtered"] == 1


# --- D-026, D-027, D-028: registry ---

def test_working_in_technology_titles_stay_excluded(cfg):
    assert not filtering.is_internship("Working in Technology (WiT) - Summer 2027", cfg)


def test_federal_reserve_renamed_with_no_fixed_city():
    companies = {c["name"]: c for c in load_companies(ROOT / "config" / "companies.yaml")}
    assert "Federal Reserve Bank of Kansas City" not in companies
    assert companies["Federal Reserve System"]["cities"] == []
    assert companies["Federal Reserve System"]["company_id"] == "federal-reserve-system"


def test_stored_data_carries_the_new_federal_reserve_id():
    records = json.loads((ROOT / "data" / "internships.json").read_text(encoding="utf-8"))
    status = json.loads((ROOT / "data" / "companies_status.json").read_text(encoding="utf-8"))
    assert not any(r["company_id"] == "federal-reserve-bank-of-kansas-city" for r in records)
    assert "federal-reserve-bank-of-kansas-city" not in status


def test_wells_fargo_is_manual_and_no_board_points_at_its_workday_host():
    companies = load_companies(ROOT / "config" / "companies.yaml")
    assert next(c for c in companies if c["name"] == "Wells Fargo")["ats"] == "manual"
    assert not any("wf.wd" in str(c["board"]) for c in companies)


# --- Failure threshold ---

@pytest.mark.parametrize("failed, live, expected", [(0, 58, False), (1, 58, False), (29, 58, False), (30, 58, True), (1, 2, False), (2, 2, True), (0, 0, False)])
def test_too_many_failures_means_more_than_half(failed, live, expected):
    assert too_many_failures({"totals": {"companies_failed": failed, "companies_live": live}}) is expected


def test_command_exits_1_when_more_than_half_fail(space, capsys):
    code = main(["run", "--config-dir", str(space / "config"), "--data-dir", str(space / "data")])
    assert code == 1  # the network is refused here, so every company fails
    assert "Too many sources failed" in capsys.readouterr().err


def test_exit_0_when_one_of_two_companies_fails(space, monkeypatch, capsys):
    meta = {"companies": [], "errors": [], "source_health": {}, "requests_by_host": {},
            "totals": {"companies_failed": 1, "companies_live": 2, "fetched": 0, "kept": 0, "excluded": 0, "listings_before": 0,
                       "listings_new": 0, "listings_updated": 0, "listings_after": 0, "status_changes": {}, "database_total": 0,
                       "database_open": 0, "open_at_or_above_min_score": 0, "location_unknown_open": 0, "remote_iowa_open": 0}}
    monkeypatch.setattr("scanner.__main__.run", lambda *a: meta)
    assert main(["run", "--config-dir", str(space / "config"), "--data-dir", str(space / "data")]) == 0


# --- Commit-only-on-change script ---

@pytest.mark.parametrize("changed, age_days, expected", [
    (True, 0, "data"), (True, 30, "data"), (False, 0, "none"), (False, 6.9, "none"), (False, 7, "keepalive"), (False, 60, "keepalive"),
])
def test_commit_decision(changed, age_days, expected):
    assert commit_data.decide(changed, age_days * 86400) == expected


def git(repo, *args, env=None):
    full = {**os.environ, "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": "T",
            "GIT_COMMITTER_EMAIL": "t@example.invalid", **(env or {})}
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True, env=full).stdout.strip()


NOW = 1800000000


@pytest.fixture
def repo(tmp_path, monkeypatch):
    # Like a fresh GitHub runner: no git identity at all, unless the script supplies one.
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    origin = tmp_path / "origin.git"
    origin.mkdir()
    git(origin, "init", "--bare", "-b", "main")
    work = tmp_path / "work"
    git(tmp_path, "clone", str(origin), str(work))
    git(work, "checkout", "-B", "main")
    git(work, "config", "user.useConfigOnly", "true")
    (work / "data").mkdir()
    (work / ".gitignore").write_text("data/excluded_last_run.json\n.venv/\n__pycache__/\n", encoding="utf-8")
    for name in ("internships.json", "meta.json", "last_seen.json"):
        (work / "data" / name).write_text("[]\n", encoding="utf-8")
    (work / "README.md").write_text("hi\n", encoding="utf-8")
    git(work, "add", ".")
    stamp = f"{NOW - 3600} +0000"
    git(work, "commit", "-m", "start", env={"GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp})
    git(work, "push", "-u", "origin", "main")
    return work


def commits(repo):
    return int(git(repo, "rev-list", "--count", "HEAD"))


def scan_output(repo, listings=False):
    """What a scan leaves behind, including files that must never be committed."""
    if listings:
        (repo / "data" / "internships.json").write_text('[{"id": 1}]\n', encoding="utf-8")
    (repo / "data" / "meta.json").write_text('{"run": "new"}\n', encoding="utf-8")
    (repo / "data" / "last_seen.json").write_text('{"1": "today"}\n', encoding="utf-8")
    (repo / "data" / "excluded_last_run.json").write_text("big\n", encoding="utf-8")
    (repo / ".venv").mkdir()
    (repo / ".venv" / "x").write_text("x", encoding="utf-8")
    (repo / "__pycache__").mkdir()
    (repo / "__pycache__" / "x.pyc").write_text("x", encoding="utf-8")
    (repo / "README.md").write_text("edited outside data\n", encoding="utf-8")


def test_no_listing_change_means_no_commit(repo):
    scan_output(repo)
    assert commit_data.commit_and_push(repo, NOW) == "none"
    assert commits(repo) == 1


def test_listing_change_commits_data_only_as_the_bot_and_pushes(repo):
    scan_output(repo, listings=True)
    assert commit_data.commit_and_push(repo, NOW) == "data"
    assert sorted(git(repo, "show", "--name-only", "--format=", "HEAD").splitlines()) == [
        "data/internships.json", "data/last_seen.json", "data/meta.json"]
    assert git(repo, "log", "-1", "--format=%an|%ae|%cn|%ce") == "|".join([commit_data.BOT_NAME, commit_data.BOT_EMAIL] * 2)
    assert git(repo, "rev-parse", "HEAD") == git(repo, "rev-parse", "origin/main")


def test_message_carries_the_utc_date(repo):
    scan_output(repo, listings=True)
    commit_data.commit_and_push(repo, NOW)
    assert git(repo, "log", "-1", "--format=%s") == "Update listings (2027-01-15)"


def test_keepalive_after_a_week_commits_meta_only(repo):
    scan_output(repo)
    assert commit_data.commit_and_push(repo, NOW + 8 * 86400) == "keepalive"
    assert git(repo, "show", "--name-only", "--format=", "HEAD").splitlines() == ["data/meta.json"]
    assert git(repo, "rev-parse", "HEAD") == git(repo, "rev-parse", "origin/main")
    assert git(repo, "log", "-1", "--format=%s").startswith("Weekly keepalive")


def test_no_second_keepalive_within_the_week(repo):
    scan_output(repo)
    commit_data.commit_and_push(repo, NOW + 8 * 86400)
    (repo / "data" / "meta.json").write_text('{"run": "newer"}\n', encoding="utf-8")
    # the keepalive commit carries the real clock, so ask about a moment right after it
    last = int(git(repo, "log", "-1", "--format=%ct"))
    assert commit_data.commit_and_push(repo, last + 86400) == "none"


def test_commit_refuses_files_staged_outside_data(repo):
    scan_output(repo, listings=True)
    git(repo, "add", "README.md")
    with pytest.raises(commit_data.CommitError, match="outside data/"):
        commit_data.commit_and_push(repo, NOW)
    assert commits(repo) == 1


def test_push_catches_up_when_someone_pushed_during_the_scan(repo, tmp_path):
    other = tmp_path / "other"
    git(tmp_path, "clone", str(tmp_path / "origin.git"), str(other))
    (other / "config.yaml").write_text("changed by Lucas\n", encoding="utf-8")
    git(other, "add", ".")
    git(other, "commit", "-m", "edit config")
    git(other, "push", "origin", "main")
    (repo / "data" / "internships.json").write_text('[{"id": 2}]\n', encoding="utf-8")
    assert commit_data.commit_and_push(repo, NOW) == "data"
    assert (repo / "config.yaml").exists()
    assert git(repo, "rev-parse", "HEAD") == git(repo, "rev-parse", "origin/main")


def test_keepalive_push_catches_up_with_other_data_files_uncommitted(repo, tmp_path):
    other = tmp_path / "other"
    git(tmp_path, "clone", str(tmp_path / "origin.git"), str(other))
    (other / "note.txt").write_text("x\n", encoding="utf-8")
    git(other, "add", ".")
    git(other, "commit", "-m", "edit")
    git(other, "push", "origin", "main")
    scan_output(repo)
    assert commit_data.commit_and_push(repo, NOW + 8 * 86400) == "keepalive"
    assert git(repo, "rev-parse", "HEAD") == git(repo, "rev-parse", "origin/main")


def test_failed_push_raises_so_the_job_goes_red(repo):
    git(repo, "remote", "set-url", "origin", str(repo.parent / "missing.git"))
    scan_output(repo, listings=True)
    with pytest.raises(commit_data.CommitError):
        commit_data.commit_and_push(repo, NOW, wait_seconds=0)


def test_script_runs_from_the_command_line_and_reports_the_result(repo, tmp_path):
    scan_output(repo, listings=True)
    output = tmp_path / "gh_output"
    done = subprocess.run([sys.executable, str(ROOT / "scripts" / "commit_data.py"), "--repo", str(repo), "--now", str(NOW)],
                          capture_output=True, text=True, env={**os.environ, "GITHUB_OUTPUT": str(output)})
    assert done.returncode == 0 and "Commit result: data" in done.stdout
    assert output.read_text(encoding="utf-8") == "action=data\n"


# --- Run summary script ---

def fake_meta(**companies):
    rows = [{"company": name, "status": status, "error": f"{name} broke" if status != "ok" else None} for name, status in companies.items()]
    return {"companies": rows, "totals": {
        "companies_fetched_ok": 1, "companies_live": 3, "fetched": 10, "listings_new": 4, "database_total": 20, "database_open": 19,
        "open_at_or_above_min_score": 7, "location_unknown_open": 2, "remote_iowa_open": 5}}


def test_summary_shows_every_requested_number():
    text = run_summary.build(fake_meta(A="ok", B="error", C="manual_fallback"), "success", "success", "data")
    for expected in ("| New listings | 4 |", "| Database total | 20 |", "| Open at or above min score | 7 |", "| Failures | 1 |",
                     "| Manual fallbacks | 1 |", "- B: B broke", "- C: C broke", "listings changed"):
        assert expected in text


@pytest.mark.parametrize("meta, tests, scan, expected", [
    (None, "failure", "skipped", "no data was committed"),
    (None, "success", "failure", "did not finish"),
    (fake_meta(A="error"), "success", "failure", "Too many companies failed"),
])
def test_summary_explains_a_failed_run(meta, tests, scan, expected):
    assert expected in run_summary.build(meta, tests, scan, "")


def test_each_failed_company_gets_a_warning_and_ok_ones_do_not():
    lines = run_summary.warnings(fake_meta(A="ok", B="error", C="manual_fallback"))
    assert lines == ["::warning title=B::error: B broke", "::warning title=C::manual_fallback: C broke"]


def test_a_website_error_cannot_break_out_of_its_warning_line():
    meta = fake_meta(B="error")
    meta["companies"][0]["error"] = "bad\n::error::fake | cell"
    line = run_summary.warnings(meta)[0]
    assert "\n" not in line and "::error::" not in line


def test_summary_does_not_show_old_numbers_after_a_crash(repo, capsys):
    (repo / "data" / "meta.json").write_text(json.dumps(fake_meta(A="ok")), encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "old meta")
    run_summary.main(["--tests", "success", "--scan", "failure", "--repo", str(repo)])
    assert "did not finish" in capsys.readouterr().out


def test_summary_is_written_to_the_run_page(repo, tmp_path, monkeypatch):
    (repo / "data" / "meta.json").write_text(json.dumps(fake_meta(A="ok")), encoding="utf-8")
    target = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(target))
    assert run_summary.main(["--tests", "success", "--scan", "success", "--commit-action", "none", "--repo", str(repo)]) == 0
    assert "| New listings | 4 |" in target.read_text(encoding="utf-8")


# --- Workflow file ---

@pytest.fixture(scope="module")
def workflow():
    return yaml.safe_load((ROOT / ".github" / "workflows" / "scan.yml").read_text(encoding="utf-8"))


def test_workflow_triggers(workflow):
    triggers = workflow[True]  # YAML reads the bare key "on" as true
    assert "workflow_dispatch" in triggers
    entry = triggers["schedule"][0]
    assert entry["timezone"] == "America/Chicago"
    minute, hour = entry["cron"].split()[:2]
    assert hour == "5" and int(minute) not in (0, 30)


def test_workflow_permissions_and_limits(workflow):
    assert workflow["permissions"] == {"contents": "write"}
    assert workflow["concurrency"]["cancel-in-progress"] is False
    job = workflow["jobs"]["scan"]
    assert job["timeout-minutes"] >= 60


def test_workflow_order_and_failure_handling(workflow):
    steps = workflow["jobs"]["scan"]["steps"]
    ids = [s.get("id") for s in steps]
    assert ids.index("tests") < ids.index("scan") < ids.index("commit")
    # Only the summary runs after a failure, so a failed test or scan can never reach the commit.
    assert [s["name"] for s in steps if "if" in s] == ["Write run summary"]
    assert not any("continue-on-error" in s for s in steps)


def test_workflow_uses_python_312_with_pip_cache_and_pinned_actions(workflow):
    steps = workflow["jobs"]["scan"]["steps"]
    python = next(s for s in steps if "setup-python" in s.get("uses", ""))
    assert python["with"]["python-version"] == "3.12" and python["with"]["cache"] == "pip"
    assert all(len(s["uses"].split("@")[1]) == 40 for s in steps if "uses" in s)


def test_workflow_uses_no_secrets():
    text = (ROOT / ".github" / "workflows" / "scan.yml").read_text(encoding="utf-8")
    assert "secrets." not in text


def test_requirements_are_pinned():
    lines = (ROOT / "requirements.txt").read_text(encoding="utf-8").split()
    assert lines and all("==" in line for line in lines)
