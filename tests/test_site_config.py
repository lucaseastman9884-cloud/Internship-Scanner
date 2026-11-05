"""P7: site_config.json holds display values only, and the staged site has what the app fetches."""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build_site_config  # noqa: E402
import stage_site  # noqa: E402

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def site_cfg(cfg, cities):
    return build_site_config.build(cfg, cities, NOW)


def test_values_come_from_config(site_cfg, cfg):
    assert site_cfg["schema_version"] == 1
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


def test_main_writes_file(tmp_path):
    out = tmp_path / "nested" / "site_config.json"
    assert build_site_config.main([str(out)]) == 0
    assert json.loads(out.read_text())["schema_version"] == 1


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


def test_stage_refuses_repo_folders():
    with pytest.raises(SystemExit):
        stage_site.stage(ROOT / "site")
