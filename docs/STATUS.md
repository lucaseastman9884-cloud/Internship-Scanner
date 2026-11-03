# STATUS — Current state (updated 2026-11-03)

## Phase
P0 — Setup: DONE.
P1 — Plan: DONE and approved.
P2 — Pipeline core: DONE and merged to main.
P3 — Full pipeline: DONE and merged to main.
P4 — Automation: DONE and merged to main (PR #4). The first GitHub run, started by hand, succeeded on 2026-11-03.
P5 — Morning email: merged to main (PR #5). Whether a real email has arrived is **not confirmed** in the repo.
P5.1 — Email polish: built on branch `p5.1-email-polish`, **not pushed, awaiting Lucas's approval**. Tested offline only. Report: docs/reports/P5_1_REPORT.md.
P5.2 — IB coverage (D-035): next.

## Environment
- Repo: github.com/lucaseastman9884-cloud/Internship-Scanner (public)
- Local folder: ~/Documents/GitHub/Internship-Scanner (cloned with GitHub Desktop)
- Mac, Claude Code, Claude Pro, Python 3.9.6. GitHub Actions uses Python 3.12. Tests pass on both.
- Lucas is new to GitHub, terminal, and deployment: explain any step he must do himself.
- Git commits use Lucas's GitHub noreply address. The workflow commits as github-actions[bot].
- Email secrets (P5), names only: `SMTP_USERNAME`, `SMTP_APP_PASSWORD`, `EMAIL_TO`. They live only in GitHub Actions secrets.

## Done
- P1: docs/PLAN.md, config files, first company registry, decisions D-009 to D-014.
- P2: the `scanner` package, Greenhouse, Lever, and Ashby adapters, normalization, eligibility, filtering, scoring, dedupe, upsert, data files, and offline tests.
- P3: Workday adapter with manual fallback; open → possibly_closed → closed; filtered status; recurring programs; full companies_status.json; scoring in config; registry grown to 106 companies.
- P4: decisions D-022 to D-030 and the empty-response guard; Census Gazetteer coordinates; remote_iowa tag; Workday cap of 500 with a per-listing check before a miss; daily workflow; commit-on-change and summary scripts; docs/AUTOMATION.md.
- First GitHub run (manual, 2026-11-03, 05:46–06:12 UTC, about 27 minutes): green. All 58 live companies answered, 0 failed. The bot saved the data as commit b743974.
- P5: `scanner/email_report.py` (morning email, failure email, dry run, Gmail SMTP on port 587 with STARTTLS); `python -m scanner email`; workflow email steps; docs/AUTOMATION.md section 10.
- Docs: D-031 and D-032; SPEC v2.2 with D-033 to D-035 folded in (P5.1).
- P5.1:
  - Manual links capped at `email.max_manual` (10): failed today first, then priority 1, 2, 3, alphabetical, then "…and N more manual companies." (D-033)
  - Email hides listings whose title matches only `insurance_risk` (`email.exclude_role_categories`); the health line counts them. They stay in the data (D-034). "credit risk" and "market risk" now match `banking`.
  - Part-time/term-time titles kept only within 150 miles of home (`exclude_keywords_outside_home`).
  - Technology/marketing titles get −30 each (`scoring.title_penalty_keywords`), except investment-banking titles.
  - Titles naming a different "City, ST" get the tag `location_conflict`, and the email adds "(title says …)".
  - Year-only titles store `season_year`; the email shows "2028 · season not stated".
  - Workflow: manual-run checkbox `simulate_failure` to test the failure email (docs/AUTOMATION.md section 10).

## How to run
From the project folder, after the one-time setup in README.md:
- Run the pipeline: `python -m scanner run` (about 35 to 60 minutes, because of the polite delays)
- Preview the email: `python -m scanner email --dry-run`, then open `outputs/email_preview.html`
- Run the tests: `pytest` (never uses the network, never sends email)
- Run it on GitHub: see docs/AUTOMATION.md
- Test the failure email: Actions → Daily scan → Run workflow → tick `simulate_failure`

## Current coverage (first GitHub run, 2026-11-03)
- 106 companies: 58 fetched live (42 Workday, 15 Greenhouse, 1 Ashby) and 48 manual links.
- Database: 209 listings. 189 open, 16 filtered, 4 possibly_closed, 0 closed. 53 open at or above email.min_score (50).
- P5.1 dry run on this data (before the next scan rescores it): 34 new (25 shown), 9 top open, 0 remote Iowa, 10 manual links + "…and 38 more", 19 insurance-only listings hidden.
- After the next scan rescores: Plante Moran "2027 Summer Wealth Management Marketing Intern" drops 75 → 45 (below 50), and Akuna Capital "Accounting Intern (Term-Time, Part-Time)" in Chicago becomes `filtered`.
- The goal of "hundreds of qualifying listings" is **not met**. IB coverage (P5.2) is the response.

## Next
1. Lucas reviews P5.1: pushes `p5.1-email-polish`, opens and merges the PR (docs/reports/P5_1_REPORT.md).
2. Run **Daily scan** by hand with `simulate_failure` ticked, and check the "Scan failed" email arrives. Then a normal run, and check the morning email.
3. Per D-032: compress, `/clear`, and start P5.2 — IB coverage (D-035).

## Open questions
- Does a commit by github-actions[bot] count as "repository activity" for GitHub's 60-day rule? GitHub's docs don't say. The weekly keepalive assumes yes.
- Will careers sites keep answering GitHub's computers? On the first run all 58 did. One run isn't a trend.
- Commerce Bank lists some internships by street address only, such as "811 Main, Flr 12". They are excluded because no city can be read. Should a company's known cities be used for this?
- Season detection pairs a year and season only up to 2 words apart, so "2028 PMCF Investment Banking Summer Analyst" (Plante Moran, score 48) is "Season not stated" instead of Summer 2028. Widening the gap would raise such scores (+8 → +25). Change it in P5.2?
- Apollo Gmail-account search and monthly reset — test in P6.

## Known limits
- The Workday cap is per search term, not per company in total. 10 big boards still hit 500 for "intern," so interns past that rank can be missed. Listings on those boards can now close, because each is checked individually.
- D-025's "403 means gone" rests on two real postings seen on 2026-11-02.
- A failed run commits nothing, including what the healthy companies found. The next run finds those again.
- On a day with no commit, `meta.json`, `last_seen.json`, and `companies_status.json` aren't saved (D-023). So `consecutive_failures` can undercount, and the Actions summary is the record.
- A second run on the same day counts as a miss. Runs are counted, not days.
- A filtered listing keeps its old score and location label until it's next kept. Filter by status first (the email does).
- The role-category exclusion reads titles only. A listing whose title matches no category isn't hidden, even if it is insurance work (e.g. EMC "Insurance Intern", which scores below 50 anyway).
- `location_conflict` reads "City, ST" text only. A title naming a city without a state, or in another shape, isn't flagged.
- Many board names in the registry were guessed, then verified with a live request. Each entry's notes say GUESS or LINKED.
- If Gmail itself refuses to send, the failure email can't get through either. The Actions tab stays the reliable record.
- UNVERIFIED items are listed in PLAN sections 5 and 7.
