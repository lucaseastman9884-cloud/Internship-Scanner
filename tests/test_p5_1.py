"""P5.1: email polish. Offline only: conftest blocks sockets and SMTP is never reached here.

Listings are built with the pipeline's own evaluation, so tags, scores and reasons are real.
"""
import copy
import datetime as dt
import json
import shutil
import zlib

import pytest
import yaml

from conftest import ROOT, FakeClient
from scanner import email_report as er
from scanner import filtering, store
from scanner.config import ConfigError, load_config
from scanner.location import title_names_city, title_place
from scanner.normalize import new_listing, title_year_only
from scanner.pipeline import _evaluate, run

NOW = dt.datetime(2026, 11, 3, 12, 0, tzinfo=dt.timezone.utc)  # 6:00 AM in Ames
TODAY = "2026-11-03"
COMPANY = {"company_id": "acme", "name": "Acme Financial"}


def make(cfg, resolver, title, location, description="", job_id=None, company=COMPANY, first_seen="2026-10-01"):
    """One listing as the pipeline would build it. Returns (listing, exclusion codes)."""
    listing = new_listing(company, "greenhouse", job_id or title, title, location,
                          f"https://boards.greenhouse.io/acme/jobs/{zlib.crc32((job_id or title).encode())}", description=description)
    _place, exclusions = _evaluate(listing, cfg, resolver)
    listing = store.public_fields(listing)
    listing.update(first_seen=first_seen, last_seen=TODAY)
    return listing, [code for code, _ in exclusions]


def kept(cfg, resolver, title, location, **kw):
    listing, codes = make(cfg, resolver, title, location, **kw)
    assert codes == [], (title, codes)
    return listing


def with_cfg(cfg, section=None, **changes):
    out = copy.deepcopy(cfg)
    (out[section] if section else out).update(changes)
    return out


def write_config(tmp_path, change):
    raw = yaml.safe_load((ROOT / "config" / "config.yaml").read_text(encoding="utf-8"))
    change(raw)
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return path


def shown(report):
    s = report["sections"]
    return [x["title"] for key in ("new", "deadlines", "top_open", "remote_iowa") for x in s[key]]


# ------------------------------------------------------------ settings

def test_shipped_p5_1_settings(cfg):
    assert cfg["email"]["max_manual"] == 10
    assert cfg["email"]["exclude_role_categories"] == ["insurance_risk"]
    assert cfg["exclude_keywords_outside_home"] == ["part-time", "term-time"]
    assert cfg["scoring"]["title_penalty_keywords"] == {"technology": -30, "marketing": -30}
    assert cfg["scoring"]["title_penalty_exempt_categories"] == ["investment_banking"]
    assert {"credit risk", "market risk"} <= set(cfg["role_categories"]["banking"])


@pytest.mark.parametrize("change, message", [
    (lambda d: d["email"].update(max_manual=-1), "email.max_manual"),
    (lambda d: d["email"].update(exclude_role_categories=["insurance"]), "email.exclude_role_categories: 'insurance'"),
    (lambda d: d["email"].update(exclude_role_categories="insurance_risk"), "email.exclude_role_categories must be a list"),
    (lambda d: d.update(exclude_keywords_outside_home="part-time"), "exclude_keywords_outside_home must be a list"),
    (lambda d: d.pop("exclude_keywords_outside_home"), "missing setting 'exclude_keywords_outside_home'"),
    (lambda d: d["scoring"].update(title_penalty_keywords={"marketing": "lots"}), "scoring.title_penalty_keywords"),
    (lambda d: d["scoring"].update(title_penalty_exempt_categories=["ib"]), "title_penalty_exempt_categories: 'ib'"),
    (lambda d: d["scoring"].pop("title_penalty_keywords"), "scoring must have exactly"),
])
def test_bad_p5_1_settings_are_reported(tmp_path, cities, change, message):
    with pytest.raises(ConfigError, match=message):
        load_config(write_config(tmp_path, change), cities)


