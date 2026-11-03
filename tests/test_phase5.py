"""Phase 5: the morning email. Offline only: SMTP is always a fake, and conftest blocks sockets."""
import copy
import datetime as dt
import json
import shutil
import smtplib

import pytest
import yaml

from conftest import ROOT
from scanner import email_report as er
from scanner import store
from scanner.__main__ import main
from scanner.config import ConfigError, load_config

# 12:00 UTC is 6:00 AM in Ames on 2026-11-03, after the 5:33 AM scan.
NOW = dt.datetime(2026, 11, 3, 12, 0, tzinfo=dt.timezone.utc)
TODAY = "2026-11-03"
ENV = {"SMTP_USERNAME": "sender@example.com", "SMTP_APP_PASSWORD": "ab12 cd34 ef56 gh78", "EMAIL_TO": "to@example.com"}


def listing(id_, score=80, status="open", first_seen="2026-10-01", season="Summer 2027", city="Des Moines",
            state="IA", lat=41.5725, lng=-93.6105, deadline=None, tags=None, label=None, location_raw=None, **extra):
    base = {
        "id": id_, "company_id": "acme", "company": "Acme Insurance", "title": f"Finance Intern {id_}",
        "ats": "greenhouse", "status": status, "relevance_score": score, "first_seen": first_seen,
        "season": season, "city": city, "state": state, "lat": lat, "lng": lng, "deadline": deadline,
        "tags": tags or [], "is_remote": "remote_iowa" in (tags or []),
        "location_label": label or (f"{city}, {state}" if city else "Location unknown"),
        "location_raw": location_raw if location_raw is not None else (f"{city}, {state}" if city else ""),
        "apply_url": f"https://boards.greenhouse.io/acme/jobs/{id_}",
        "sources": [{"source_name": "greenhouse", "source_job_id": id_, "url": f"https://boards.greenhouse.io/acme/jobs/{id_}"}],
        "match_reasons": ["+40 role: 'finance intern' in title (corporate_finance)", "+20 location: Des Moines metro",
                          "+25 season: Summer 2027 (weight 1.0)", "+10 eligibility: eligible"],
        "filtered_reason": None,
    }
    base.update(extra)
    return base


META = {
    "run_started": "2026-11-03T11:33:00+00:00", "run_finished": "2026-11-03T12:00:00+00:00",
    "totals": {"companies_fetched_ok": 57, "companies_live": 58, "companies_failed": 1},
    "source_health": {"workday": {"ok": 41, "error": 1}, "greenhouse": {"ok": 15}, "ashby": {"ok": 1}, "manual": {"manual": 2}},
    "companies": [{"status": "manual"}, {"status": "manual"}],
    "check_manually": [
        {"company": "Wells Fargo", "url": "https://www.wellsfargojobs.com", "reason": "manual", "detail": None},
        {"company": "Broken Bank", "url": "https://broken.example/careers", "reason": "error", "detail": "HttpError"},
        {"company": "No Link Co", "url": None, "reason": "manual", "detail": None},
    ],
}
COMPANIES = [{"name": "Wells Fargo", "priority": 1}, {"name": "Broken Bank", "priority": 2}, {"name": "No Link Co", "priority": 3}]


class RefuseSMTP:
    def __init__(self, *args, **kwargs):
        raise AssertionError("a test tried to use real SMTP")


@pytest.fixture(autouse=True)
def no_real_smtp(monkeypatch):
    monkeypatch.setattr(smtplib, "SMTP", RefuseSMTP)
    monkeypatch.setattr(smtplib, "SMTP_SSL", RefuseSMTP)


def with_email(cfg, **changes):
    out = copy.deepcopy(cfg)
    out["email"].update(changes)
    return out


def build(listings, cfg, resolver, meta=None, now=NOW):
    return er.build_email(listings, META if meta is None else meta, cfg, COMPANIES, resolver, now)


def ids(items):
    return [x["id"] for x in items]


# ------------------------------------------------------------ status first

