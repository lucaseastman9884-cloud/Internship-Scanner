# SPEC — Internship Scanner v2.1
Source of truth for what we are building. Decisions referenced as D-00X live in docs/DECISIONS.md. Settings live in docs/CONFIG.md (becomes config/config.yaml).

## MISSION
Build a $0 system that:
1. Collects finance, banking, accounting, investment, insurance, and risk internships and early-career student programs from legitimate sources — newly posted and previously posted — in Lucas's target locations.
2. Stores every listing with history so nothing is lost between runs.
3. Sends Lucas a morning email with new postings that match his config (cities, seasons, minimum score) and 15–20 coffee-chat candidates at those companies.
4. Later: a public web app with a filterable list and a map.

**Success looks like this:**
- Every morning an email arrives with new matching internships, upcoming deadlines, and contact candidates.
- The database holds hundreds of current and past listings.
- Lucas changes cities, seasons, or keywords by editing one config file.
- One failing source never breaks the run.

## ARCHITECTURE: TWO ENGINES (D-003)
**Engine A — Job pipeline.** Python 3, run by GitHub Actions daily plus manual trigger. Deterministic, no LLM.
- Reads `config/config.yaml` and `config/companies.yaml`.
- Writes `data/internships.json`, `data/meta.json`, `data/companies_status.json`.
- Sends the morning jobs email (D-005).
- Later serves the static web app on GitHub Pages.

**Engine B — Contacts assistant.** A Claude scheduled task at about 7:00 AM CT.
- Reads that day's new and top listings from Engine A's published JSON.
- Uses Apollo through its official connector to find people.
- Sends or drafts the coffee-chat email.
- Keeps a private contacts log in a Google Sheet. Contact data never touches the repo or site (D-004).