def test_empty_lists_turn_the_rules_off(tmp_path, cities, resolver):
    def off(d):
        d["email"]["exclude_role_categories"] = []
        d["exclude_keywords_outside_home"] = []
        d["scoring"]["title_penalty_keywords"] = {}
    cfg = load_config(write_config(tmp_path, off), cities)
    listing = kept(cfg, resolver, "Part-Time Marketing Actuarial Intern", "Chicago, IL")
    assert not any("off-target" in r for r in listing["match_reasons"])
    assert not er.hidden_by_role(listing, cfg)


# ------------------------------------------------------------ A. manual-links cap

def manual_meta(failed=3, manual=45):
    rows = [{"company": f"Failed {chr(90 - i)}", "url": f"https://f{i}.example/careers", "reason": "error", "detail": "x"}
            for i in range(failed)]
    rows += [{"company": f"Manual {i:02d}", "url": f"https://m{i}.example/careers", "reason": "manual", "detail": None}
             for i in range(manual)]
    return {"totals": {"companies_fetched_ok": 55, "companies_live": 58, "companies_failed": failed},
            "source_health": {"workday": {"ok": 40, "error": failed}, "greenhouse": {"ok": 15}},
            "companies": [{"status": "manual"}] * manual, "check_manually": rows}


def manual_companies(failed=3, manual=45):
    # Priorities 3, 1, 2 repeating, so name order and priority order differ.
    out = [{"name": f"Failed {chr(90 - i)}", "priority": 3 - i % 3} for i in range(failed)]
    return out + [{"name": f"Manual {i:02d}", "priority": [3, 1, 2][i % 3]} for i in range(manual)]


def test_48_manual_companies_show_10_failed_first_then_by_priority(cfg, resolver):
    report = er.build_email([], manual_meta(), cfg, manual_companies(), resolver, NOW)
    s = report["sections"]
    names = [m["company"] for m in s["manual"]]
    assert len(names) == cfg["email"]["max_manual"] == 10
    assert s["manual_more"] == 38
    # Failed today first, alphabetical, whatever their priority.
    assert names[:3] == ["Failed X", "Failed Y", "Failed Z"]
    # Then priority 1 alphabetically: Manual 01, 04, 07, ...
    assert names[3:] == ["Manual 01", "Manual 04", "Manual 07", "Manual 10", "Manual 13", "Manual 16", "Manual 19"]
    for body in (report["html"], report["text"]):
        assert "…and 38 more manual companies." in body
        assert "Check these manually (48)" in body
    assert "Manual 22" not in report["html"]


def test_priority_groups_run_1_then_2_then_3(cfg, resolver):
    cfg = with_cfg(cfg, "email", max_manual=100)
    s = er.build_email([], manual_meta(failed=0, manual=6), cfg, manual_companies(0, 6), resolver, NOW)["sections"]
    assert [m["company"] for m in s["manual"]] == ["Manual 01", "Manual 04", "Manual 02", "Manual 05", "Manual 00", "Manual 03"]
    assert s["manual_more"] == 0
    assert "more manual" not in er.build_email([], manual_meta(0, 6), cfg, manual_companies(0, 6), resolver, NOW)["text"]


def test_max_manual_zero_shows_only_the_count(cfg, resolver):
    report = er.build_email([], manual_meta(1, 1), with_cfg(cfg, "email", max_manual=0), manual_companies(1, 1), resolver, NOW)
    assert report["sections"]["manual"] == []
    assert "…and 2 more manual companies." in report["text"]
    assert "None today." not in report["text"]


def test_one_more_is_singular(cfg, resolver):
    report = er.build_email([], manual_meta(0, 11), cfg, manual_companies(0, 11), resolver, NOW)
    assert "…and 1 more manual company." in report["text"]


# ------------------------------------------------------------ B. insurance-only listings

