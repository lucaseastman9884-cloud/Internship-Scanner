# STATUS — Current state (updated 2026-11-03)

## Phase
P0 — Setup: DONE.
P1 — Plan: DONE and approved.
P2 — Pipeline core: DONE and merged to main.
P3 — Full pipeline: DONE and merged to main.
P4 — Automation: DONE and merged to main (PR #4). The first GitHub run, started by hand, succeeded on 2026-11-03.
P5 — Morning email: merged to main (PR #5). Whether a real email has arrived is **not confirmed** in the repo.
P5.1 — Email polish: merged to main (PR #6).
P5.2 — IB coverage (D-035): built on branch `p5-2-ib-coverage`, **not pushed, awaiting Lucas's approval**. Tested offline, plus one full run and email dry run on a copy of real data (nothing sent). Report: docs/reports/P5_2_REPORT.md.
P6 — Contacts (Engine B): next.

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
- First GitHub run (manual, 2026-11-03, about 27 minutes): green, all 58 live companies answered.
- P5: `scanner/email_report.py` (morning email, failure email, dry run, Gmail SMTP on port 587 with STARTTLS); `python -m scanner email`; workflow email steps.
- P5.1: manual links capped at `email.max_manual` (10); insurance-only listings hidden from the email (D-034); part-time/term-time titles kept only near home; technology/marketing titles −30 unless IB; `location_conflict` tag; `season_year`; `simulate_failure` checkbox.
- P5.2 (on branch, PROPOSED D-037 to D-040):
  - Registry: 114 companies, 61 live (44 Workday, 16 Greenhouse, 1 Ashby) and 53 manual.
  - New live boards: Piper Sandler and Stout (Workday), Lincoln International (Greenhouse).
  - New manual links: Houlihan Lokey, Moelis & Company, D.A. Davidson, Fireclay Partners, Jefferies, Kroll.
  - Lazard, Stifel and Mesirow are confirmed manual, with their ATS recorded.
  - Every firm was verified from its own careers page, with one request per endpoint.
  - Optional `tags` on companies. 16 IB and advisory firms are tagged `ib` and set to priority 1.
  - `email.manual_first_tags: ["ib"]`: the manual list shows failed today, then IB firms, then the rest.
  - Seasons: a season word and a 2026–2030 year anywhere in a title now pair. Two different seasons or years give "Not stated", with the reason in `match_reasons`.

## How to run
From the project folder, after the one-time setup in README.md:
- Run the pipeline: `python -m scanner run` (about 30 to 35 minutes, because of the polite delays)
- Preview the email: `python -m scanner email --dry-run`, then open `outputs/email_preview.html`
- Run the tests: `pytest` (never uses the network, never sends email)
- Run it on GitHub: see docs/AUTOMATION.md
- Test the failure email: Actions → Daily scan → Run workflow → tick `simulate_failure`

## Current coverage (P5.2 dry run, 2026-11-03, on a copy of the data)
- Run time: 31.6 minutes locally. The new firms add about 14 requests (about 20 seconds).
- Database: 215 listings, 193 open, 57 open at or above email.min_score (50).
- New from P5.2:
  - Lincoln International "2028 Summer Analyst Intern" (CAG and M&A, Chicago, 95);
  - Piper Sandler "2027 Summer Internship Program – Public Finance" (Des Moines and Leawood, 85).
- Plante Moran "2028 PMCF Investment Banking Summer Analyst" is now Summer 2028, scoring 75 (was 48). It ranks 14th among top open matches, so the cap of 10 keeps it out of the email.
- The goal of "hundreds of qualifying listings" is **still not met**. Most remaining IB firms use an ATS with no adapter (TalentLink, Oracle, iCIMS, UKG, Breezy) or block us.

## Next
1. Lucas reviews P5.2 (docs/reports/P5_2_REPORT.md): decide D-037 to D-040, including whether to allow one fresh request to Baird's careers page. Then push `p5-2-ib-coverage`, and open and merge the PR.
2. If not done yet: run **Daily scan** by hand with `simulate_failure` ticked and check the "Scan failed" email arrives. Then do a normal run and check the morning email.
3. Per D-032: compress, `/clear`, and start **P6 — Contacts (Engine B)**.

## Open questions
- Raise `email.max_manual` above 10? There are exactly 10 IB-tagged manual firms, so any failure pushes one into "…and N more".
- Raise `email.max_top_open`, or show IB listings separately? Plante Moran's IB listing qualifies but ranks 14th.
- Which adapter, if any, comes next? TalentLink would unlock Jefferies and Moelis (D-040).
- Does a commit by github-actions[bot] count as "repository activity" for GitHub's 60-day rule? GitHub's docs don't say. The weekly keepalive assumes yes.
- Will careers sites keep answering GitHub's computers? One run isn't a trend.
- Commerce Bank lists some internships by street address only. Should a company's known cities be used for this?
- Apollo Gmail-account search and monthly reset — test in P6.

## Known limits
- The Workday cap is per search term, not per company in total. 10 big boards still hit 500 for "intern."
- Stout is fetched from its student site only; an intern posted only on Stout-Careers would be missed.
- D-025's "403 means gone" rests on two real postings seen on 2026-11-02.
- A failed run commits nothing, including what the healthy companies found. The next run finds those again.
- On a day with no commit, `meta.json`, `last_seen.json`, and `companies_status.json` aren't saved (D-023).
- A second run on the same day counts as a miss. Runs are counted, not days.
- A filtered listing keeps its old score and location label until it's next kept.
- The role-category exclusion reads titles only.
- `location_conflict` reads "City, ST" text only.
- Many board names in the registry were guessed, then verified with a live request. Each entry's notes say GUESS or LINKED; P5.2 entries were all found from the firm's own page.
- If Gmail itself refuses to send, the failure email can't get through either.
- UNVERIFIED items are listed in PLAN sections 5 and 7.
