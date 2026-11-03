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

remote: "separate"               # include | exclude | separate (D-029)
remote_allowed_states: ["IA"]    # "separate" keeps remote jobs tied to these states, tagged remote_iowa

seasons:
  - { name: "Summer 2027",          weight: 1.0 }
  - { name: "Summer 2028",          weight: 1.0 }
  - { name: "Early-career program", weight: 1.0 }
  - { name: "Fall 2027",            weight: 0.8 }
  - { name: "Winter 2028",          weight: 0.8 }
  - { name: "Spring 2028",          weight: 0.8 }
  - { name: "Spring 2027",          weight: 0.6, max_miles_from_home: 60 }   # D-016
  - { name: "Winter 2027",          weight: 0.6, max_miles_from_home: 60 }   # D-016

role_categories:
  investment_banking: ["investment banking", "summer analyst", "M&A", "capital markets"]
  corporate_finance:  ["finance intern", "financial analyst intern", "FP&A", "treasury", "corporate finance"]
  # P5.1: "credit risk" and "market risk" are bank roles. banking is listed before insurance_risk,
  # so "Credit Risk Intern" gets role_category banking and the email doesn't hide it (D-034).
  banking:            ["commercial banking", "credit analyst", "retail banking", "treasury management", "banking intern",
                       "credit risk", "market risk"]
  investments:        ["investment analyst", "equity research", "asset management", "wealth management", "financial advisor intern", "private wealth"]
  accounting:         ["accounting intern", "audit intern", "tax intern", "assurance", "advisory intern"]
  insurance_risk:     ["actuarial", "underwriting", "risk intern", "risk management", "claims analyst intern",
                       "claims adjuster", "claims", "underwriting intern"]
  early_career:       ["sophomore", "freshman", "insight", "discovery", "early career", "rotational intern", "leadership program"]

must_be_one_of: ["intern", "internship", "summer analyst", "co-op", "insight", "discovery", "early career program"]

# D-018: a title without one of those terms still counts if it has a season and year
# (e.g. "Summer 2027") plus one of these words.
program_title_terms: ["analyst", "program", "associate program", "scholar"]

exclude_keywords: ["senior", "director", "vice president", "manager", "PhD", "MBA", "graduate degree",
                   "master's", "full-time analyst", "experienced", "CPA required"]

# P5.1: a title with one of these is kept only within radius_miles of home, where a student could
# work during the school year. Elsewhere it becomes "filtered" (D-024). "part-time" also matches "part time".
exclude_keywords_outside_home: ["part-time", "term-time"]

eligibility:
  exclude_if_restricted_to_grad_years: [2027, 2028]   # season year ≠ class year; see SPEC

status:
  possibly_closed_after_missed_runs: 2
  closed_after_missed_runs: 5
  empty_response_min_open: 3     # 0 jobs from a company that had this many open = a failed fetch
new_badge_days: 3

scoring:                         # D-020: every point value lives here
  role_in_title: 40
  role_only_in_description: -10
  no_role_signal: -15
  target_area: 20
  whole_state_or_home_radius: 10
  location_unknown: 0
  season_max: 25                 # multiplied by the season's weight
  season_not_stated: 8
  eligible: 10
  eligibility_unclear: 0
  ineligible: -50
  early_career: 5
  no_role_cap: 35                # D-021: no role-category match can never score above this
  max_score: 100
  # P5.1: off-target words in the title, as whole words. Not applied when the title matches one of
  # title_penalty_exempt_categories, so "Technology Investment Banking Summer Analyst" keeps its score.
  title_penalty_keywords: { technology: -30, marketing: -30 }
  title_penalty_exempt_categories: ["investment_banking"]

workday:                         # D-002
  search_terms: ["intern", "internship", "summer analyst", "summer program"]
  page_size: 20
  max_results_per_term: 500      # D-025: stop here per company and search term

geocoding:
  # Off (D-022): coordinates come from the Census Gazetteer in data/reference/.
  enabled: false
  min_seconds_between_requests: 15   # the usage policy caps scheduled scripts at 4 per minute
  max_lookups_per_run: 50

email:
  min_score: 50
  max_new: 25
  max_top_open: 10
  deadline_window_days: 14
  areas: "all"
  seasons: "all"
  max_manual: 10                 # P5.1 (D-033): manual links shown; the rest become "...and N more"
  # D-034: hide a listing whose title matches only these role categories. It stays in the data.
  exclude_role_categories: ["insurance_risk"]

contacts:
  daily_candidates: 15
  monthly_reveal_budget: 150
  daily_reveal_cap: 5
  priority: ["isu_alumni", "campus_recruiter", "hiring_team"]
  school_name_for_alumni: "Iowa State University"
```

## The `email:` block (Phase 5)
No values changed in P5. This is what each setting means, as `scanner/email_report.py` reads it:
- Only listings with `status: open` are considered, before anything else (D-024).
- `min_score`: a listing needs at least this score, the value included.
- `max_new`: the most listings shown under "New since last email". The subject still counts every new one, and the email says how many more there were.
- `max_top_open`: the most listings under "Top open matches". Listings already shown under "New" aren't repeated there.
- `deadline_window_days`: "Deadlines" shows stated deadlines from today through today plus this many days, both included, by the Central-time date.
- `areas`: `"all"`, or a list of `target_areas` names and/or two-letter state codes, e.g. `["Des Moines metro", "IA"]`. A listing without coordinates matches a target area when its posted location names the area's center city. Remote listings tied to Iowa (D-029) have their own section and skip this filter.
- `seasons`: `"all"`, or a list of names from `seasons`. Add `"Not stated"` to keep listings that give no season, which is most of them. A title with a year but no season word, such as "2028 Audit or Tax Intern", is "Not stated" too; the email shows it as "2028 · season not stated".
- "New" means first seen since the last successful send. Before the first send, it means first seen within `new_badge_days`.
- `max_manual` (P5.1, D-033): the most companies listed under "Check these manually". Companies whose fetch failed today come first, then priority 1, 2 and 3, alphabetical within each group. The rest are summed up as "…and N more manual companies." `0` shows only that line.
- `exclude_role_categories` (P5.1, D-034): names from `role_categories`. A listing whose **title** matches only these categories is left out of the email; one more match outside the list keeps it in. `early_career` doesn't count as a match here, because it marks a program's level, not a role. A title with no category match isn't affected (`min_score` and `no_role_cap` handle those). Hidden listings stay in `data/internships.json` with their scores, and the source-health line says how many were hidden. `[]` turns this off.

A bad value stops the email with a message saying what to fix.

## Other settings added in P5.1
- `role_categories.banking` gains `"credit risk"` and `"market risk"`. Because `banking` comes before `insurance_risk`, "Credit Risk Intern" gets `role_category: banking` and isn't hidden by `exclude_role_categories`.
- `exclude_keywords_outside_home`: title words for jobs that only make sense near campus. A listing whose title has one, as a whole word, with a hyphen or a space ("part-time", "Part Time"), is kept only within `radius_miles` of home. A multi-city posting counts by its closest city; an unknown distance doesn't pass; a remote job is exempt, since there's no commute. Elsewhere, a listing already stored becomes `filtered` with the reason, and a new one isn't stored. `[]` turns this off.
- `scoring.title_penalty_keywords`: title words, matched as whole words, and the points each adds (negative to lower a score). Each one adds a match reason such as "-30 title: 'marketing' is off-target". The 0 to `max_score` bounds and `no_role_cap` still apply afterwards.
- `scoring.title_penalty_exempt_categories`: `role_categories` names whose titles never get those penalties, so "2027 Technology Investment Banking Summer Analyst" keeps its score.
