# STATUS — Current state (updated 2026-11-03)

## Phase
P0 — Setup: DONE.
P1 — Plan: DONE and approved.
P2 — Pipeline core: DONE and merged to main.
P3 — Full pipeline: DONE and merged to main.
P4 — Automation: DONE and merged to main (PR #4). The first GitHub run, started by hand, succeeded on 2026-11-03.
Docs sync: D-031 (PWA web app) and D-032 (compress context after every phase) recorded on branch `docs-sync-d031-d032`, awaiting Lucas's PR merge. No code changed.
P5 — Morning email: built on branch `phase-5-email`, **not pushed, awaiting Lucas's approval**. Tested offline only. **No real email has been sent**: that needs the three secrets and a run on GitHub.

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
- Docs sync: D-031 and D-032 in DECISIONS; P7 and P8 laid out in PLAN section 10.
- P5: `scanner/email_report.py` (morning email, failure email, dry run, Gmail SMTP on port 587 with STARTTLS); `python -m scanner email`; `email:` settings validated; "last sent" record kept in `data/meta.json`; workflow email steps; docs/AUTOMATION.md section 10. Report: docs/reports/P5_REPORT.md.

## How to run
From the project folder, after the one-time setup in README.md:
- Run the pipeline: `python -m scanner run` (about 35 to 60 minutes, because of the polite delays)
- Preview the email: `python -m scanner email --dry-run`, then open `outputs/email_preview.html`
- Run the tests: `pytest` (never uses the network, never sends email)
- Run it on GitHub: see docs/AUTOMATION.md

## Current coverage (first GitHub run, 2026-11-03)
- 106 companies: 58 fetched live (42 Workday, 15 Greenhouse, 1 Ashby) and 48 manual links.
- Fetched 10,126, kept 191, 0 new listings.
- Database: 209 listings. 189 open, 16 filtered, 4 possibly_closed, 0 closed. **53 open at or above email.min_score (50).**
- 23 open listings are "Location unknown": 13 at Plante Moran's "Chicago Riverside Plaza" and 10 at EMC's bare "Iowa". 1 open listing is tagged remote_iowa.
- The goal of "hundreds of qualifying listings" is **not met**. Most open listings have no finance role signal, so the useful number is closer to the 54.
- No live company uses Lever, so that adapter is tested with fixtures only.
- P5 dry run on this data: 53 new (25 shown, the `max_new` limit), 0 deadlines, 10 top open, 1 remote Iowa, 48 manual links.

## Next
1. Lucas merges `docs-sync-d031-d032` (if not yet), then reviews P5: adds the three secrets, pushes `phase-5-email`, opens and merges the PR, and starts a manual run (docs/reports/P5_REPORT.md has the steps).
2. Check that the email arrives, and that a failure email works (SPEC QA: "Morning email arrives and respects filters; failure email works").
3. Per D-032: fold accepted decisions into SPEC and CONFIG, run `/clear`, and start a new planning chat for P6 — Contacts (Engine B).

## Open questions
- Does a commit by github-actions[bot] count as "repository activity" for GitHub's 60-day rule? GitHub's docs don't say. The weekly keepalive assumes yes.
- Will careers sites keep answering GitHub's computers? On the first run all 58 did. One run isn't a trend.
- Commerce Bank lists some internships by street address only, such as "811 Main, Flr 12". They are excluded because no city can be read. Should a company's known cities be used for this?
- SPEC.md still describes Nominatim and three statuses, and its WEB APP section predates D-031. D-032 says to fold accepted decisions into SPEC after each phase, so this is now a to-do, not a question. SPEC's MORNING EMAIL section also lists 5 sections; P5 built the 6 in the P5 brief (adds Remote — Iowa per D-029).
- The "Check these manually" section lists all 48 manual companies on one compact line of links. Should it be shortened, for example to priority 1 only? That would need a new `email:` setting.
- Apollo Gmail-account search and monthly reset — test in P6.

## Known limits
- The Workday cap is per search term, not per company in total. 10 big boards still hit 500 for "intern," so interns past that rank can be missed. Listings on those boards can now close, because each is checked individually.
- D-025's "403 means gone" rests on two real postings seen on 2026-11-02.
- A failed run commits nothing, including what the healthy companies found. The next run finds those again.
- On a day with no commit, `meta.json`, `last_seen.json`, and `companies_status.json` aren't saved (D-023). So `consecutive_failures` can undercount, and the Actions summary is the record. The email's "last sent" record is also in `meta.json`, but that's harmless: on such a day no listing was added.
- A second run on the same day counts as a miss. Runs are counted, not days.
- A filtered listing keeps its old score and location label until it's next kept. Filter by status first (the email does).
- Many board names in the registry were guessed, then verified with a live request. Each entry's notes say GUESS or LINKED.
- If Gmail itself refuses to send, the failure email can't get through either. The Actions tab stays the reliable record.
- UNVERIFIED items are listed in PLAN sections 5 and 7.
