"""P7/P8: site_config.json holds display values only, and the staged site has what the app fetches.

Site tests: the Daily scan doesn't run these (see tests/site/conftest.py); Deploy site does.
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build_site_config  # noqa: E402
import stage_site  # noqa: E402

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def site_cfg(cfg, cities):
    return build_site_config.build(cfg, cities, NOW)


def test_values_come_from_config(site_cfg, cfg):
    assert site_cfg["schema_version"] == build_site_config.SCHEMA_VERSION
    assert site_cfg["generated_at"] == "2026-11-04T12:00:00+00:00"
    assert site_cfg["home"]["name"] == f"{cfg['home']['city']}, {cfg['home']['state']}"
    assert site_cfg["home"]["lat"] == pytest.approx(42.0257, abs=0.01)  # Ames, from the Gazetteer
    assert site_cfg["home"]["lng"] == pytest.approx(-93.6225, abs=0.01)
    assert site_cfg["radius_miles"] == cfg["radius_miles"]
    assert [a["name"] for a in site_cfg["target_areas"]] == [a["name"] for a in cfg["target_areas"]]
    for area in site_cfg["target_areas"]:
        assert set(area) == {"name", "center", "lat", "lng", "radius_miles"}
    assert site_cfg["seasons"] == [s["name"] for s in cfg["seasons"]] + ["Not stated"]
    assert site_cfg["role_categories"] == list(cfg["role_categories"])
    assert site_cfg["new_badge_days"] == cfg["new_badge_days"]
    assert site_cfg["remote_sections"] == [{"tag": "remote_iowa", "label": "Remote — Iowa"}]
    assert "IA" in site_cfg["state_codes"]


def test_nothing_private_or_internal(site_cfg, cfg):
    assert set(site_cfg) == {"schema_version", "generated_at", "home", "radius_miles", "target_areas", "seasons",
                             "role_categories", "new_badge_days", "remote_sections", "state_codes"}
    text = json.dumps(site_cfg)
    # No keyword lists, scoring points, profile or contacts settings.
    for keyword in cfg["role_categories"]["investment_banking"] + cfg["exclude_keywords"]:
        assert keyword not in text
    for leaked in ("scoring", "profile", "contacts", "grad_date", "Iowa State", "email", "min_score"):
        assert leaked not in text
    assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text)


def test_no_remote_section_unless_separate(cfg, cities):
    out = build_site_config.build({**cfg, "remote": "exclude"}, cities, NOW)
    assert out["remote_sections"] == []


def test_unknown_target_area_city_is_skipped_with_a_warning(cfg, cities, tmp_path, capsys):
    """P8 follow-up: a place missing from the Gazetteer never stops the build."""
    bad = {**cfg, "target_areas": cfg["target_areas"] + [
        {"name": "Nowhere metro", "center": "Notacity, ZZ", "radius_miles": 10}]}
    warnings = []
    out = build_site_config.build(bad, cities, NOW, warnings=warnings)
    assert [a["name"] for a in out["target_areas"]] == [a["name"] for a in cfg["target_areas"]]
    assert len(warnings) == 1 and "Nowhere metro" in warnings[0]
    assert "::warning" in capsys.readouterr().err
    # The result is still a complete, valid file.
    path = tmp_path / "site_config.json"
    path.write_text(json.dumps(out))
    assert json.loads(path.read_text())["schema_version"] == build_site_config.SCHEMA_VERSION


def test_unknown_home_city_is_skipped_with_a_warning(cfg, cities):
    warnings = []
    out = build_site_config.build({**cfg, "home": {"city": "Notacity", "state": "ZZ"}}, cities, NOW, warnings=warnings)
    assert out["home"] == {"name": "Notacity, ZZ", "lat": None, "lng": None}
    assert len(warnings) == 1 and "home" in warnings[0]


def test_unknown_city_through_main_still_writes_the_file(tmp_path, monkeypatch, cfg):
    """The real command, with a config whose new target area isn't in the Gazetteer: exit 0, file written."""
    bad = {**cfg, "target_areas": cfg["target_areas"] + [
        {"name": "Nowhere metro", "center": "Notacity, ZZ", "radius_miles": 10}]}
    monkeypatch.setattr(build_site_config, "load_config", lambda path, cities: bad)
    out = tmp_path / "site_config.json"
    assert build_site_config.main([str(out)]) == 0
    assert "Nowhere metro" not in out.read_text()
    assert json.loads(out.read_text())["home"]["name"] == "Ames, IA"


def test_last_scan_ran_is_written_only_when_it_is_a_real_time(cfg, cities):
    out = build_site_config.build(cfg, cities, NOW, last_scan_ran="2026-11-05T12:53:40Z")
    assert out["last_scan_ran"] == "2026-11-05T12:53:40+00:00"
    for bad in (None, "", "   ", "yesterday", "2026-11-05", "2026-11-05T12:53:40"):  # no zone = can't be trusted
        warnings = []
        assert "last_scan_ran" not in build_site_config.build(cfg, cities, NOW, last_scan_ran=bad, warnings=warnings)


def test_main_writes_file(tmp_path):
    out = tmp_path / "nested" / "site_config.json"
    assert build_site_config.main([str(out)]) == 0
    data = json.loads(out.read_text())
    assert data["schema_version"] == build_site_config.SCHEMA_VERSION
    assert "last_scan_ran" not in data
    assert build_site_config.main([str(out), "--last-scan-ran", "2026-11-05T12:53:40Z"]) == 0
    assert json.loads(out.read_text())["last_scan_ran"] == "2026-11-05T12:53:40+00:00"


def test_stage_builds_the_pages_folder(tmp_path):
    out = tmp_path / "_site"
    stamp = stage_site.stage(out)
    for path in ("index.html", "manifest.webmanifest", "service-worker.js", "styles.css", "js/app.js",
                 "icons/icon-192.png", "icons/icon-512.png", "icons/maskable-512.png", "site_config.json",
                 "data/internships.json", "data/meta.json", "data/companies_status.json"):
        assert (out / path).is_file(), path
    worker = (out / "service-worker.js").read_text()
    assert stage_site.STAMP not in worker and stamp in worker
    # Nothing else from data/ is published: last_seen, geocache and the local debug file stay out.
    assert sorted(p.name for p in (out / "data").iterdir()) == sorted(stage_site.DATA_FILES)
    # The service worker precaches every app file it names.
    for rel in re.findall(r'"\./([^"]+)"', worker):
        assert (out / rel).is_file(), rel
    # Same app files give the same stamp, so data-only deploys don't force an app update.
    assert stage_site.stage(tmp_path / "_site2") == stamp


def test_stage_passes_the_scan_time_through(tmp_path):
    stage_site.stage(tmp_path / "a", "2026-11-05T12:53:40Z")
    assert json.loads((tmp_path / "a" / "site_config.json").read_text())["last_scan_ran"] == "2026-11-05T12:53:40+00:00"
    assert stage_site.main([str(tmp_path / "b"), "--last-scan-ran", ""]) == 0  # the lookup failed: left out
    assert "last_scan_ran" not in json.loads((tmp_path / "b" / "site_config.json").read_text())


def test_stage_refuses_repo_folders():
    with pytest.raises(SystemExit):
        stage_site.stage(ROOT / "site")