def test_only_open_listings_appear(cfg, resolver):
    rows = [listing("open1"), listing("filt", status="filtered"), listing("poss", status="possibly_closed"),
            listing("closed", status="closed")]
    for row in rows:
        row["first_seen"] = TODAY
    report = build(rows, cfg, resolver)
    s = report["sections"]
    shown = ids(s["new"]) + ids(s["top_open"]) + ids(s["deadlines"]) + ids(s["remote_iowa"])
    assert shown == ["open1"]
    for hidden in ("filt", "poss", "closed"):
        assert f"Finance Intern {hidden}" not in report["html"]
        assert f"Finance Intern {hidden}" not in report["text"]


def test_a_filtered_listing_with_a_stale_high_score_is_still_excluded(cfg, resolver):
    # D-024: a filtered listing keeps its old score, so the status check must come before min_score.
    rows = [listing("stale", status="filtered", score=100, first_seen=TODAY, deadline="2026-11-05")]
    s = build(rows, cfg, resolver)["sections"]
    assert not (s["new"] or s["top_open"] or s["deadlines"])


# ------------------------------------------------------------ config filters

def test_min_score_is_respected_including_the_boundary(cfg, resolver):
    floor = cfg["email"]["min_score"]
    rows = [listing("at", score=floor), listing("below", score=floor - 1)]
    s = build(rows, cfg, resolver)["sections"]
    assert ids(s["top_open"]) == ["at"]
    s = build(rows, with_email(cfg, min_score=floor + 1), resolver)["sections"]
    assert s["top_open"] == []


def test_max_new_and_max_top_open_are_respected(cfg, resolver):
    rows = [listing(f"n{i}", score=90 - i, first_seen=TODAY) for i in range(5)]
    rows += [listing(f"o{i}", score=70 - i) for i in range(5)]
    small = with_email(cfg, max_new=2, max_top_open=3)
    s = build(rows, small, resolver)["sections"]
    assert ids(s["new"]) == ["n0", "n1"]
    assert s["new_total"] == 5  # the subject counts every new listing, not only those shown
    # Top open skips what "New" already showed, so the unshown new ones can appear there.
    assert ids(s["top_open"]) == ["n2", "n3", "n4"]
    report = build(rows, small, resolver)
    assert "3 more new listing(s)" in report["text"]


def test_new_is_sorted_by_score(cfg, resolver):
    rows = [listing("low", score=60, first_seen=TODAY), listing("high", score=95, first_seen=TODAY),
            listing("mid", score=75, first_seen=TODAY)]
    assert ids(build(rows, cfg, resolver)["sections"]["new"]) == ["high", "mid", "low"]


def test_seasons_filter(cfg, resolver):
    rows = [listing("s27"), listing("s28", season="Summer 2028"), listing("none", season=None)]
    s = build(rows, with_email(cfg, seasons=["Summer 2028"]), resolver)["sections"]
    assert ids(s["top_open"]) == ["s28"]
    s = build(rows, with_email(cfg, seasons=["Summer 2028", "Not stated"]), resolver)["sections"]
    assert sorted(ids(s["top_open"])) == ["none", "s28"]
    s = build(rows, cfg, resolver)["sections"]  # the shipped "all"
    assert len(s["top_open"]) == 3


def test_areas_filter_by_target_area_and_state(cfg, resolver):
    rows = [listing("dsm"),  # Des Moines, inside the Des Moines metro
            listing("chi", city="Chicago", state="IL", lat=41.8375, lng=-87.6866),
            listing("kc", city="Kansas City", state="MO", lat=39.1251, lng=-94.5503),
            # Coordinates unknown, but the posting names Chicago (D-022's rule)
            listing("chi_unknown", city=None, state=None, lat=None, lng=None, location_raw="Chicago Riverside Plaza")]
    s = build(rows, with_email(cfg, areas=["Chicago metro"]), resolver)["sections"]
    assert sorted(ids(s["top_open"])) == ["chi", "chi_unknown"]
    s = build(rows, with_email(cfg, areas=["IA", "Kansas City metro"]), resolver)["sections"]
    assert sorted(ids(s["top_open"])) == ["dsm", "kc"]
    s = build(rows, cfg, resolver)["sections"]
    assert len(s["top_open"]) == 4


