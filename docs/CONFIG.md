# CONFIG — Lucas's settings (accepted 2026-11-02; Lucas may change any value)
Phase 1 copies this into `config/config.yaml`. No value may be hard-coded elsewhere.
Never put personal details (phone, email, resume) in config — the repo is public. Lucas's email goes in a GitHub secret.

```yaml
profile:
  grad_date: "2029-05"
  degree: "B.S. Finance and Accounting, minor in AI"
  school: "Iowa State University"

home: { city: "Ames", state: "IA" }
radius_miles: 150

target_areas:                    # always included regardless of distance
  - { name: "Des Moines metro",  center: "Des Moines, IA",  radius_miles: 25 }
  - { name: "Dubuque",           center: "Dubuque, IA",     radius_miles: 20 }
  - { name: "Kansas City metro", center: "Kansas City, MO", radius_miles: 30 }
  - { name: "Chicago metro",     center: "Chicago, IL",     radius_miles: 30 }
include_whole_states: ["IA"]

remote: "exclude"                # include | exclude | separate

seasons:
  - { name: "Summer 2027",          weight: 1.0 }
  - { name: "Summer 2028",          weight: 1.0 }
  - { name: "Early-career program", weight: 1.0 }
  - { name: "Fall 2027",            weight: 0.8 }
  - { name: "Winter 2028",          weight: 0.8 }
  - { name: "Spring 2028",          weight: 0.8 }
  - { name: "Spring 2027",          weight: 0.6 }
  - { name: "Winter 2027",          weight: 0.6 }

role_categories:
  investment_banking: ["investment banking", "summer analyst", "M&A", "capital markets"]
  corporate_finance:  ["finance intern", "financial analyst intern", "FP&A", "treasury", "corporate finance"]
  banking:            ["commercial banking", "credit analyst", "retail banking", "treasury management", "banking intern"]
  investments:        ["investment analyst", "equity research", "asset management", "wealth management", "financial advisor intern", "private wealth"]
  accounting:         ["accounting intern", "audit intern", "tax intern", "assurance", "advisory intern"]
  insurance_risk:     ["actuarial", "underwriting", "risk intern", "risk management", "claims analyst intern"]
  early_career:       ["sophomore", "freshman", "insight", "discovery", "early career", "rotational intern", "leadership program"]

must_be_one_of: ["intern", "internship", "summer analyst", "co-op", "insight", "discovery", "early career program"]

exclude_keywords: ["senior", "director", "vice president", "manager", "PhD", "MBA", "graduate degree",
                   "master's", "full-time analyst", "experienced", "CPA required"]

eligibility:
  exclude_if_restricted_to_grad_years: [2027, 2028]   # season year ≠ class year; see SPEC

status:
  possibly_closed_after_missed_runs: 2
  closed_after_missed_runs: 5
new_badge_days: 3

email:
  min_score: 50
  max_new: 25
  max_top_open: 10
  deadline_window_days: 14
  areas: "all"
  seasons: "all"

contacts:
  daily_candidates: 15
  monthly_reveal_budget: 150
  daily_reveal_cap: 5
  priority: ["isu_alumni", "campus_recruiter", "hiring_team"]
  school_name_for_alumni: "Iowa State University"
```
