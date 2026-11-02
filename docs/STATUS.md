# STATUS — Current state (updated 2026-11-02)

## Phase
P0 — Setup: DONE.
P1 — Plan: DONE and approved.
P2 — Pipeline core: DONE and merged to main.
P3 — Full pipeline: DONE and merged to main.
P4 — Automation: built on branch `phase-4-automation`, **not pushed, awaiting Lucas's approval**. The workflow has never run on GitHub, because it can only run after Lucas merges it. Do not start P5 until approved.

## Environment
- Repo: github.com/lucaseastman9884-cloud/Internship-Scanner (public)
- Local folder: ~/Documents/GitHub/Internship-Scanner (cloned with GitHub Desktop)
- Mac, Claude Code, Claude Pro, Python 3.9.6. GitHub Actions uses Python 3.12. Tests pass on both.
- Lucas is new to GitHub, terminal, and deployment: explain any step he must do himself.
- Git commits use Lucas's GitHub noreply address. The workflow commits as github-actions[bot].

## Done
- P1: docs/PLAN.md, config files, first company registry, decisions D-009 to D-014.
- P2: the `scanner` package, Greenhouse, Lever, and Ashby adapters, normalization, eligibility, filtering, scoring, dedupe, upsert, data files, and offline tests.
- P3: Workday adapter with manual fallback; open → possibly_closed → closed; filtered status; recurring programs; full companies_status.json; scoring in config; registry grown to 106 companies.
- P4: decisions D-022 to D-030 and the empty-response guard; Census Gazetteer coordinates; remote_iowa tag; Workday cap of 500 with a per-listing check before a miss; daily workflow; commit-on-change and summary scripts; docs/AUTOMATION.md.

## How to run
From the project folder, after the one-time setup in README.md:
- Run the pipeline: `python -m scanner run` (about 35 to 60 minutes, because of the polite delays)
- Run the tests: `pytest` (never uses the network)
- Run it on GitHub: see docs/AUTOMATION.md

## Current coverage (real local run, 2026-11-02)
- 106 companies: 58 fetched live (42 Workday, 15 Greenhouse, 1 Ashby) and 48 manual links.
- Database: 209 listings. 190 open, 16 filtered, 3 possibly_closed, 0 closed. **54 open at or above email.min_score (50).**
- 23 open listings are "Location unknown": 13 at Plante Moran's "Chicago Riverside Plaza" and 10 at EMC's bare "Iowa". 1 open listing is tagged remote_iowa.
- The goal of "hundreds of qualifying listings" is **not met**. Most open listings have no finance role signal, so the useful number is closer to the 54.
- No live company uses Lever, so that adapter is tested with fixtures only.

## Next
Lucas merges this branch and does a first manual run (docs/AUTOMATION.md). Then P5 — Morning email (see SPEC "PHASES").

## Open questions
- Does a commit by github-actions[bot] count as "repository activity" for GitHub's 60-day rule? GitHub's docs don't say. The weekly keepalive assumes yes.
- Will careers sites answer requests from GitHub's computers the way they answer a home connection? Unknown until the first run. If more than half refuse, the run goes red. If that happens, it needs a decision.
- Commerce Bank lists some internships by street address only, such as "811 Main, Flr 12". They are excluded because no city can be read. Should a company's known cities be used for this?
- SPEC.md still describes Nominatim and three statuses. DECISIONS.md (D-022, D-024) overrides it. Should SPEC be edited to match?
- Apollo Gmail-account search and monthly reset — test in P6.

## Known limits
- The Workday cap is per search term, not per company in total. 10 big boards still hit 500 for "intern," so interns past that rank can be missed. Listings on those boards can now close, because each is checked individually.
- D-025's "403 means gone" rests on two real postings seen on 2026-11-02.
- A failed run commits nothing, including what the healthy companies found. The next run finds those again.
- On a day with no commit, `meta.json`, `last_seen.json`, and `companies_status.json` aren't saved (D-023). So `consecutive_failures` can undercount, and the Actions summary is the record.
- A second run on the same day counts as a miss. Runs are counted, not days.
- A filtered listing keeps its old score and location label until it's next kept. Filter by status first.
- Many board names in the registry were guessed, then verified with a live request. Each entry's notes say GUESS or LINKED.
- UNVERIFIED items are listed in PLAN sections 5 and 7.
