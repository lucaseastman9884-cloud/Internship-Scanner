import datetime as dt
import json
import shutil

import pytest
import yaml

from conftest import ROOT, FakeClient, load_fixture
from scanner import store
from scanner.__main__ import main
from scanner.adapters.base import Adapter
from scanner.http_client import RobotsBlocked
from scanner.normalize import new_listing
from scanner.pipeline import run
from scanner.text import make_snippet, scrub_contact_data

NOW = dt.datetime(2026, 11, 2, 11, 30, tzinfo=dt.timezone.utc)
LATER = dt.datetime(2026, 11, 3, 11, 30, tzinfo=dt.timezone.utc)


@pytest.fixture
def workspace(tmp_path):
    """A small registry: two healthy boards, one failing, plus manual and Workday entries."""
    config = tmp_path / "config"
    config.mkdir()
    for name in ("config.yaml", "cities.yaml"):
        shutil.copy(ROOT / "config" / name, config / name)
    companies = [
        {"name": "American Equity", "ats": "greenhouse", "board": "good", "cities": [], "priority": 1, "notes": "x"},
        {"name": "Broken Co", "ats": "greenhouse", "board": "broken", "cities": [], "priority": 1, "notes": "x"},
        {"name": "Lever Co", "ats": "lever", "board": "leverco", "cities": [], "priority": 1, "notes": "x"},
        {"name": "RR Donnelley", "ats": "smartrecruiters", "board": "RRDonnelley", "cities": [], "priority": 2, "notes": "x"},
        {"name": "Workday Co", "ats": "workday", "board": "https://w.wd1.myworkdayjobs.com/site", "cities": [], "priority": 1, "notes": "x"},
        {"name": "Manual Co", "ats": "manual", "board": "https://example.com/careers", "cities": [], "priority": 1, "notes": "x"},
    ]
    (config / "companies.yaml").write_text(yaml.safe_dump({"companies": companies}), encoding="utf-8")
    return tmp_path


def client():
    return FakeClient({
        "boards/good/": load_fixture("greenhouse_board.json"),
        "boards/broken/": RuntimeError("board exploded"),
        "postings/leverco": load_fixture("lever_postings.json"),
        "w.wd1.myworkdayjobs.com": {"total": 0, "jobPostings": []},
    })


def run_pipeline(workspace, now=NOW):
    return run(workspace / "config", workspace / "data", client=client(), now=now)


def data(workspace, name):
    return json.loads((workspace / "data" / name).read_text(encoding="utf-8"))


def by_company(meta):
    return {row["company"]: row for row in meta["companies"]}


# --- Isolation ---

def test_one_failing_adapter_does_not_stop_the_others(workspace):
    meta = run_pipeline(workspace)
    rows = by_company(meta)
    assert rows["Broken Co"]["status"] == "error"
    assert rows["American Equity"]["status"] == "ok" and rows["American Equity"]["kept"] > 0
    assert rows["Lever Co"]["status"] == "ok" and rows["Lever Co"]["kept"] == 1
    assert len(data(workspace, "internships.json")) > 0


def test_meta_records_the_error(workspace):
    run_pipeline(workspace)
    meta = data(workspace, "meta.json")
    errors = {e["company"]: e for e in meta["errors"]}
    assert "board exploded" in errors["Broken Co"]["error"]
    assert meta["source_health"]["greenhouse"] == {"ok": 1, "error": 1}


def test_an_adapter_of_any_type_raising_is_isolated(workspace):
    class Exploding(Adapter):
        def fetch(self, company, wants_detail=None):
            raise KeyError("surprise")

    meta = run(workspace / "config", workspace / "data", client=client(), now=NOW,
               adapters={"greenhouse": Exploding, "lever": Exploding, "smartrecruiters": Exploding})
    assert all(r["status"] == "error" for r in meta["companies"] if r["ats"] in ("greenhouse", "lever", "smartrecruiters"))
    assert data(workspace, "internships.json") == []