def test_credit_and_market_risk_are_banking(cfg, resolver):
    for title in ("Credit Risk Intern", "Market Risk Summer Intern"):
        listing = kept(cfg, resolver, title, "Chicago, IL")
        assert listing["role_category"] == "banking", title
        assert not er.hidden_by_role(listing, cfg)


def test_insurance_only_hidden_mixed_shown(cfg, resolver):
    only = kept(cfg, resolver, "Actuarial Intern - Summer 2027", "Des Moines, IA")
    mixed = kept(cfg, resolver, "Underwriting and Commercial Banking Intern - Summer 2027", "Des Moines, IA")
    credit = kept(cfg, resolver, "Credit Risk Intern - Summer 2027", "Des Moines, IA")
    for x in (only, mixed, credit):
        assert x["relevance_score"] >= cfg["email"]["min_score"]
    assert er.hidden_by_role(only, cfg)
    assert not er.hidden_by_role(mixed, cfg)
    report = er.build_email([only, mixed, credit], {"totals": {}}, cfg, [], resolver, NOW)
    titles = shown(report)
    assert only["title"] not in titles and only["title"] not in report["html"]
    assert mixed["title"] in titles and credit["title"] in titles


@pytest.mark.parametrize("title", [
    "Investment Banking and Underwriting Intern", "Corporate Finance Risk Management Intern",
    "Asset Management Actuarial Intern", "Audit Intern - Claims", "Commercial Banking Underwriting Intern",
])
def test_any_non_insurance_match_keeps_a_listing(cfg, resolver, title):
    assert not er.hidden_by_role(kept(cfg, resolver, title, "Chicago, IL"), cfg)


def test_early_career_alone_does_not_rescue_an_insurance_listing(cfg, resolver):
    # early_career is a signal, not a role (role_match keeps it apart), so it doesn't count here.
    assert er.hidden_by_role(kept(cfg, resolver, "Sophomore Actuarial Intern", "Chicago, IL"), cfg)


def test_a_title_with_no_category_is_not_hidden_by_this_rule(cfg, resolver):
    assert not er.hidden_by_role(kept(cfg, resolver, "Summer Intern", "Chicago, IL"), cfg)


def test_health_line_counts_hidden_listings(cfg, resolver):
    rows = [kept(cfg, resolver, f"Actuarial Intern {i} - Summer 2027", "Des Moines, IA") for i in range(3)]
    rows.append(kept(cfg, resolver, "Claims Intern - Summer 2027", "Des Moines, IA", job_id="low"))
    rows[-1]["relevance_score"] = 10  # below min_score, so it wouldn't have shown anyway
    rows.append(dict(rows[0], id="filtered-one", status="filtered"))
    health = er.build_email(rows, {"totals": {"companies_fetched_ok": 1, "companies_live": 1}}, cfg, [], resolver, NOW)["sections"]["health"]
    assert health.endswith(" 3 insurance-only listings hidden.")
    one = er.build_email(rows[:1], {"totals": {}}, cfg, [], resolver, NOW)["sections"]["health"]
    assert one.endswith(" 1 insurance-only listing hidden.")
    off = er.build_email(rows, {"totals": {}}, with_cfg(cfg, "email", exclude_role_categories=[]), [], resolver, NOW)
    assert "hidden" not in off["sections"]["health"]
    assert "Actuarial Intern 0" in off["html"]


def test_hidden_listings_stay_in_the_data(space):
    go(space, [gh("1", "Actuarial Intern - Summer 2027"), gh("2", "Underwriting and Commercial Banking Intern - Summer 2027")])
    titles = {r["title"]: r for r in stored(space)}
    assert titles["Actuarial Intern - Summer 2027"]["status"] == "open"
    assert titles["Actuarial Intern - Summer 2027"]["relevance_score"] >= 50
    report = er.build_email(store.load_listings(space / "data"), {}, *email_inputs(space), NOW)
    assert shown(report) == ["Underwriting and Commercial Banking Intern - Summer 2027"]


