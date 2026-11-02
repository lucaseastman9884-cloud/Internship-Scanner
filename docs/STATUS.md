# STATUS — Current state (updated 2026-11-02)

## Phase
P0 — Setup: DONE.
P1 — Plan: DONE and approved.
P2 — Pipeline core: DONE, **awaiting Lucas's approval**. Do not start P3 until approved.

## Environment
- Repo: github.com/lucaseastman9884-cloud/Internship-Scanner (public)
- Local folder: ~/Documents/GitHub/Internship-Scanner (cloned with GitHub Desktop)
- Mac, Claude Code v2.1.316, Claude Pro, Python 3.9.6
- Lucas is new to GitHub, terminal, and deployment: explain any step he must do himself.
- Git commits use Lucas's GitHub noreply address.

## Done
- P1: docs/PLAN.md, config files, company registry (44 companies), decisions D-009 to D-014 accepted.
- P2: the `scanner` package, adapters for Greenhouse, Lever, Ashby, and SmartRecruiters, normalization, eligibility, filtering, scoring, dedupe, upsert, data files, and offline tests. Committed locally on branch `phase-2-core`. Not pushed; Lucas pushes with GitHub Desktop.

## How to run
From the project folder, after the one-time setup in README.md:
- Run the pipeline: `python -m scanner run`
- Run the tests: `pytest`

## Current coverage
Only 3 of 44 companies are fetched live: American Equity, Cottingham & Butler, and William Blair (Greenhouse).
- 16 Workday companies: skipped until P3.
- 2 SmartRecruiters companies: blocked by robots.txt, awaiting D-015.
- 23 manual companies: links only.
- Registry has no Lever or Ashby company yet, so those two adapters are tested with fixtures only.

## Seed companies (from the old Internship Log)
Bankers Trust, Wintrust Financial, Federal Reserve Bank of Kansas City, CIBC, Corient, Commerce Bank, UHY, Northwestern Medicine, RR Donnelley, Pella, BMO, Fifth Third, Lazard, CliftonLarsonAllen, Forvis Mazars, American Equity, Bank Iowa, BGM Group, KPMG.
ATS check results are in config/companies.yaml.

## Next
Lucas reviews P2 and decides the open questions below. Then P3 — Full pipeline (see SPEC "PHASES").

## Open questions
- D-015: keep respecting SmartRecruiters' robots.txt (recommended), or treat the documented API as exempt?
- D-014 says Spring and Winter 2027 are realistic only near Ames/Des Moines. Today they only get a lower weight everywhere. Should they be limited by location too?
- Should insurance claims roles count as a target role? "2027 Summer Claims Adjuster Internship" scores 40, below the email's 50, because the config's keyword is "claims analyst intern".
- BGM Group: firm not identified, since both domains are parked. Does the old log have a link or location?
- Git email: commit 820b3ab, already on GitHub, records Lucas's Gmail. Rewrite that one commit?
- Apollo Gmail-account search and monthly reset — test in P6.

## Known limits
- UNVERIFIED items are listed in PLAN section 5 and section 7.
- Many `cities` values in the registry are "expected," not observed. Each entry's notes say which.
- `config/cities.yaml` coordinates are approximate and from memory, until P3 geocoding.
- Status transitions (possibly_closed, closed), recurring detection, and lat/lng are not built yet (P3).