def test_robots_block_is_reported_with_a_manual_link(workspace):
    fake = client()
    fake.routes["boards/good/"] = RobotsBlocked("robots.txt does not allow this request")
    row = by_company(run(workspace / "config", workspace / "data", client=fake, now=NOW))["American Equity"]
    assert row["status"] == "manual_fallback"
    assert row["fallback_link"] == "https://job-boards.greenhouse.io/good"


def test_smartrecruiters_makes_no_request_d015(workspace):
    fake = client()
    meta = run(workspace / "config", workspace / "data", client=fake, now=NOW)
    row = by_company(meta)["RR Donnelley"]
    assert row["status"] == "skipped" and row["fallback_link"] == "https://careers.smartrecruiters.com/RRDonnelley"
    assert not any("smartrecruiters" in url for url in fake.requested)


def test_manual_company_makes_no_request_and_keeps_its_link(workspace):
    fake = client()
    meta = run(workspace / "config", workspace / "data", client=fake, now=NOW)
    row = by_company(meta)["Manual Co"]
    assert row["status"] == "manual" and row["fallback_link"] == "https://example.com/careers"
    assert not any("example.com" in url for url in fake.requested)


# --- Idempotency ---

def healthy_client():
    fake = client()
    fake.routes["boards/broken/"] = {"jobs": []}
    return fake


def test_running_twice_gives_identical_files(workspace):
    run(workspace / "config", workspace / "data", client=healthy_client(), now=NOW)
    first = {name: (workspace / "data" / name).read_bytes()
             for name in ("internships.json", "companies_status.json", "excluded_last_run.json")}
    second_meta = run(workspace / "config", workspace / "data", client=healthy_client(), now=NOW)
    for name, content in first.items():
        assert (workspace / "data" / name).read_bytes() == content, name
    assert second_meta["totals"]["listings_new"] == 0
    assert second_meta["totals"]["listings_before"] == second_meta["totals"]["listings_after"]


def test_a_failure_on_consecutive_runs_is_counted(workspace):
    run_pipeline(workspace)
    run_pipeline(workspace)
    entry = data(workspace, "companies_status.json")["broken-co"]
    assert entry["fetch_health"]["consecutive_failures"] == 2


def test_listings_are_unchanged_by_a_rerun_even_when_a_source_keeps_failing(workspace):
    run_pipeline(workspace)
    first = (workspace / "data" / "internships.json").read_bytes()
    run_pipeline(workspace)
    assert (workspace / "data" / "internships.json").read_bytes() == first


def test_no_duplicate_ids(workspace):
    run_pipeline(workspace)
    run_pipeline(workspace)
    ids = [x["id"] for x in data(workspace, "internships.json")]
    assert len(ids) == len(set(ids))


def test_input_order_does_not_change_the_output(workspace):
    def shuffled_client():
        board = load_fixture("greenhouse_board.json")
        board["jobs"].reverse()
        return FakeClient({**client().routes, "boards/good/": board})

    run_pipeline(workspace)
    first = (workspace / "data" / "internships.json").read_bytes()
    run(workspace / "config", workspace / "data", client=shuffled_client(), now=NOW)
    assert (workspace / "data" / "internships.json").read_bytes() == first


def test_later_run_keeps_first_seen_and_updates_last_seen(workspace):
    run_pipeline(workspace, NOW)
    run_pipeline(workspace, LATER)
    last_seen = data(workspace, "last_seen.json")
    for listing in data(workspace, "internships.json"):
        assert listing["first_seen"] == "2026-11-02"
        assert last_seen[listing["id"]] == "2026-11-03"


def test_a_new_day_with_no_changes_leaves_internships_json_untouched(workspace):
    """P4 commits only when data changes, so the daily last_seen must live elsewhere."""
    run_pipeline(workspace, NOW)
    first = (workspace / "data" / "internships.json").read_bytes()
    run_pipeline(workspace, LATER)
    assert (workspace / "data" / "internships.json").read_bytes() == first
    assert b"last_seen" not in first and b"run_started" not in first


