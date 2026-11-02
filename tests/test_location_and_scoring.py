import pytest

from scanner import scoring
from scanner.normalize import new_listing

COMPANY = {"company_id": "acme", "name": "Acme", "board": "acme", "ats": "greenhouse"}


@pytest.mark.parametrize("raw, tier, city", [
    ("Des Moines, Iowa, United States", "target_area", "Des Moines"),
    ("West Des Moines, IA", "target_area", "West Des Moines"),
    ("Dubuque, Iowa, United States", "target_area", "Dubuque"),
    ("Chicago, IL, United States", "target_area", "Chicago"),
    ("Kansas City, Missouri", "target_area", "Kansas City"),
    ("Overland Park, KS", "target_area", "Overland Park"),
    ("Warrenville, IL", "target_area", "Warrenville"),
    ("Waukee", "target_area", "Waukee"),
    ("Bettendorf, IA", "whole_state", "Bettendorf"),
    ("Tinytown, Iowa", "whole_state", "Tinytown"),
    ("Iowa", "whole_state", None),
    ("Omaha, NE", "home_radius", "Omaha"),
    ("Des Moines, IA 50309", "target_area", "Des Moines"),
    ("Dallas, Texas, United States", None, "Dallas"),
    ("New York, New York", None, "New York"),
    ("Shanghai, China", None, "Shanghai"),
    ("Minneapolis, MN", None, "Minneapolis"),
    ("", None, None),
])
def test_location_tiers(resolver, raw, tier, city):
    place = resolver.resolve(raw)
    assert place["tier"] == tier
    assert place["city"] == city


def test_any_qualifying_city_counts_in_a_multi_city_posting(resolver):
    place = resolver.resolve("Atlanta, Georgia; Chicago, Illinois, United States")
    assert place["city"] == "Chicago" and place["tier"] == "target_area"


def test_radius_comes_from_config(cfg, cities):
    from scanner.location import LocationResolver
    narrow = {**cfg, "radius_miles": 10}
    assert LocationResolver(narrow, cities).resolve("Omaha, NE")["tier"] is None


@pytest.mark.parametrize("raw, hint, expected", [
    ("Remote", False, True),
    ("Remote - European Union", False, True),
    ("Chicago, IL", True, True),
    ("Chicago, IL", False, False),
    ("Chicago, IL; Remote", False, False),
])
def test_remote_detection(resolver, raw, hint, expected):
    assert resolver.resolve(raw, hint)["is_remote"] is expected


def scored(cfg, resolver, title, location, season, status, description=""):
    listing = new_listing(COMPANY, "greenhouse", "1", title, location, "https://example.com", description=description)
    listing["season"] = season
    listing["eligibility"] = {"status": status, "reason": "test"}
    return scoring.score(listing, resolver.resolve(location), cfg)


def test_best_case_scores_high_with_reasons(cfg, resolver):
    value, reasons = scored(cfg, resolver, "Tax Intern - Summer 2027", "Chicago, IL", "Summer 2027", "eligible")
    assert value == 95
    assert any(r.startswith("+40 role: 'tax intern'") for r in reasons)
    assert "+20 location: Chicago metro" in reasons
    assert any(r.startswith("+25 season: Summer 2027") for r in reasons)
    assert "+10 eligibility: eligible" in reasons


def test_every_point_has_a_reason(cfg, resolver):
    value, reasons = scored(cfg, resolver, "Sophomore Insight Program", "Ames, IA", "Early-career program", "unclear")
    assert sum(int(r.split()[0]) for r in reasons) == value


def test_season_weights_order_the_scores(cfg, resolver):
    def for_season(season):
        return scored(cfg, resolver, "Tax Intern", "Des Moines, IA", season, "eligible")[0]
    assert for_season("Summer 2027") == for_season("Summer 2028")
    assert for_season("Summer 2028") > for_season("Fall 2027") > for_season("Spring 2027")
    assert for_season("Fall 2027") == for_season("Spring 2028")
    assert for_season("Winter 2027") == for_season("Spring 2027")


def test_non_finance_interns_fall_below_the_email_threshold(cfg, resolver):
    threshold = cfg["email"]["min_score"]
    value, _ = scored(cfg, resolver, "2027 Summer Sales Internship", "Dubuque, IA", "Summer 2027", "eligible")
    assert value < threshold


def test_boilerplate_role_words_do_not_reach_the_threshold(cfg, resolver):
    threshold = cfg["email"]["min_score"]
    value, reasons = scored(cfg, resolver, "IT Intern, SAP Security", "Des Moines, IA", "Summer 2027", "eligible",
                            description="We are a leader in asset management.")
    assert value < threshold
    assert any("only in description" in r for r in reasons)


def test_ineligible_scores_low_and_never_below_zero(cfg, resolver):
    value, reasons = scored(cfg, resolver, "IT Intern", "Dallas, TX", "Summer 2029", "ineligible")
    assert value == 0
    assert "-50 eligibility: ineligible" in reasons
    assert any("score limited" in r for r in reasons)