# ------------------------------------------------------------ C. part-time and off-target titles

@pytest.mark.parametrize("location, codes", [("Chicago, IL", ["outside_home_keyword"]), ("Ames, IA", [])])
def test_part_time_term_time_only_near_home(cfg, resolver, location, codes):
    _listing, found = make(cfg, resolver, "Accounting Intern (Term-Time, Part-Time)", location)
    assert found == codes


@pytest.mark.parametrize("title", ["Part Time Tax Intern", "PART-TIME Tax Intern", "Tax Intern - term time"])
def test_part_time_matches_hyphen_and_space_forms(cfg, resolver, title):
    assert make(cfg, resolver, title, "Chicago, IL")[1] == ["outside_home_keyword"]


@pytest.mark.parametrize("title", ["Tax Intern - Parttime Pay", "Counterpart Timeline Intern", "Tax Intern"])
def test_part_time_is_whole_words_only(cfg, resolver, title):
    assert make(cfg, resolver, title, "Chicago, IL")[1] == []


def test_part_time_with_unknown_distance_is_not_kept(cfg, resolver):
    # "Chicago Riverside Plaza" has no coordinates but names a target metro, so it is normally kept.
    assert make(cfg, resolver, "Tax Intern", "Chicago Riverside Plaza")[1] == []
    listing = new_listing(COMPANY, "greenhouse", "1", "Part-Time Tax Intern", "Chicago Riverside Plaza", None)
    _place, exclusions = _evaluate(listing, cfg, resolver)
    assert exclusions[0][0] == "outside_home_keyword" and "distance is unknown" in exclusions[0][1]


def test_part_time_remote_iowa_is_kept(cfg, resolver):
    assert make(cfg, resolver, "Part-Time Tax Intern", "Iowa - Work From Home")[1] == []


def test_part_time_far_listing_becomes_filtered_and_near_one_stays_open(space):
    title = "Accounting Intern (Term-Time, Part-Time)"
    loose = lambda d: d.update(exclude_keywords_outside_home=[])
    (space / "config" / "config.yaml").write_text(
        yaml.safe_dump(edit_yaml(loose)), encoding="utf-8")
    go(space, [gh("1", title, "Chicago, IL"), gh("2", title, "Ames, IA")])
    assert {r["status"] for r in stored(space)} == {"open"}
    shutil.copy(ROOT / "config" / "config.yaml", space / "config" / "config.yaml")
    meta = go(space, [gh("1", title, "Chicago, IL"), gh("2", title, "Ames, IA")], day=4)
    rows = {r["location_raw"]: r for r in stored(space)}
    assert rows["Chicago, IL"]["status"] == "filtered"
    assert "part-time" in rows["Chicago, IL"]["filtered_reason"] and "150 miles" in rows["Chicago, IL"]["filtered_reason"]
    assert rows["Ames, IA"]["status"] == "open"
    assert meta["totals"]["status_changes"]["filtered"] == 1


def test_technology_title_is_penalized_with_a_reason(cfg, resolver):
    listing = kept(cfg, resolver, "Technology Risk Consulting Intern", "Chicago, IL")
    assert "-30 title: 'technology' is off-target" in listing["match_reasons"]
    plain = kept(cfg, resolver, "Risk Consulting Intern", "Chicago, IL")
    assert listing["relevance_score"] == plain["relevance_score"] - 30


def test_marketing_title_is_penalized(cfg, resolver):
    listing = kept(cfg, resolver, "Wealth Management Marketing Intern", "Chicago, IL")
    assert "-30 title: 'marketing' is off-target" in listing["match_reasons"]
    assert listing["relevance_score"] < cfg["email"]["min_score"]