def test_listing_missing_later_is_never_deleted(workspace):
    run_pipeline(workspace, NOW)
    before = {x["id"] for x in data(workspace, "internships.json")}
    fake = client()
    fake.routes["boards/good/"] = {"jobs": []}
    run(workspace / "config", workspace / "data", client=fake, now=LATER)
    after = data(workspace, "internships.json")
    assert {x["id"] for x in after} == before
    gone = next(x for x in after if x["title"] == "Accounting Intern")
    assert data(workspace, "last_seen.json")[gone["id"]] == "2026-11-02"
    assert gone["status"] == "open" and gone["missed_runs"] == 1  # one miss is below N


# --- Dedupe ---

COMPANY = {"company_id": "acme", "name": "Acme", "board": "acme", "ats": "greenhouse"}


def stored(source, job_id, title="Tax Intern", city="Chicago"):
    listing = new_listing(COMPANY, source, job_id, title, f"{city}, IL", f"https://{source}.test/{job_id}")
    listing["city"] = city
    return listing


def test_cross_source_duplicates_merge_and_keep_every_link():
    merged, added, _ = store.upsert([], [stored("greenhouse", "1"), stored("lever", "abc")], "2026-11-02")
    assert added == 1 and len(merged) == 1
    assert {s["source_name"] for s in merged[0]["sources"]} == {"greenhouse", "lever"}


def test_same_title_in_different_cities_stays_separate():
    merged, _, _ = store.upsert([], [stored("greenhouse", "1"), stored("greenhouse", "2", city="Dubuque")], "2026-11-02")
    assert len(merged) == 2


def test_new_source_for_a_known_listing_keeps_its_id_and_first_seen():
    first, _, _ = store.upsert([], [stored("greenhouse", "1")], "2026-11-02")
    second, added, updated = store.upsert(first, [stored("lever", "abc")], "2026-11-05")
    assert (added, updated) == (0, 1)
    assert second[0]["id"] == first[0]["id"]
    assert second[0]["first_seen"] == "2026-11-02" and second[0]["last_seen"] == "2026-11-05"
    assert len(second[0]["sources"]) == 2


def test_renamed_job_with_the_same_source_id_updates_in_place():
    first, _, _ = store.upsert([], [stored("greenhouse", "1")], "2026-11-02")
    second, added, _ = store.upsert(first, [stored("greenhouse", "1", title="Tax Intern - Summer 2027")], "2026-11-03")
    assert added == 0 and len(second) == 1
    assert second[0]["title"] == "Tax Intern - Summer 2027"


def test_ids_are_stable_hashes():
    assert stored("greenhouse", "1")["id"] == stored("greenhouse", "1")["id"]
    assert stored("greenhouse", "1")["id"] != stored("greenhouse", "2")["id"]


# --- Output files ---

def test_kept_and_excluded_are_decided_correctly(workspace):
    run_pipeline(workspace)
    titles = {x["title"] for x in data(workspace, "internships.json")}
    assert {"Accounting Intern", "Tax Intern", "IT Intern, SAP Security"} <= titles
    excluded = {x["title"]: x for x in data(workspace, "excluded_last_run.json")}
    assert excluded["Director, Internal Sales"]["primary_reason"] == "not_internship"
    assert excluded["2027 Summer Sales Internship"]["primary_reason"] == "location"


def test_stored_listings_have_every_spec_field_and_no_working_fields(workspace):
    run_pipeline(workspace)
    for listing in data(workspace, "internships.json"):
        assert not [k for k in listing if k.startswith("_")]
        assert listing["relevance_score"] >= 0 and listing["match_reasons"]
        assert listing["eligibility"]["reason"]
        assert isinstance(listing["lat"], float) and isinstance(listing["lng"], float)  # from the city table
        assert listing["location_label"] != "Location unknown"


def test_meta_has_counts_and_times(workspace):
    meta = run_pipeline(workspace)
    assert meta["run_started"] and meta["run_finished"]
    totals = meta["totals"]
    assert totals["fetched"] == totals["kept"] + totals["excluded"]
    row = by_company(meta)["American Equity"]
    assert row["fetched"] == row["kept"] + row["excluded"]
    assert sum(row["exclusion_reasons"].values()) == row["excluded"]


