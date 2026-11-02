"""Titles here are real ones seen on live boards in Phase 1, unless a comment says otherwise."""
import pytest

from scanner import eligibility, filtering
from scanner.normalize import detect_season, find_deadline, role_match
from scanner.text import has_phrase


@pytest.mark.parametrize("title, expected", [
    ("International Tax Senior", False),
    ("Internal Controls Manager", False),
    ("Internal Audit Intern", True),
    ("Internal Wholesaler", False),
    ("Director, Internal Sales", False),
    ("Technical Director - International Tax Services (ITS)", False),
    ("Agent(e) des ventes internes", False),
    ("Accounting Intern", True),
    ("Intern-Claims", True),
    ("Intern - Fast Track Claims", True),
    ("2027 Summer Claims Adjuster Internship", True),
    ("Wintrust 2027 Summer Internship: Legal", True),
    ("Summer 2027 Intern - Accounting Majors", True),
    ("2028 Summer Analyst", True),
    ("Working in Technology (WiT) Data Science - Summer 2027", False),
])
def test_internship_word_boundaries(cfg, title, expected):
    assert filtering.is_internship(title, cfg) is expected


def test_excluded_words_match_whole_words_only():
    assert has_phrase("Senior Accountant", "senior")
    assert not has_phrase("Seniority Program Intern", "senior")
    assert has_phrase("M&A Summer Analyst", "M&A")


def test_excluded_keyword_in_title(cfg):
    assert filtering.title_exclude_keyword("International Tax Senior", cfg) == "senior"
    assert filtering.title_exclude_keyword("Internal Controls Manager", cfg) == "manager"
    assert filtering.title_exclude_keyword("Internal Audit Intern", cfg) is None


def test_rising_senior_is_a_class_not_a_job_level(cfg):
    assert filtering.title_exclude_keyword("Rising Senior Summer Analyst", cfg) is None


def test_level_words_in_a_description_do_not_exclude(cfg):
    text = "You must report to a senior manager and the director of tax."
    assert filtering.description_exclude_keyword(text, cfg) is None


def test_stated_degree_requirement_excludes(cfg):
    assert filtering.description_exclude_keyword("An MBA is required for this role.", cfg) == "MBA"
    assert filtering.description_exclude_keyword("CPA required.", cfg) == "CPA required"


def test_credential_mentions_that_allow_undergrads_do_not_exclude(cfg):
    assert filtering.description_exclude_keyword("Must be pursuing a bachelor's or master's degree.", cfg) is None
    assert filtering.description_exclude_keyword("Many of our leaders hold an MBA.", cfg) is None


@pytest.mark.parametrize("title, description, expected", [
    ("2028 Summer Analyst", "", "eligible"),
    ("Summer 2029 Intern", "", "ineligible"),
    ("Fall 2029 Intern", "", "ineligible"),
    ("Summer Analyst", "Candidates graduating 2027 or 2028 only.", "ineligible"),
    ("Summer 2028 Analyst", "Must be graduating in 2028.", "ineligible"),
    ("Accounting Intern", "", "unclear"),
    ("Summer Analyst", "Students graduating in 2028 have enjoyed this program.", "unclear"),
    ("Summer 2028 Analyst", "Open to students graduating 2028 or 2029 only.", "eligible"),
    ("Summer 2028 Analyst", "Graduation between December 2028 and May 2029 is required.", "eligible"),
    ("Summer 2027 Analyst", "This program is for rising seniors.", "ineligible"),
    ("Summer 2028 Analyst", "This program is for rising seniors.", "eligible"),
    ("Summer 2028 Analyst", "This program is for rising juniors.", "ineligible"),
    ("Sophomore Insight Program", "", "unclear"),
])
def test_eligibility(cfg, title, description, expected):
    season, _ = detect_season(title, description, cfg)
    assert eligibility.evaluate(title, description, season, cfg)["status"] == expected


def test_eligibility_always_gives_a_reason(cfg):
    result = eligibility.evaluate("Summer Analyst", "Graduating 2027 or 2028 only.", None, cfg)
    assert "2027 or 2028" in result["reason"]


@pytest.mark.parametrize("title, description, expected", [
    ("2027 Summer Claims Adjuster Internship", "", "Summer 2027"),
    ("Tax Intern: Spring 2027", "", "Spring 2027"),
    ("2027 Tax Winter Internship - Quad Cities", "", "Winter 2027"),
    ("Internal Operations Intern - Winter 2027 - Kansas City", "", "Winter 2027"),
    ("Intern - Commercial Payments (Summer 2027)", "", "Summer 2027"),
    ("Summer Analyst 2028", "", "Summer 2028"),
    ("Accounting Intern", "Join our Summer 2027 program.", "Summer 2027"),
    ("Accounting Intern", "Classes begin Fall 2026.", None),
    ("Accounting Intern", "", None),
    ("Sophomore Discovery Program", "", "Early-career program"),
    ("Summer 2028 Early Career Program", "", "Summer 2028"),
])
def test_season_detection(cfg, title, description, expected):
    assert detect_season(title, description, cfg)[0] == expected


@pytest.mark.parametrize("title, expected", [
    ("Accounting Intern", "accounting"),
    ("Tax Intern - Summer 2027", "accounting"),
    ("2027 Summer Tax Internship - West Des Moines", "accounting"),
    ("Summer 2027 Intern - Accounting Majors", "accounting"),
    ("Intern - Commercial Payments (Summer 2027)", None),
    ("2027 Summer Intern - Commercial Banking", "banking"),
    ("Wintrust 2027 Summer Internship: Wealth Management", "investments"),
    ("2027 Summer Intern  Equity Research (Buy Side)", "investments"),
    ("2028 Summer Analyst", "investment_banking"),
    ("IT Intern, SAP Security", None),
    ("Sophomore Insight Program", "early_career"),
])
def test_role_category(cfg, title, expected):
    assert role_match(title, cfg)["category"] == expected


def test_deadline_is_read_only_when_explicit():
    assert find_deadline("Application deadline: March 1, 2027.") == "2027-03-01"
    assert find_deadline("Apply by Feb. 15, 2027") == "2027-02-15"
    assert find_deadline("The program begins March 1, 2027.") is None