def test_investment_banking_titles_are_never_penalized(cfg, resolver):
    for title in ("2027 Technology Investment Banking Summer Analyst", "Technology Banking Summer Analyst",
                  "Technology M&A Intern"):
        listing = kept(cfg, resolver, title, "Chicago, IL")
        assert not any("off-target" in r for r in listing["match_reasons"]), title


def test_penalties_add_up_and_respect_the_floor(cfg, resolver):
    listing, _ = make(cfg, resolver, "Technology Marketing Intern", "Chicago, IL")
    assert sum(1 for r in listing["match_reasons"] if "off-target" in r) == 2
    assert listing["relevance_score"] == 0
    assert any("score limited to 0" in r for r in listing["match_reasons"])


def test_penalty_values_come_from_config(cfg, resolver):
    changed = copy.deepcopy(cfg)
    changed["scoring"]["title_penalty_keywords"] = {"technology": -7}
    a = kept(cfg, resolver, "Technology Audit Intern", "Chicago, IL")["relevance_score"]
    b = kept(changed, resolver, "Technology Audit Intern", "Chicago, IL")["relevance_score"]
    assert b - a == 23


def test_no_role_cap_still_applies_after_a_penalty(cfg, resolver):
    changed = copy.deepcopy(cfg)
    changed["scoring"]["title_penalty_keywords"] = {"technology": 90}  # a bonus, to test the cap
    listing = kept(changed, resolver, "Technology Intern - Summer 2027", "Chicago, IL")
    assert listing["role_category"] is None
    assert listing["relevance_score"] == cfg["scoring"]["no_role_cap"]


# ------------------------------------------------------------ D. location named in the title

@pytest.mark.parametrize("title, expected", [
    ("Intern, Tax- Cincinnati, OH", ("Cincinnati", "OH")),
    ("Tax/Audit Intern - Winter 2028 - King of Prussia, PA", ("King of Prussia", "PA")),
    ("Wealth Management Advisor - St. Louis, MO", ("St. Louis", "MO")),
    ("Registered Client Service Associate-Winston-Salem, NC", ("Client Service Associate-Winston-Salem", "NC")),
    ("Commercial Counsel - Remote (IL, CA, NY)", None),
    ("Intern, IT Security", None),
    ("Tax Intern", None),
])
def test_title_place(title, expected):
    assert title_place(title) == expected


def test_title_names_city_cuts_at_spaces_and_hyphens():
    assert title_names_city("Client Service Associate-Winston-Salem", "Winston-Salem")
    assert title_names_city("Wealth Management Advisor-Pella", "Pella")
    assert title_names_city("Central Salt Lake City", "Salt Lake City")
    assert not title_names_city("Cincinnati", "Overland Park")
    assert not title_names_city("Salem", "Winston-Salem")


def test_mariner_title_conflict_is_tagged_and_shown(cfg, resolver):
    # The real Ashby record lists Cincinnati first and Overland Park second; Overland Park qualifies.
    listing = kept(cfg, resolver, "Intern, Tax- Cincinnati, OH", "Cincinnati, OH; Overland Park, KS")
    assert (listing["city"], listing["state"]) == ("Overland Park", "KS")  # the source location stands
    assert "location_conflict" in listing["tags"]
    report = er.build_email([listing], {}, cfg, [], resolver, NOW)
    assert "Overland Park, KS (title says Cincinnati, OH)" in report["html"]
    assert "Overland Park, KS (title says Cincinnati, OH)" in report["text"]


def test_given_location_alone_also_gets_the_tag(cfg, resolver):
    listing = kept(cfg, resolver, "Intern, Tax- Cincinnati, OH", "Overland Park, KS")
    assert listing["tags"] == ["location_conflict"]


@pytest.mark.parametrize("title, location", [
    ("Tax Intern - Des Moines, IA", "Des Moines, IA"),
    ("Tax Intern - DES MOINES, IA", "Des Moines, IA"),
    ("Tax Intern", "Overland Park, KS"),
    ("Wealth Management Intern - West Des Moines, IA", "West Des Moines, IA"),
])
def test_no_tag_when_the_title_agrees_or_names_nothing(cfg, resolver, title, location):
    listing = kept(cfg, resolver, title, location)
    assert "location_conflict" not in listing["tags"]
    assert "title says" not in er._place(listing)


