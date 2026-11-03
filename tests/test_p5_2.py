"""P5.2: IB coverage (D-035). Offline only: conftest blocks sockets, and no email is sent.

Covers the registry's new `tags`, the manual-list order with email.manual_first_tags, the wider
season pairing, and a newly added Workday firm failing without stopping the run.
"""
import datetime as dt
import shutil

import pytest
import yaml

from conftest import ROOT, FakeClient
from scanner import email_report as er
from scanner.config import ATS_VALUES, ConfigError, load_companies, load_config
from scanner.http_client import HttpError
from scanner.normalize import detect_season, title_season, title_season_conflict, title_year_only
from scanner.pipeline import run
from test_p5_1 import NOW, kept, make, manual_companies, manual_meta, with_cfg, write_config

REGISTRY = ROOT / "config" / "companies.yaml"
REQUIRED = {"name", "ats", "board", "cities", "priority", "notes"}


# ------------------------------------------------------------ registry validation (test 2)

def raw_registry():
    return yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["companies"]


def test_every_registry_entry_has_the_required_fields_and_valid_values():
    for entry in raw_registry():
        label = entry.get("name")
        assert REQUIRED <= set(entry) <= REQUIRED | {"tags"}, label
        assert entry["ats"] in ATS_VALUES, label
        assert entry["priority"] in (1, 2, 3), label
        assert isinstance(entry["cities"], list) and all(isinstance(c, str) for c in entry["cities"]), label
        assert isinstance(entry["notes"], str) and entry["notes"].strip(), label
        if "tags" in entry:
            assert isinstance(entry["tags"], list) and all(isinstance(t, str) and t.strip() for t in entry["tags"]), label


def test_the_real_registry_loads_and_every_company_gets_a_tags_list():
    companies = load_companies(REGISTRY)
    assert all(isinstance(c["tags"], list) for c in companies)
    assert len(companies) == 114


def test_ib_firms_are_tagged_priority_1_and_use_the_verified_sources():
    by_name = {c["name"]: c for c in load_companies(REGISTRY)}
    expected = {
        "Piper Sandler": ("workday", "https://pipersandler.wd501.myworkdayjobs.com/Piper_Sandler_Careers"),
        "Stout": ("workday", "https://stout.wd5.myworkdayjobs.com/Stout-Student-Careers"),
        "Lincoln International": ("greenhouse", "lincolninternational"),
    }
    for name, (ats, board) in expected.items():
        assert (by_name[name]["ats"], by_name[name]["board"]) == (ats, board), name
    for name in ("Baird", "Houlihan Lokey", "Moelis & Company", "D.A. Davidson", "Fireclay Partners",
                 "Lazard", "Stifel", "Jefferies", "Mesirow", "Kroll"):
        assert by_name[name]["ats"] == "manual", name
    ib = [c for c in by_name.values() if "ib" in c["tags"]]
    assert len(ib) == 16 and all(c["priority"] == 1 for c in ib)


def write_registry(tmp_path, entries):
    path = tmp_path / "companies.yaml"
    path.write_text(yaml.safe_dump({"companies": entries}), encoding="utf-8")
    return path


BASE = {"name": "Acme", "ats": "manual", "board": None, "cities": [], "priority": 1, "notes": "x"}


@pytest.mark.parametrize("tags", ["ib", [""], [1], {"ib": True}, None])
def test_bad_tags_are_rejected_with_a_clear_message(tmp_path, tags):
    with pytest.raises(ConfigError, match="tags must be a list"):
        load_companies(write_registry(tmp_path, [{**BASE, "tags": tags}]))


def test_tags_are_optional_and_unknown_keys_are_still_rejected(tmp_path):
    assert load_companies(write_registry(tmp_path, [BASE]))[0]["tags"] == []
    assert load_companies(write_registry(tmp_path, [{**BASE, "tags": ["ib"]}]))[0]["tags"] == ["ib"]
    with pytest.raises(ConfigError, match="unknown:tag"):
        load_companies(write_registry(tmp_path, [{**BASE, "tag": ["ib"]}]))


# ------------------------------------------------------------ email.manual_first_tags setting

def test_manual_first_tags_is_in_config(cfg):
    assert cfg["email"]["manual_first_tags"] == ["ib"]


def test_max_manual_leaves_room_for_every_ib_manual_firm_and_two_failures(cfg):
    # D-041: the reason for the cap, checked against the registry rather than a fixed number.
    ib_manual = [c for c in load_companies(REGISTRY) if c["ats"] == "manual" and "ib" in c["tags"]]
    assert cfg["email"]["max_manual"] >= len(ib_manual) + 2


@pytest.mark.parametrize("value", ["ib", [""], [3], None])
def test_bad_manual_first_tags_are_rejected(tmp_path, cities, value):
    path = write_config(tmp_path, lambda d: d["email"].update(manual_first_tags=value))
    with pytest.raises(ConfigError, match="email.manual_first_tags"):
        load_config(path, cities)