def test_company_status_counts_interns_anywhere(workspace):
    run_pipeline(workspace)
    entry = data(workspace, "companies_status.json")["american-equity"]
    assert entry["fetch_health"]["status"] == "ok"
    assert entry["open_intern_count"] == 4  # includes the Dallas internship
    assert entry["last_intern_posting_seen"]["seen_on"] == "2026-11-02"
    assert entry["last_checked"]


def test_failed_company_keeps_its_last_known_counts_and_stays_listed(workspace):
    run_pipeline(workspace, NOW)
    fake = client()
    fake.routes["boards/good/"] = RuntimeError("down today")
    run(workspace / "config", workspace / "data", client=fake, now=LATER)
    entry = data(workspace, "companies_status.json")["american-equity"]
    assert entry["fetch_health"]["status"] == "error"
    assert entry["fetch_health"]["consecutive_failures"] == 1
    assert entry["open_intern_count"] == 4
    assert entry["last_intern_posting_seen"]["seen_on"] == "2026-11-02"


def test_company_removed_from_registry_stays_in_status(workspace):
    run_pipeline(workspace, NOW)
    path = workspace / "config" / "companies.yaml"
    registry = yaml.safe_load(path.read_text(encoding="utf-8"))
    registry["companies"] = [c for c in registry["companies"] if c["name"] != "American Equity"]
    path.write_text(yaml.safe_dump(registry), encoding="utf-8")
    run_pipeline(workspace, LATER)
    assert "american-equity" in data(workspace, "companies_status.json")


def test_damaged_history_stops_the_run_and_is_not_overwritten(workspace):
    damaged = workspace / "data" / "internships.json"
    damaged.parent.mkdir()
    damaged.write_text("{not json", encoding="utf-8")
    with pytest.raises(store.StoreError):
        run_pipeline(workspace)
    assert damaged.read_text(encoding="utf-8") == "{not json"


# --- Privacy ---

# Built at runtime so that the repo itself contains no address or number for a scan to find.
FAKE_EMAIL = "recruiter" + "@" + "example.com"
FAKE_PHONE = "515" + "-555-" + "0100"


def test_scrub_removes_emails_phones_and_profile_links():
    text = f"Write {FAKE_EMAIL} or call {FAKE_PHONE} or see https://www.linkedin.com/in/someone now"
    cleaned = scrub_contact_data(text)
    assert FAKE_EMAIL not in cleaned and FAKE_PHONE not in cleaned and "linkedin" not in cleaned


def test_snippet_drops_sentences_that_invite_contact():
    snippet = make_snippet(f"Prepare workpapers. Contact Pat Example at {FAKE_EMAIL} with questions. Learn audit.")
    assert snippet == "Prepare workpapers. Learn audit."


def test_contact_data_in_a_posting_never_reaches_the_data_files(workspace):
    board = {"jobs": [{
        "id": 1, "title": "Tax Intern", "absolute_url": "https://example.org/1",
        "location": {"name": "Des Moines, Iowa"}, "first_published": None, "application_deadline": None,
        "content": f"Prepare returns for {FAKE_EMAIL} and {FAKE_PHONE}. Graduating in 2028, ask {FAKE_EMAIL}.",
    }]}
    fake = client()
    fake.routes["boards/good/"] = board
    run(workspace / "config", workspace / "data", client=fake, now=NOW)
    for path in (workspace / "data").glob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert FAKE_EMAIL not in text and FAKE_PHONE not in text, path.name


# --- Command line ---

def test_bad_config_stops_with_a_clear_message(workspace, capsys):
    path = workspace / "config" / "config.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace('remote: "exclude"', 'remote: "maybe"'), encoding="utf-8")
    code = main(["run", "--config-dir", str(workspace / "config"), "--data-dir", str(workspace / "data")])
    assert code == 2
    assert "remote must be one of" in capsys.readouterr().err
    assert not (workspace / "data").exists()