def test_remote_iowa_tag_and_conflict_tag_can_coexist_without_harm(cfg, resolver):
    listing = kept(cfg, resolver, "Tax Intern - Chicago, IL", "Iowa - Work From Home")
    assert listing["tags"] == ["remote_iowa"]  # remote: no physical location to conflict with


# ------------------------------------------------------------ E. year-only seasons

def test_year_only_title_keeps_season_not_stated(cfg, resolver):
    listing = kept(cfg, resolver, "2028 Audit or Tax Intern", "Des Moines, IA")
    assert listing["season"] is None  # shown, and matched by email.seasons, as "Not stated"
    assert listing["season_year"] == 2028
    assert "+8 season: not stated" in listing["match_reasons"]  # no scoring change
    assert "2028 · season not stated" in er._season(listing)
    report = er.build_email([listing], {}, with_cfg(cfg, "email", seasons=["Not stated"]), [], resolver, NOW)
    assert listing["title"] in shown(report)
    assert "2028 · season not stated" in report["html"] and "2028 · season not stated" in report["text"]


@pytest.mark.parametrize("title, year", [
    ("2028 Audit or Tax Intern", 2028), ("Audit Intern (2026)", 2026), ("2030 Tax Intern", 2030),
    ("2031 Tax Intern", None), ("2025 Tax Intern", None), ("Summer 2028 Tax Intern", None),
    ("2027 Tax Winter Internship", None), ("Tax Intern 12028", None), ("Tax Intern", None),
    # A season word too far from the year for title_season still means it isn't year-only.
    ("2028 PMCF Investment Banking Summer Analyst", None),
])
def test_title_year_only(title, year):
    assert title_year_only(title) == year


def test_a_season_from_the_description_leaves_season_year_empty(cfg, resolver):
    listing = kept(cfg, resolver, "2028 Tax Intern", "Des Moines, IA", description="This is a Summer 2028 role.")
    assert listing["season"] == "Summer 2028" and listing["season_year"] is None


def test_old_records_load_with_an_empty_season_year(tmp_path):
    store.write_json(tmp_path / "internships.json", [{"id": "a", "title": "x"}])
    assert store.load_listings(tmp_path)[0]["season_year"] is None


# ------------------------------------------------------------ F. simulated failure in the workflow

def workflow():
    return yaml.safe_load((ROOT / ".github" / "workflows" / "scan.yml").read_text(encoding="utf-8"))


def test_simulate_failure_input_is_a_boolean_that_defaults_to_false():
    on = workflow()[True]  # PyYAML reads the key "on" as True
    assert on["workflow_dispatch"]["inputs"]["simulate_failure"]["type"] == "boolean"
    assert on["workflow_dispatch"]["inputs"]["simulate_failure"]["default"] is False
    assert "schedule" in on


def test_simulated_failure_runs_right_after_the_tests_and_stops_the_rest():
    steps = workflow()["jobs"]["scan"]["steps"]
    order = [s.get("id") for s in steps]
    sim = steps[order.index("simulate_failure")]
    assert order.index("simulate_failure") == order.index("tests") + 1
    assert sim["if"] == "${{ inputs.simulate_failure }}"
    assert "exit 1" in sim["run"]
    by_id = {s.get("id"): s for s in steps}
    # No "if" means GitHub's default success(), so both are skipped after the simulated failure.
    assert "if" not in by_id["scan"] and "if" not in by_id["email"]
    assert "steps.scan.outcome == 'success'" in by_id["commit"]["if"]
    failure = by_id["failure_email"]
    assert failure["if"] == "failure()"
    assert failure["env"]["SIMULATED"] == "${{ steps.simulate_failure.outcome }}"
    assert '"simulated failure=$SIMULATED"' in failure["run"]