@pytest.mark.parametrize("changes, message", [
    ({"areas": ["Nowhere metro"]}, "email.areas: 'Nowhere metro'"),
    ({"seasons": ["Summer 2099"]}, "email.seasons: 'Summer 2099'"),
    ({"max_new": -1}, "email.max_new"),
    ({"deadline_window_days": "14"}, "email.deadline_window_days"),
    ({"surprise": 1}, "unknown setting 'email.surprise'"),
])
def test_bad_email_settings_are_reported(tmp_path, cities, changes, message):
    raw = yaml.safe_load((ROOT / "config" / "config.yaml").read_text(encoding="utf-8"))
    raw["email"].update(changes)
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ConfigError, match=message.replace("(", r"\(")):
        load_config(path, cities)


def test_no_email_value_is_hard_coded():
    """Every number the email uses comes from config: none of the shipped values appear in the module."""
    source = (ROOT / "scanner" / "email_report.py").read_text(encoding="utf-8")
    shipped = yaml.safe_load((ROOT / "config" / "config.yaml").read_text(encoding="utf-8"))["email"]
    for key in ("min_score", "max_new", "max_top_open", "deadline_window_days"):
        assert f"= {shipped[key]}\n" not in source and f"({shipped[key]})" not in source, key


# ------------------------------------------------------------ deadlines

def test_deadline_window_boundaries(cfg, resolver):
    window = cfg["email"]["deadline_window_days"]
    today = dt.date(2026, 11, 3)  # Chicago's date at NOW
    day = lambda n: (today + dt.timedelta(days=n)).isoformat()
    rows = [listing("yesterday", deadline=day(-1)), listing("today", deadline=day(0)),
            listing("last_day", deadline=day(window)), listing("past_window", deadline=day(window + 1)),
            listing("none", deadline=None), listing("junk", deadline="soon")]
    s = build(rows, cfg, resolver)["sections"]
    assert ids(s["deadlines"]) == ["today", "last_day"]


def test_deadline_window_uses_chicago_dates(cfg, resolver):
    # 03:00 UTC on Nov 4 is still Nov 3 in Ames, so a Nov 3 deadline is "today", not past.
    late = dt.datetime(2026, 11, 4, 3, 0, tzinfo=dt.timezone.utc)
    report = build([listing("d", deadline="2026-11-03")], cfg, resolver, now=late)
    assert ids(report["sections"]["deadlines"]) == ["d"]
    assert report["subject"].endswith("(2026-11-03)")


def test_deadlines_sorted_soonest_first(cfg, resolver):
    rows = [listing("later", deadline="2026-11-10", score=99), listing("sooner", deadline="2026-11-05", score=55)]
    assert ids(build(rows, cfg, resolver)["sections"]["deadlines"]) == ["sooner", "later"]


# ------------------------------------------------------------ remote and manual

def remote_listing(id_="remote", **kw):
    return listing(id_, city=None, state="IA", lat=None, lng=None, tags=["remote_iowa"], label="Remote",
                   location_raw="Iowa - Work From Home", **kw)


def test_remote_iowa_section_only_when_such_listings_exist(cfg, resolver):
    report = build([listing("a")], cfg, resolver)
    assert "Remote — Iowa" not in report["html"] and "Remote — Iowa" not in report["text"]
    report = build([listing("a"), remote_listing()], cfg, resolver)
    assert ids(report["sections"]["remote_iowa"]) == ["remote"]
    assert "Remote — Iowa (1)" in report["html"] and "Remote — Iowa (1)" in report["text"]
    assert "Remote (Iowa)" in report["text"]
    # D-029: it appears only in its own section.
    assert "remote" not in ids(report["sections"]["top_open"]) + ids(report["sections"]["new"])


def test_remote_iowa_section_hidden_when_its_listings_are_not_open_or_below_min_score(cfg, resolver):
    rows = [remote_listing("r1", status="filtered"), remote_listing("r2", score=cfg["email"]["min_score"] - 1)]
    report = build(rows, cfg, resolver)
    assert report["sections"]["remote_iowa"] == []
    assert "Remote — Iowa" not in report["html"]