def test_missing_manual_first_tags_is_rejected(tmp_path, cities):
    path = write_config(tmp_path, lambda d: d["email"].pop("manual_first_tags"))
    with pytest.raises(ConfigError, match="manual_first_tags"):
        load_config(path, cities)


# ------------------------------------------------------------ manual-list order (test 3)

def ib_meta_and_companies(failed=2, ib=3, other=12):
    """Failed X/Y (priority 3), IB A..C (priority 2, tagged), and Manual 00.. with mixed priority."""
    meta = manual_meta(failed=failed, manual=other)
    companies = manual_companies(failed=failed, manual=other)
    for i in range(ib):
        name = f"IB {chr(67 - i)}"  # IB C, IB B, IB A, so sorting is visible
        meta["check_manually"].append({"company": name, "url": f"https://ib{i}.example/careers", "reason": "manual", "detail": None})
        companies.append({"name": name, "priority": 2, "tags": ["ib"]})
    return meta, companies


def test_failed_today_then_ib_tagged_then_priority_order(cfg, resolver):
    meta, companies = ib_meta_and_companies()
    s = er.build_email([], meta, with_cfg(cfg, "email", max_manual=100), companies, resolver, NOW)["sections"]
    names = [m["company"] for m in s["manual"]]
    assert names[:2] == ["Failed Y", "Failed Z"]
    assert names[2:5] == ["IB A", "IB B", "IB C"]  # tagged, ahead of every priority-1 manual company
    assert names[5:9] == ["Manual 01", "Manual 04", "Manual 07", "Manual 10"]  # then priority 1, 2, 3
    assert names[9:] == ["Manual 02", "Manual 05", "Manual 08", "Manual 11", "Manual 00", "Manual 03", "Manual 06", "Manual 09"]


def test_an_ib_firm_that_failed_today_is_listed_with_the_failures(cfg, resolver):
    meta, companies = ib_meta_and_companies(failed=1, ib=1, other=2)
    meta["check_manually"].append({"company": "IB Down", "url": "https://down.example", "reason": "manual_fallback", "detail": "HTTP 403"})
    companies.append({"name": "IB Down", "priority": 1, "tags": ["ib"]})
    s = er.build_email([], meta, cfg, companies, resolver, NOW)["sections"]
    names = [m["company"] for m in s["manual"]]
    assert names[:3] == ["Failed Z", "IB Down", "IB C"]
    assert not s["manual"][1]["first"]  # shown under "Couldn't be fetched today", not the IB line


def test_the_cap_keeps_the_ib_firms_and_summarizes_the_rest(cfg, resolver):
    cap = cfg["email"]["max_manual"]
    meta, companies = ib_meta_and_companies(failed=2, ib=3, other=45)
    report = er.build_email([], meta, cfg, companies, resolver, NOW)
    s = report["sections"]
    names = [m["company"] for m in s["manual"]]
    assert len(names) == cap and names[2:5] == ["IB A", "IB B", "IB C"]
    assert s["manual_more"] == 50 - cap
    for body in (report["html"], report["text"]):
        assert f"…and {50 - cap} more manual companies." in body
        assert "Check these manually (50)" in body
    assert "<b>IB firms, no feed:</b>" in report["html"]
    assert "<b>Other, no feed, check by hand:</b>" in report["html"]
    assert "- IB A (IB): https://ib" in report["text"]


def p5_1_order(meta, companies):
    """The P5.1 sort, copied here so the comparison doesn't depend on the code under test."""
    priority = {c["name"]: c["priority"] for c in companies}
    rows = [dict(r, priority=priority.get(r["company"], 9)) for r in meta["check_manually"]]
    rows.sort(key=lambda r: (r["reason"] == "manual", r["priority"] if r["reason"] == "manual" else 0, r["company"].lower()))
    return [r["company"] for r in rows]


@pytest.mark.parametrize("max_manual", [10, 12, 100])
def test_empty_manual_first_tags_gives_the_p5_1_order(cfg, resolver, max_manual):
    meta, companies = ib_meta_and_companies(failed=3, ib=3, other=20)
    off = with_cfg(cfg, "email", manual_first_tags=[], max_manual=max_manual)
    report = er.build_email([], meta, off, companies, resolver, NOW)
    assert [m["company"] for m in report["sections"]["manual"]] == p5_1_order(meta, companies)[:max_manual]
    assert "IB firms" not in report["html"] and "(IB)" not in report["text"]
    assert "<b>No feed, check by hand:</b>" in report["html"]


# ------------------------------------------------------------ season detection (test 4)