def test_failure_email_names_the_simulated_step():
    outcomes = {"tests": "success", "simulated failure": "failure", "scan": "skipped", "email": "skipped", "commit": "skipped"}
    report = er.build_failure_email(NOW, "https://github.com/x/y/actions/runs/1", outcomes)
    assert "Steps that didn't succeed: simulated failure: failure." in report["text"]
    assert "scan" not in report["text"].split("Steps that didn't succeed:")[1].split("\n")[0]


def test_a_normal_failure_email_does_not_mention_the_simulation():
    report = er.build_failure_email(NOW, None, {"tests": "success", "simulated failure": "skipped", "scan": "failure"})
    assert "simulated" not in report["text"]


# ------------------------------------------------------------ pipeline helpers

GOOD = {"name": "Acme Financial", "ats": "greenhouse", "board": "acme", "cities": [], "priority": 1, "notes": "x"}


def edit_yaml(change):
    raw = yaml.safe_load((ROOT / "config" / "config.yaml").read_text(encoding="utf-8"))
    change(raw)
    return raw


@pytest.fixture
def space(tmp_path):
    config = tmp_path / "config"
    config.mkdir()
    for name in ("config.yaml", "cities.yaml"):
        shutil.copy(ROOT / "config" / name, config / name)
    (config / "companies.yaml").write_text(yaml.safe_dump({"companies": [GOOD]}), encoding="utf-8")
    return tmp_path


def gh(job_id, title, location="Des Moines, IA", content="Prepare returns."):
    return {"id": job_id, "title": title, "absolute_url": f"https://example.org/{job_id}", "location": {"name": location},
            "first_published": None, "application_deadline": None, "content": content}


def go(space, jobs, day=3):
    now = dt.datetime(2026, 11, day, 11, 30, tzinfo=dt.timezone.utc)
    return run(space / "config", space / "data", client=FakeClient({"boards/acme/": {"jobs": jobs}}), now=now)


def stored(space):
    return json.loads((space / "data" / "internships.json").read_text(encoding="utf-8"))


def email_inputs(space):
    cfg, companies, resolver, _listings, _meta = er.load_inputs(space / "config", space / "data")
    return cfg, companies, resolver


P5_1_JOBS = [
    gh("1", "Intern, Tax- Cincinnati, OH", "Cincinnati, OH; Overland Park, KS"),
    gh("2", "2028 Audit or Tax Intern"),
    gh("3", "Actuarial Intern - Summer 2027"),
    gh("4", "Credit Risk Intern - Summer 2027", "Chicago, IL"),
    gh("5", "Accounting Intern (Term-Time, Part-Time)", "Chicago, IL"),
    gh("6", "Accounting Intern (Term-Time, Part-Time)", "Ames, IA"),
    gh("7", "Technology Risk Consulting Intern", "Chicago, IL"),
    gh("8", "2027 Technology Investment Banking Summer Analyst", "Chicago, IL"),
]


def test_pipeline_end_to_end_and_reruns_change_nothing(space):
    go(space, P5_1_JOBS, day=3)
    first = (space / "data" / "internships.json").read_text(encoding="utf-8")
    rows = {r["title"] + "|" + r["location_raw"]: r for r in stored(space)}
    assert len(rows) == 7  # the far part-time listing is new and excluded, so it is never stored
    assert rows["Intern, Tax- Cincinnati, OH|Cincinnati, OH; Overland Park, KS"]["tags"] == ["location_conflict"]
    assert rows["2028 Audit or Tax Intern|Des Moines, IA"]["season_year"] == 2028
    assert rows["Accounting Intern (Term-Time, Part-Time)|Ames, IA"]["status"] == "open"
    assert all(r["status"] == "open" for r in rows.values())
    for day in (3, 4):  # a same-day rerun and a next-day run
        meta = go(space, P5_1_JOBS, day=day)
        assert meta["totals"]["listings_new"] == 0
        assert meta["totals"]["listings_after"] == 7
        assert meta["totals"]["status_changes"] == {"filtered": 0, "missed": 0, "possibly_closed": 0, "closed": 0,
                                                    "verified_open": 0, "check_failed": 0}
        assert (space / "data" / "internships.json").read_text(encoding="utf-8") == first
    assert len({r["id"] for r in stored(space)}) == 7