def test_new_remote_listing_counts_in_subject_and_gets_a_badge(cfg, resolver):
    report = build([remote_listing(first_seen=TODAY)], cfg, resolver)
    assert report["subject"] == "Internships — 1 new (2026-11-03)"
    assert "[NEW]" in report["text"]


def test_manual_links_failed_first_then_by_priority(cfg, resolver):
    report = build([], cfg, resolver)
    assert [m["company"] for m in report["sections"]["manual"]] == ["Broken Bank", "Wells Fargo", "No Link Co"]
    assert "Couldn't be fetched today" in report["html"]
    assert 'href="https://www.wellsfargojobs.com"' in report["html"]


def test_health_line(cfg, resolver):
    line = build([], cfg, resolver)["sections"]["health"]
    assert line.startswith("Source health: 57 of 58 live companies fetched (41 Workday, 15 Greenhouse, 1 Ashby), 1 failed, 2 manual.")
    assert "6:00 AM CST" in line
    assert er.health_line({}) == "Source health: no run summary was found."


# ------------------------------------------------------------ rendering

def test_subject_format():
    assert er.subject_for(3, "2026-11-03") == "Internships — 3 new (2026-11-03)"
    assert er.subject_for(0, "2026-01-09") == "Internships — 0 new (2026-01-09)"


def test_empty_day_still_renders(cfg, resolver):
    report = build([], cfg, resolver, meta={})
    assert report["subject"] == "Internships — 0 new (2026-11-03)"
    for text in (report["html"], report["text"]):
        assert "Nothing new since the last email." in text
        assert "Top open matches (0)" in text
        assert "Source health: no run summary was found." in text
    assert report["html"].startswith("<!DOCTYPE html>") and report["html"].rstrip().endswith("</html>")


def test_each_listing_shows_the_required_fields(cfg, resolver):
    row = listing("x", first_seen=TODAY)
    unknown = listing("u", city=None, state=None, lat=None, lng=None, location_raw="Des Moines HQ", season=None)
    report = build([row, unknown], cfg, resolver)
    text, page = report["text"], report["html"]
    for part in ("Finance Intern x", "Acme Insurance", "Des Moines, IA", "Summer 2027", "Score 80",
                 "+40 role: 'finance intern' in title (corporate_finance)", "+25 season: Summer 2027 (weight 1.0)",
                 "https://boards.greenhouse.io/acme/jobs/x"):
        assert part in text and (part.replace("'", "&#x27;") in page)
    assert "Location unknown" in text and "Season not stated" in text
    # Only the top 2 reasons appear: the +20 location reason ranks third.
    assert "+20 location: Des Moines metro" not in text


def test_html_escapes_titles_and_drops_non_http_links(cfg, resolver):
    row = listing("x", title="<script>alert(1)</script> Intern", apply_url="javascript:alert(1)",
                  sources=[{"source_name": "g", "source_job_id": "x", "url": "javascript:bad"}])
    page = build([row], cfg, resolver)["html"]
    assert "<script>" not in page and "&lt;script&gt;" in page
    assert "javascript:" not in page
    assert "<style" not in page  # Gmail strips <style> blocks, so everything is inline


# ------------------------------------------------------------ new since last email

def test_new_falls_back_to_new_badge_days_without_a_record(cfg, resolver):
    days = cfg["new_badge_days"]
    today = dt.date(2026, 11, 3)
    inside = (today - dt.timedelta(days=days - 1)).isoformat()
    outside = (today - dt.timedelta(days=days)).isoformat()
    s = build([listing("in", first_seen=inside), listing("out", first_seen=outside)], cfg, resolver, meta={})["sections"]
    assert ids(s["new"]) == ["in"]


def test_new_since_the_recorded_send(cfg, resolver):
    meta = {**META, "email": {"last_sent_at": "2026-11-02T12:00:00+00:00", "sent_date": "2026-11-02",
                              "ids_first_seen_on_sent_date": ["already_sent"]}}
    rows = [listing("old", first_seen="2026-11-01"), listing("already_sent", first_seen="2026-11-02"),
            listing("later_same_day", first_seen="2026-11-02"), listing("today", first_seen=TODAY)]
    s = build(rows, cfg, resolver, meta=meta)["sections"]
    assert sorted(ids(s["new"])) == ["later_same_day", "today"]