@pytest.mark.parametrize("title, season", [
    ("2028 PMCF Investment Banking Summer Analyst", "Summer 2028"),
    ("Summer 2028 Analyst", "Summer 2028"),
    ("2028 Summer Analyst Intern | M&A", "Summer 2028"),       # real Lincoln International title
    ("Summer Investment Banking Analyst Program, Chicago 2027", "Summer 2027"),
    ("2027 IT-Product & Strategy Summer Intern", "Summer 2027"),
    ("2028 Analyst Program", None),
    ("2027 Summer / 2028 Winter Program", None),
    ("Federal Tax Associate (Fall 2027/Winter 2028)", None),  # real RSM title: two seasons
    ("Winter/Spring 2027 Intern", None),
    ("Full Time Analyst 2027 (for 2026 Summer interns only)", None),  # two years
    ("Summer 2027 and Summer 2027 Analyst", "Summer 2027"),   # the same pair twice isn't a conflict
    ("Autumn Analyst ... Fall 2027", "Fall 2027"),            # autumn and fall are one season
    ("Summer 2025 Intern", "Summer 2025"),                    # side by side, any year, as before
    ("2031 PMCF Investment Banking Summer Analyst", None),    # far apart and outside 2026-2030
    ("2031 Investment Banking Summer Analyst", "Summer 2031"),  # two words apart: the P5.1 rule, any year
    ("Summer Analyst", None),
])
def test_title_season(title, season):
    assert title_season(title) == season


def test_analyst_program_with_a_year_only_keeps_season_year(cfg, resolver):
    listing, codes = make(cfg, resolver, "2028 Analyst Program", "Des Moines, IA")
    assert listing["season"] is None and listing["season_year"] == 2028
    # No internship word and no season, so D-018 doesn't admit it. That is unchanged by P5.2.
    assert codes == ["not_internship"]


@pytest.mark.parametrize("title, why", [
    ("2027 Summer / 2028 Winter Program", "more than one season (Summer, Winter)"),
    ("Summer Analyst 2027 (2028 graduates)", "more than one year (2027, 2028)"),
])
def test_conflicting_titles_say_why(title, why):
    assert why in title_season_conflict(title)
    assert title_year_only(title) is None  # a season word anywhere means it isn't year-only (D-036 item 5)


def test_a_conflict_is_logged_in_match_reasons_and_scores_as_not_stated(cfg, resolver):
    listing = kept(cfg, resolver, "2027 Summer / 2028 Winter Intern Program", "Des Moines, IA")
    assert listing["season"] is None and listing["season_year"] is None
    reason = next(r for r in listing["match_reasons"] if "season" in r)
    assert reason.startswith("+8 season: not stated (title names more than one season")


def test_a_conflicting_title_does_not_take_a_season_from_the_description(cfg):
    assert detect_season("2027 Summer / 2028 Winter Program", "This is a Summer 2027 role.", cfg) == (None, None)


def test_plante_moran_ib_title_now_scores_summer_2028(cfg, resolver):
    listing = kept(cfg, resolver, "2028 PMCF Investment Banking Summer Analyst", "Chicago, IL")
    assert listing["season"] == "Summer 2028"
    assert "+25 season: Summer 2028 (weight 1.0)" in listing["match_reasons"]


# ------------------------------------------------------------ adapter isolation (test 5)

GOOD = {"name": "Good Co", "ats": "greenhouse", "board": "good", "cities": [], "priority": 2, "notes": "x"}
PIPER = {"name": "Piper Sandler", "ats": "workday", "board": "https://pipersandler.wd501.myworkdayjobs.com/Piper_Sandler_Careers",
         "cities": ["Chicago"], "priority": 1, "tags": ["ib"], "notes": "x"}
LAZARD = {"name": "Lazard", "ats": "manual", "board": "https://lazard.example/careers", "cities": [], "priority": 1,
          "tags": ["ib"], "notes": "x"}
PELLA = {"name": "Pella", "ats": "manual", "board": "https://pella.example/careers", "cities": [], "priority": 1, "notes": "x"}


def test_a_new_workday_firm_answering_403_fails_alone_and_leads_the_manual_list(tmp_path, cfg, resolver):
    config = tmp_path / "config"
    config.mkdir()
    for name in ("config.yaml", "cities.yaml"):
        shutil.copy(ROOT / "config" / name, config / name)
    companies = [GOOD, PIPER, LAZARD, PELLA]
    (config / "companies.yaml").write_text(yaml.safe_dump({"companies": companies}), encoding="utf-8")
    job = {"id": 1, "title": "Tax Intern", "absolute_url": "https://example.org/1", "location": {"name": "Des Moines, Iowa"},
           "first_published": None, "application_deadline": None, "content": "Prepare returns."}
    client = FakeClient({"boards/good/": {"jobs": [job]}, "myworkdayjobs.com": HttpError("HTTP 403", 403)})

    meta = run(config, tmp_path / "data", client=client, now=dt.datetime(2026, 11, 3, 11, 30, tzinfo=dt.timezone.utc))
    rows = {r["company"]: r for r in meta["companies"]}
    assert rows["Piper Sandler"]["status"] == "manual_fallback"
    assert rows["Good Co"]["status"] == "ok" and rows["Good Co"]["kept"] == 1  # the run kept going
    assert meta["totals"]["companies_failed"] == 1

    s = er.build_email([], meta, cfg, load_companies(config / "companies.yaml"), resolver, NOW)["sections"]
    assert [m["company"] for m in s["manual"]] == ["Piper Sandler", "Lazard", "Pella"]
    assert s["manual"][0]["reason"] == "manual_fallback"