# ------------------------------------------------------------ the sample email

def sample_inputs(cfg, resolver):
    """Fixtures for docs/reports/P5_1_sample_email.html. Example addresses only."""
    rows = [
        kept(cfg, resolver, "2027 Investment Banking Summer Analyst", "Chicago, IL", first_seen=TODAY),
        kept(cfg, resolver, "2027 Technology Investment Banking Summer Analyst", "Chicago, IL", first_seen=TODAY),
        kept(cfg, resolver, "Intern, Tax- Cincinnati, OH", "Cincinnati, OH; Overland Park, KS", first_seen=TODAY),
        kept(cfg, resolver, "2028 Audit or Tax Intern", "Des Moines, IA"),
        kept(cfg, resolver, "Credit Risk Intern - Summer 2027", "Kansas City, MO"),
        kept(cfg, resolver, "Underwriting and Commercial Banking Intern - Summer 2027", "Dubuque, IA"),
        kept(cfg, resolver, "Accounting Intern (Term-Time, Part-Time)", "Ames, IA"),
        kept(cfg, resolver, "Tax Intern - Summer 2027", "Iowa - Work From Home"),
        # Hidden or below the bar, so they must not appear:
        kept(cfg, resolver, "Actuarial Intern - Summer 2027", "Des Moines, IA", first_seen=TODAY),
        kept(cfg, resolver, "Claims Intern - Summer 2028", "Chicago, IL"),
        kept(cfg, resolver, "Technology Risk Consulting Intern", "Chicago, IL"),
        kept(cfg, resolver, "Wealth Management Marketing Intern", "Chicago, IL"),
    ]
    far_part_time, codes = make(cfg, resolver, "Accounting Intern (Term-Time, Part-Time)", "Chicago, IL", job_id="far")
    assert codes == ["outside_home_keyword"]
    rows.append(dict(far_part_time, status="filtered", filtered_reason="part-time, far from home"))
    meta = manual_meta()
    meta["run_finished"] = "2026-11-03T11:58:00+00:00"
    return rows, meta, manual_companies()


SAMPLE_HIDDEN = ["Actuarial Intern - Summer 2027", "Claims Intern - Summer 2028", "Technology Risk Consulting Intern",
                 "Wealth Management Marketing Intern"]


def test_sample_email_shows_everything_p5_1_changed(cfg, resolver):
    rows, meta, companies = sample_inputs(cfg, resolver)
    report = er.build_email(rows, meta, cfg, companies, resolver, NOW)
    page = report["html"]
    assert "Overland Park, KS (title says Cincinnati, OH)" in page
    assert "2028 · season not stated" in page
    assert "Credit Risk Intern - Summer 2027" in page
    assert "Underwriting and Commercial Banking Intern - Summer 2027" in page
    assert "2027 Technology Investment Banking Summer Analyst" in page
    assert page.count("2028 · season not stated") == 1  # the IB title has a season word, so it isn't year-only
    assert "Accounting Intern (Term-Time, Part-Time)" in page and page.count("Term-Time, Part-Time") == 1  # Ames only
    assert "Ames, IA" in page
    for title in SAMPLE_HIDDEN:
        assert title not in page, title
    assert "…and 38 more manual companies." in page
    assert "2 insurance-only listings hidden." in page
    assert "@gmail.com" not in page and "@" not in page.replace("&#x27;", "")