## HARD CONSTRAINTS
1. **$0 total.** Free tiers only, no credit card. The core pipeline makes no paid API calls and no LLM calls. Engine B runs on Lucas's existing Claude plan and Apollo free credits, within a monthly reveal budget.
2. **Legitimate data only.** Official public ATS job-board APIs, government APIs, openly licensed lists.
   - No automated search-engine queries (Google's ToS prohibits them) (D-001).
   - No scraping LinkedIn, Indeed, Handshake, or Glassdoor.
   - Never bypass logins, CAPTCHAs, or rate limits. Respect robots.txt.
   - Identifying User-Agent; at most 1 request per second per host.
3. **No secrets in git or the frontend.** API keys, the email password, and Lucas's email address live only in GitHub Actions secrets.
4. **Privacy.** The repo and site are public.
   - Tracker data stays in the viewer's browser (localStorage, export/import).
   - Contact data, the resume, and personal details (phone, email) never go in the repo or site.
5. **No false claims.** Report "tested" separately from "should work."
6. **Verify third-party facts** against current official docs, and name the source.
7. **Never act for Lucas.** No applications, account creation, or outreach messages are sent. Drafts only.

## COMPANY REGISTRY ("track every company")
- `config/companies.yaml`, one entry per company: `name`, `ats` (`greenhouse` | `lever` | `ashby` | `smartrecruiters` | `workday` | `manual`), `board` (slug or careers URL), `cities`, `priority` (1–3), `notes`.
- Seed list: companies from the old Internship Log (see docs/STATUS.md) plus target employers in Iowa, Kansas City, and Chicago. Verify each company's ATS.
- `data/companies_status.json` keeps every company ever checked: last checked, open intern count, last intern posting seen, fetch health. Never deleted.
- Discovery: weekly list of companies seen in community lists but not in the registry. Suggestions only; Lucas approves additions.

## DATA SOURCES (see docs/SOURCES.md)
- Priority 1 (official, documented, no auth): Greenhouse, Lever, Ashby, SmartRecruiters.
- Priority 2: Workday public career-site JSON, used politely (D-002). USAJOBS where relevant.
- Priority 3: openly licensed community internship lists.
Every source is an independent adapter behind one interface. A failing adapter logs its error to `meta.json` and the run continues.

## ELIGIBILITY RULES (CLASS OF MAY 2029) (D-006)
- Season → standing:
  - Summer 2027 = after sophomore year (sophomore / early-insight programs)
  - Fall 2027, Winter/Spring 2028 = during junior year
  - Summer 2028 = after junior year — the main summer-analyst internship
  - Summer 2029 = after graduation — not an internship for Lucas
- A season year is not a class year. "2028 Summer Analyst" normally targets 2029 graduates: include it.
- Exclude only when the posting explicitly rules Lucas out (e.g., "graduating 2027/2028 only," "rising senior" for Summer 2027).
- Unclear → include with `eligibility.status = unclear` and the reason.

## DATA MODEL (PER LISTING)
- `id`: stable hash of source job ID, or company + normalized title + location
- `company_id`, `title`, `company`, `ats`
- `location_raw`, `city`, `state`, `country`, `lat`, `lng`, `is_remote`
- `sources`: list of `{source_name, url, source_job_id}`
- `apply_url`
- `date_posted`, `deadline` — only if the source states them; never invented
- `first_seen`, `last_seen`
- `status`: `open` | `possibly_closed` | `closed`
- `season`, `role_category`
- `eligibility`: `{status: eligible|unclear|ineligible, reason}`
- `relevance_score` (0–100), `match_reasons` (human-readable list)
- `description_snippet` (short)
- `recurring` (boolean), `last_known_open`

## "NEW AND OLD" LOGIC
- Never delete. Each run upserts and updates `last_seen`.
- Missing for N consecutive runs → `possibly_closed`; after M → `closed`. N, M in config. Closed listings stay as history.
- New = `first_seen` within X days (config), or in the web app, appeared since the viewer's last visit.
- Recurring: same company + program across seasons → `recurring = true`, show `last_known_open`.
- Cross-source dedupe: same company, normalized title, and city → merge, keep every source link.

## RELEVANCE SCORING
Rule-based, driven by config (role keywords, location, season, eligibility, early-career signals). Every point added or removed produces a match reason. Email threshold set in config, calibrated in QA with a 20-included / 20-excluded spot check.

## MORNING EMAIL — ENGINE A (D-005)
- HTML email after each successful daily run. Subject: "Internships — {n} new ({date})".
- Sections: (1) new since last email, by score; (2) deadlines in next 14 days; (3) top open matches; (4) one-line source health; (5) "check manually" links for Workday fallbacks (D-002).
- Filters from the `email:` block in config.
- If a run fails, a short failure email goes out instead.
- Sending method verified in Phase 1: Gmail SMTP with an app password in GitHub secrets, or another free, no-card provider.

## COFFEE-CHAT CONTACTS — ENGINE B (D-004, D-008)
- Input: companies with new or top-scoring listings from `data/internships.json`.
- Apollo only via official connector (OAuth) or official API. No LinkedIn browsing or scraping.
- Priority: ISU alumni (prefer finance/banking/accounting, posting's city) → campus recruiters → hiring-team neighbors.
- 15–20 candidates/day (name, title, company, LinkedIn URL when available). Emails revealed only within `contacts.monthly_reveal_budget` / `daily_reveal_cap`, highest-scoring jobs first.
- Draft per revealed contact: under 90 words, shared connection + one true resume detail, asks for 15–20 minutes, no referral ask.
- Private Google Sheet log so no one is suggested twice.

## WEB APP (LATER)
Synced list + map (Leaflet + OpenStreetMap, clustered markers); filters (search, distance, city, role, season, date range, status, source, eligibility, min score); sort; detail drawer with match reasons and all source links; localStorage tracker (save, status, notes, My List, export/import); "new since last visit"; freshness/source health; URL-encoded filters; loading/empty/error states; accessibility; responsive at 375px; light/dark.
Geocoding in pipeline only: local city table first, then Nominatim under its usage policy, cached in `data/geocache.json`.

## PHASES
Pause after each phase and report: files changed, tests run and how, results, known issues, next step. Update `docs/STATUS.md` every time.
- P0 — Setup (done by Lucas).
- P1 — Plan: `docs/PLAN.md`, `config/config.yaml`, `config/companies.yaml` (verified ATS), verified source table, email method. STOP for approval.
- P2 — Pipeline core: config loader, adapter interface, Greenhouse + one more adapter, normalization, eligibility, scoring, dedupe, upsert, `meta.json`, fixture tests, local run.
- P3 — Full pipeline: remaining adapters (incl. Workday), status/history/recurring, company status, geocoding. Tests for each.
- P4 — Automation: GitHub Actions daily (~5:30 AM CT) + manual; commit only on change; visible failures.
- P5 — Morning email.
- P6 — Contacts (Engine B).
- P7 — Web app core. P8 — Map. P9 — QA + README.

## QA CHECKLIST
- One command runs the pipeline from a clean clone.
- A failing source is isolated and logged.
- Rerun creates zero duplicates.
- Fixtures show open → possibly_closed → closed.
- No map marker with null coordinates; ungeocoded listings show "Location unknown."
- Relevance spot check: 20 included + 20 excluded with reasons.
- Secret scan finds no keys. PII scan finds no contact data, phone numbers, or personal email.
- 375px: everything works, no horizontal scroll.
- Shared URL reproduces the view. Tracker survives reload; export/import round-trips.
- Morning email arrives and respects filters; failure email works.
- Engine B stays within Apollo budget.
- Eligibility fixtures pass ("2028 Summer Analyst" included).
- README: what it is, how to run, add a source, edit config, deploy, costs and free-tier limits.

## WORKING RULES
Simplicity over cleverness. Few dependencies, pinned. Small commits, clear messages. Comments explain why. Ask when intent is unclear; check docs when a fact is unclear. Never silently drop a requirement. Lucas is learning: explain any step he must do himself.