def test_record_send_holds_ids_and_a_time_only():
    rows = [listing("a", first_seen=TODAY), listing("b", first_seen="2026-11-01")]
    meta = er.record_send({"totals": {}}, rows, NOW)
    assert meta["email"] == {"last_sent_at": "2026-11-03T12:00:00+00:00", "sent_date": TODAY,
                             "ids_first_seen_on_sent_date": ["a"]}
    assert meta["totals"] == {}


# ------------------------------------------------------------ sending (always mocked)

class FakeSMTP:
    instances = []
    fail_with = None

    def __init__(self, host, port, timeout=None):
        self.host, self.port, self.timeout = host, port, timeout
        self.calls = []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.calls.append("quit")
        return False

    def starttls(self, context=None):
        self.calls.append("starttls")
        self.tls_context = context

    def login(self, user, password):
        self.calls.append("login")
        self.user, self.password = user, password
        if FakeSMTP.fail_with:
            raise FakeSMTP.fail_with

    def send_message(self, msg, from_addr=None, to_addrs=None):
        self.calls.append("send")
        self.msg, self.from_addr, self.to_addrs = msg, from_addr, to_addrs


@pytest.fixture
def fake_smtp():
    FakeSMTP.instances, FakeSMTP.fail_with = [], None
    return FakeSMTP


def a_report(cfg, resolver):
    return build([listing("x", first_seen=TODAY)], cfg, resolver)


def test_send_uses_gmail_starttls_and_sends_html_with_text(cfg, resolver, fake_smtp):
    logs = []
    assert er.send(a_report(cfg, resolver), ENV, fake_smtp, logs.append) is True
    smtp = fake_smtp.instances[0]
    assert (smtp.host, smtp.port) == ("smtp.gmail.com", 587)
    assert smtp.calls == ["starttls", "login", "send", "quit"]
    assert smtp.tls_context is not None
    assert smtp.password == "ab12cd34ef56gh78"  # the spaces Google shows aren't part of it
    assert smtp.to_addrs == ["to@example.com"]
    msg = smtp.msg
    assert msg["Subject"] == "Internships — 1 new (2026-11-03)"
    assert msg.get_body(("plain",)) is not None and msg.get_body(("html",)) is not None
    assert not any("ab12" in line for line in logs)


@pytest.mark.parametrize("missing", er.SECRET_NAMES)
def test_missing_secret_skips_without_crashing(cfg, resolver, fake_smtp, missing):
    env = {**ENV, missing: "  "}
    logs = []
    assert er.send(a_report(cfg, resolver), env, fake_smtp, logs.append) is False
    assert fake_smtp.instances == []
    assert len(logs) == 1 and missing in logs[0] and logs[0].startswith("::warning")
    for name, value in ENV.items():
        if name != missing:
            assert value not in logs[0]


def test_missing_secrets_exit_zero_and_leave_meta_alone(workspace5, fake_smtp, capsys):
    before = (workspace5 / "data" / "meta.json").read_bytes()
    code = er.run_email(workspace5 / "config", workspace5 / "data", workspace5 / "outputs", dry_run=False,
                        env={}, smtp_class=fake_smtp, now=NOW)
    assert code == 0
    assert "SMTP_USERNAME, SMTP_APP_PASSWORD, EMAIL_TO" in capsys.readouterr().out
    assert (workspace5 / "data" / "meta.json").read_bytes() == before
    assert fake_smtp.instances == []


def test_smtp_failure_is_reported_without_secrets(workspace5, fake_smtp, capsys):
    fake_smtp.fail_with = smtplib.SMTPAuthenticationError(535, b"bad login for sender@example.com ab12 cd34 ef56 gh78")
    code = er.run_email(workspace5 / "config", workspace5 / "data", workspace5 / "outputs", dry_run=False,
                        env=ENV, smtp_class=fake_smtp, now=NOW)
    out = capsys.readouterr().out
    assert code == 1
    assert "::error" in out and "SMTPAuthenticationError" in out
    for value in ENV.values():
        assert value not in out
    assert "email" not in json.loads((workspace5 / "data" / "meta.json").read_text(encoding="utf-8"))


