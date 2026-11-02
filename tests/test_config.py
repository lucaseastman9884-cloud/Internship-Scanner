import re

import pytest
import yaml

from scanner.config import ConfigError, company_id, load_companies, load_config
from conftest import ROOT


def write_config(tmp_path, change):
    data = yaml.safe_load((ROOT / "config" / "config.yaml").read_text(encoding="utf-8"))
    change(data)
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def test_config_matches_the_doc_exactly():
    doc = (ROOT / "docs" / "CONFIG.md").read_text(encoding="utf-8")
    block = re.search(r"```yaml\n(.*?)```", doc, re.S).group(1)
    assert (ROOT / "config" / "config.yaml").read_text(encoding="utf-8") == block


def test_season_weights_match_d014(cfg):
    weights = {s["name"]: s["weight"] for s in cfg["seasons"]}
    assert weights == {
        "Summer 2027": 1.0, "Summer 2028": 1.0, "Early-career program": 1.0,
        "Fall 2027": 0.8, "Winter 2028": 0.8, "Spring 2028": 0.8,
        "Spring 2027": 0.6, "Winter 2027": 0.6,
    }


def test_real_registry_loads():
    companies = load_companies(ROOT / "config" / "companies.yaml")
    assert len(companies) >= 43
    assert "BGM Group" not in {c["name"] for c in companies}  # D-019


@pytest.mark.parametrize("change, expected", [
    (lambda d: d.update(remote="sometimes"), "remote must be one of"),
    (lambda d: d.update(seasons=["Summer 2027"]), "must have exactly name and weight"),
    (lambda d: d["seasons"][0].update(weight=1.5), "weight must be a number from 0 to 1"),
    (lambda d: d["seasons"][0].update(name="Summer"), "must look like 'Summer 2027'"),
    (lambda d: d.update(typo_setting=1), "unknown setting 'typo_setting'"),
    (lambda d: d.pop("radius_miles"), "missing setting 'radius_miles'"),
    (lambda d: d["profile"].update(grad_date="May 2029"), "grad_date"),
    (lambda d: d["target_areas"][0].update(center="Atlantis, IA"), "Atlantis"),
])
def test_bad_config_gives_a_clear_message(tmp_path, cities, change, expected):
    with pytest.raises(ConfigError) as err:
        load_config(write_config(tmp_path, change), cities)
    assert expected in str(err.value)


def test_all_config_problems_are_reported_together(tmp_path, cities):
    def change(d):
        d["remote"] = "sometimes"
        d["radius_miles"] = "far"
    with pytest.raises(ConfigError) as err:
        load_config(write_config(tmp_path, change), cities)
    assert "2 problem(s)" in str(err.value)


def test_invalid_yaml_is_reported(tmp_path, cities):
    path = tmp_path / "config.yaml"
    path.write_text("remote: [unclosed", encoding="utf-8")
    with pytest.raises(ConfigError, match="not valid YAML"):
        load_config(path, cities)


@pytest.mark.parametrize("entry, expected", [
    ({"ats": "taleo"}, "must be one of"),
    ({"ats": "workday", "board": "acme"}, "workday board must be"),
    ({"ats": "greenhouse", "board": "has spaces"}, "slug with no spaces"),
    ({"ats": "manual", "board": "not-a-url"}, "manual board must be"),
    ({"priority": 9}, "priority must be"),
    ({"notes": ""}, "notes must not be empty"),
])
def test_bad_company_gives_a_clear_message(tmp_path, entry, expected):
    company = {"name": "Acme", "ats": "greenhouse", "board": "acme", "cities": [], "priority": 1, "notes": "x"}
    company.update(entry)
    path = tmp_path / "companies.yaml"
    path.write_text(yaml.safe_dump({"companies": [company]}), encoding="utf-8")
    with pytest.raises(ConfigError) as err:
        load_companies(path)
    assert expected in str(err.value)


def test_duplicate_company_is_rejected(tmp_path):
    company = {"name": "Acme", "ats": "manual", "board": None, "cities": [], "priority": 1, "notes": "x"}
    path = tmp_path / "companies.yaml"
    path.write_text(yaml.safe_dump({"companies": [company, company]}), encoding="utf-8")
    with pytest.raises(ConfigError, match="duplicate"):
        load_companies(path)


def test_company_id_is_a_stable_slug():
    assert company_id("Cottingham & Butler") == "cottingham-butler"