def test_successful_send_records_the_time_in_meta(workspace5, fake_smtp):
    code = er.run_email(workspace5 / "config", workspace5 / "data", workspace5 / "outputs", dry_run=False,
                        env=ENV, smtp_class=fake_smtp, now=NOW)
    assert code == 0 and len(fake_smtp.instances) == 1
    meta = json.loads((workspace5 / "data" / "meta.json").read_text(encoding="utf-8"))
    assert meta["email"]["last_sent_at"] == "2026-11-03T12:00:00+00:00"
    assert meta["totals"]  # the run's own numbers are kept
    # The next email doesn't repeat what this one called new.
    code = er.run_email(workspace5 / "config", workspace5 / "data", workspace5 / "outputs", dry_run=False,
                        env=ENV, smtp_class=fake_smtp, now=NOW + dt.timedelta(days=1))
    assert fake_smtp.instances[1].msg["Subject"].startswith("Internships — 0 new")


def test_real_smtp_is_never_reached_in_tests(cfg, resolver):
    # The autouse fixture below swaps smtplib.SMTP itself, so even code that forgets to pass a fake
    # can't open a connection (or a DNS lookup). conftest also blocks every socket connect.
    with pytest.raises(AssertionError, match="real SMTP"):
        er.send(a_report(cfg, resolver), ENV)


# ------------------------------------------------------------ dry run, failure email, CLI, pipeline

@pytest.fixture
def workspace5(tmp_path):
    config, data = tmp_path / "config", tmp_path / "data"
    config.mkdir()
    for name in ("config.yaml", "cities.yaml"):
        shutil.copy(ROOT / "config" / name, config / name)
    companies = [{"name": "Wells Fargo", "ats": "manual", "board": "https://www.wellsfargojobs.com",
                  "cities": [], "priority": 1, "notes": "x"}]
    (config / "companies.yaml").write_text(yaml.safe_dump({"companies": companies}), encoding="utf-8")
    store.save_listings(data, [listing("a", first_seen=TODAY, last_seen=TODAY), listing("b", status="filtered", last_seen=TODAY)])
    store.write_json(data / "meta.json", META)
    return tmp_path


def test_dry_run_writes_preview_and_sends_nothing(workspace5, fake_smtp):
    code = er.run_email(workspace5 / "config", workspace5 / "data", workspace5 / "outputs", dry_run=True,
                        env=ENV, smtp_class=fake_smtp, now=NOW)
    assert code == 0 and fake_smtp.instances == []
    page = (workspace5 / "outputs" / "email_preview.html").read_text(encoding="utf-8")
    assert "Finance Intern a" in page and "Finance Intern b" not in page
    assert (workspace5 / "outputs" / "email_preview.txt").exists()
    assert "email" not in json.loads((workspace5 / "data" / "meta.json").read_text(encoding="utf-8"))


def test_cli_dry_run(workspace5, monkeypatch):
    for name in er.SECRET_NAMES:
        monkeypatch.delenv(name, raising=False)
    code = main(["email", "--dry-run", "--config-dir", str(workspace5 / "config"), "--data-dir", str(workspace5 / "data"),
                 "--out-dir", str(workspace5 / "outputs")])
    assert code == 0
    assert (workspace5 / "outputs" / "email_preview.html").exists()


def test_outputs_folder_is_gitignored():
    assert "outputs/" in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()


def test_failure_email(fake_smtp):
    report = er.build_failure_email(NOW, "https://github.com/o/r/actions/runs/1", {"tests": "success", "scan": "failure"})
    assert report["subject"] == "Scan failed (2026-11-03)"
    assert "https://github.com/o/r/actions/runs/1" in report["text"] and 'href="https://github.com/o/r/actions/runs/1"' in report["html"]
    assert "scan: failure" in report["text"] and "tests" not in report["text"]
    assert er.run_failure_email("https://github.com/o/r/actions/runs/1", {}, env=ENV, smtp_class=fake_smtp, now=NOW) == 0
    assert fake_smtp.instances[0].msg["Subject"] == "Scan failed (2026-11-03)"


def test_failure_email_skips_without_secrets(fake_smtp, capsys):
    assert er.run_failure_email(None, {}, env={}, smtp_class=fake_smtp, now=NOW) == 0
    assert fake_smtp.instances == [] and "Missing secret(s)" in capsys.readouterr().out


def test_failure_email_needs_no_config(tmp_path, fake_smtp, monkeypatch):
    # The failure email must work even when config is what broke.
    monkeypatch.chdir(tmp_path)
    assert er.run_failure_email(None, {"tests": "failure"}, env=ENV, smtp_class=fake_smtp, now=NOW) == 0


def test_pipeline_keeps_the_email_record_in_meta(tmp_path):
    from test_pipeline_and_store import client
    config = tmp_path / "config"
    config.mkdir()
    for name in ("config.yaml", "cities.yaml"):
        shutil.copy(ROOT / "config" / name, config / name)
    companies = [{"name": "American Equity", "ats": "greenhouse", "board": "good", "cities": [], "priority": 1, "notes": "x"}]
    (config / "companies.yaml").write_text(yaml.safe_dump({"companies": companies}), encoding="utf-8")
    record = {"last_sent_at": "2026-11-02T12:00:00+00:00", "sent_date": "2026-11-02", "ids_first_seen_on_sent_date": []}
    store.write_json(tmp_path / "data" / "meta.json", {"email": record})
    from scanner.pipeline import run
    meta = run(config, tmp_path / "data", client=client(), now=NOW)
    assert meta["email"] == record
    assert json.loads((tmp_path / "data" / "meta.json").read_text(encoding="utf-8"))["email"] == record


# ------------------------------------------------------------ workflow and secrets

def workflow():
    return yaml.safe_load((ROOT / ".github" / "workflows" / "scan.yml").read_text(encoding="utf-8"))


def test_secrets_reach_only_the_email_steps():
    steps = workflow()["jobs"]["scan"]["steps"]
    text = (ROOT / ".github" / "workflows" / "scan.yml").read_text(encoding="utf-8")
    assert "env:" not in text.split("jobs:")[0]  # no workflow-wide env
    for step in steps:
        env = step.get("env") or {}
        has_secrets = any("secrets." in str(v) for v in env.values())
        is_email = "scanner email" in step.get("run", "")
        assert has_secrets == is_email, step.get("name")
        assert "secrets." not in step.get("run", ""), step.get("name")  # never in a command line
        if is_email:
            assert {k for k, v in env.items() if "secrets." in str(v)} == set(er.SECRET_NAMES)


def test_failure_email_step_runs_on_failure_and_commit_survives_an_email_error():
    steps = {s.get("id"): s for s in workflow()["jobs"]["scan"]["steps"]}
    assert steps["failure_email"]["if"] == "failure()"
    assert "--failure" in steps["failure_email"]["run"]
    assert "steps.scan.outcome == 'success'" in steps["commit"]["if"]
    order = [s.get("id") for s in workflow()["jobs"]["scan"]["steps"]]
    assert order.index("scan") < order.index("email") < order.index("commit") < order.index("failure_email")


def test_no_secret_values_or_addresses_in_tracked_text_files():
    import re
    import subprocess
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    email = re.compile(r"[A-Za-z0-9._%+-]+@(gmail|yahoo|outlook|hotmail|icloud)\.com", re.I)
    # A secret may only ever be filled from GitHub's secrets, never written out.
    assigned = re.compile(r"\b(SMTP_USERNAME|SMTP_APP_PASSWORD|EMAIL_TO)\s*[:=]\s*(?![\s$]|\$\{\{\s*secrets\.)[\"']?[^\s\"',)]+")
    for name in files:
        path = ROOT / name
        if path.suffix in {".txt", ".json"} and "reference" in name:
            continue  # the Census file is large and holds place names only
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue
        assert not email.search(text), name
        if name != "tests/test_phase5.py":  # the fake values above are example.com and test-only
            assert not assigned.search(text), (name, assigned.search(text))
