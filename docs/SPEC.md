# 01_SPEC — Internship Scanner v2.2
Supersedes v2.1. Status: SYNCED 2026-11-02 with decisions D-001 to D-032; D-033 to D-035 folded in on 2026-11-03 (P5.1). Decision numbers in parentheses show where a rule came from. If this file and 04_DECISIONS disagree, the decision wins until the next sync.

File names used here: 01_SPEC = `docs/SPEC.md`, 02_CONFIG = `docs/CONFIG.md`, 03_STATUS = `docs/STATUS.md`, 04_DECISIONS = `docs/DECISIONS.md`, 05_SOURCES = `docs/SOURCES.md`.

## MISSION
Build a $0 system that:
1. Collects finance, banking, accounting, investment, insurance, and risk internships and early-career student programs from legitimate sources. It covers both newly posted and previously posted roles in Lucas's target locations.
2. Stores every listing with history, so nothing is lost between runs.
3. Sends Lucas a morning email with:
   - new postings that match his config (cities, seasons, minimum score)
   - 15–20 coffee-chat candidates at those companies
4. Later: an installable, highly interactive web app (PWA) with a filterable list and a map (D-031).

**Success looks like this:**
- Every morning, an email arrives listing new matching internships, upcoming deadlines, and contact candidates.
- The database holds hundreds of current and past listings.
- Lucas changes cities, seasons, keywords, or scoring by editing one config file.
- One failing source never breaks the run.

## ARCHITECTURE: TWO ENGINES (D-003)
**Engine A — Job pipeline.** Python 3, run by GitHub Actions on a daily schedule plus manual trigger. It is deterministic and uses no LLM.
- Reads `config/config.yaml` and `config/companies.yaml`.
- Writes `data/internships.json`, `data/meta.json`, `data/companies_status.json`, and `data/last_seen.json` (D-023).
- Commits only when `internships.json` changes, plus a keepalive commit after 7 days without one (D-023, D-007).
- Sends the morning jobs email (D-005).
- Later serves the static PWA on GitHub Pages (D-031).

**Engine B — Contacts assistant.** A Claude scheduled task at about 7:00 AM CT.
- Reads that day's new and top listings from Engine A's published JSON.
- Uses Apollo through its official connector to find people.
- Sends or drafts the coffee-chat email.
- Keeps a private contacts log in a Google Sheet. Contact data never touches the repo or site (D-004).

## HARD CONSTRAINTS
1. **$0 total.** Use free tiers only, with no credit card. The core pipeline makes no paid API calls and no LLM calls. Engine B runs on Lucas's existing Claude plan and his Apollo free-plan credits, and it must stay inside a configured monthly reveal budget.
2. **Legitimate data only.** Use official public ATS job-board APIs, government APIs, and openly licensed lists.
   - No automated search-engine queries; Google's ToS prohibits them (D-001).
   - No scraping of LinkedIn, Indeed, Handshake, or Glassdoor.
   - Never bypass logins, CAPTCHAs, or rate limits. Respect robots.txt (D-015).
   - Send an identifying User-Agent and make at most 1 request per second per host.
   - If a host returns 403, stop probing it and make the company manual (D-028).
3. **No secrets in git or the frontend.** API keys, the email password, and Lucas's email address live only in GitHub Actions secrets.
4. **Privacy.** The repo and site are public.
   - Tracker data stays in the viewer's browser (localStorage, with export/import).
   - Contact data, the resume, and personal details (phone, email) never go into the repo or site.
5. **No false claims.** Report "tested" separately from "should work."
6. Verify third-party facts against current official docs, and name the source.
7. **Never act for Lucas.** No applications, account creation, or outreach messages are ever sent. Only drafts.

## CONFIGURATION
`config/config.yaml` in the repo is the single source of truth (see 02_CONFIG). No value from it may be hard-coded anywhere else. This includes scoring points (D-020).

## COMPANY REGISTRY ("track every company")
- `config/companies.yaml` has one entry per company:
  - `name`
  - `ats`: greenhouse | lever | ashby | smartrecruiters | workday | manual
  - `board`: the slug or careers URL
  - `cities`
  - `priority`: 1–3
  - `notes`
- Manual companies (no adapter or blocked): any ATS without an adapter, such as Oracle Cloud or iCIMS (D-011, e.g. Pella); RR Donnelley and Northwestern Medicine (D-015); Wells Fargo (D-028). They appear as manual links.
- Removed: BGM Group (D-019).
- Naming: "Federal Reserve System," with each listing's city taken from the posting (D-027).
- `data/companies_status.json` keeps every company ever checked: last checked, current open intern count, last intern posting seen, and fetch health. Companies are never deleted from status history.
- Discovery: paused until a licensed community list is confirmed (D-013). When it resumes, it only suggests; Lucas approves additions.
- **IB coverage is the top scanner priority (D-035), as phase P5.2.** Research which ATS each IB-relevant firm uses: the currently manual Lazard, Piper Sandler, Baird, Stifel and Mesirow, plus new IB firms in or near the target areas (Chicago, Kansas City, Des Moines, Dubuque). Use only legitimate public feeds (D-001, D-002, D-015). Firms with feeds are added as live companies; the rest stay manual links, grouped at the top of the manual list. The registry grows.

## DATA SOURCES (see 05_SOURCES)
- **Priority 1 (official, documented, no auth):** Greenhouse Job Board API, Lever Postings API, Ashby Job Posting API, SmartRecruiters public postings where robots.txt allows (D-015).
- **Priority 2:** Workday public career-site JSON, unofficial, used politely with the risk accepted (D-002, D-010). Per-company search cap is 500, and an unseen listing is checked individually before it counts as missing (D-025). USAJOBS where relevant (later).
- **Priority 3:** community internship lists. ON HOLD until a license is confirmed (D-013).

Every source is an independent adapter behind one interface. A failing adapter logs its error to `meta.json` and the run continues.

## ELIGIBILITY RULES (CLASS OF MAY 2029) (D-006)
- Seasons map to standing:
  - Winter 2027 / Spring 2027 = during sophomore year. Ranked lower, and only within 60 miles of Ames (D-014, D-016).
  - Summer 2027 = after sophomore year (sophomore and early-insight programs)
  - Fall 2027 / Winter–Spring 2028 = during junior year
  - Summer 2028 = after junior year; this is the main summer-analyst internship
  - Summer 2029 = after graduation, so it is not an internship for Lucas
- A season year is not a class year. A "2028 Summer Analyst" is normally for students graduating in 2029, so include it.
- Program titles with a season and year count as internships even without the word "intern" (D-018).
- Exclude only when the posting explicitly rules Lucas out. Examples: "graduating 2027/2028 only," or a standing he won't have that season, such as "rising senior" for Summer 2027.
- If eligibility is unclear, include the listing with `eligibility.status = unclear` and the reason.
- Excluded by preference: William Blair "Working in Technology" programs (D-026).

## LOCATION AND REMOTE RULES
- In-person listings must fall within the home radius, a target area, or a whole included state (02_CONFIG).
- Remote (D-029): only remote listings tied to Iowa are kept, with `is_remote: true` and the tag `remote_iowa`. They get their own section in the email and UI. All other remote listings are excluded.
- Coordinates (D-022): from the 2026 U.S. Census Gazetteer places file stored in the repo. No network geocoding at run time; Nominatim is off. A listing with unknown coordinates never passes a distance check, and the map never plots a null coordinate.

## DATA MODEL (PER LISTING)
- `id`: stable hash of the source job ID, or of company + normalized title + location
- `company_id`, `title`, `company`, `ats`
- `location_raw`, `city`, `state`, `country`, `lat`, `lng`, `is_remote`
- `tags`: list, e.g. `remote_iowa` (D-029), or `location_conflict` when the title names a different "City, ST" than the kept location (P5.1)
- `sources`: list of `{source_name, url, source_job_id}`
- `apply_url`
- `date_posted` and `deadline`, only if the source states them; never invented
- `first_seen`, `last_seen`
- `status`: open | filtered | possibly_closed | closed (D-024)
- `season`, `role_category`
- `season_year`: the year a title states with no season word, e.g. 2028 for "2028 Audit or Tax Intern"; the season stays not stated (P5.1)
- `eligibility`: `{status: eligible|unclear|ineligible, reason}`
- `relevance_score` (0–100), `match_reasons` (human-readable list)
- `description_snippet` (short)
- `recurring` (boolean), `last_known_open`

## "NEW AND OLD" LOGIC
- **Never delete.** Each run upserts records and updates `last_seen`.
- **Missing listings.** A listing missing for N consecutive runs becomes `possibly_closed`; after M runs it becomes `closed`. N and M are set in the config. Closed listings stay as history.
- **Filtered (D-024).** A listing that is still posted but now excluded by the config is `filtered`, not closed. Filtered listings keep stale score and location, so every consumer (email, UI) filters by status first.
- **"New."** A listing is new if `first_seen` falls within X days (config), or, in the web app, if it appeared since the viewer's last visit.
- **Recurring.** If the same company and program appear across seasons, set `recurring = true` and show `last_known_open`.
- **Cross-source dedupe.** Merge listings with the same company, normalized title, and city, keeping every source link.

## RELEVANCE SCORING
- Rule-based and driven entirely by the config, including point values (D-020): role keywords, location, season, eligibility, and early-career signals.
- Keyword matching uses whole words only (D-012).
- A listing with no role-category match is capped at 35 points (D-021).
- Every point added or removed produces a match reason.
- The email threshold is set in the config and calibrated during QA using a spot check of 20 included and 20 excluded listings.

## MORNING EMAIL — ENGINE A (P5) (D-005, D-009, D-033, D-034)
- An HTML email to Lucas after each successful daily run.
- Subject: "Internships — {n} new ({date})".
- Sections:
  1. New since the last email, sorted by score.
  2. Deadlines in the next 14 days.
  3. Top open matches, with a configurable limit. It skips listings already shown under New (D-033).
  4. Remote — Iowa (D-029), only if any exist. These listings appear only here; they get a NEW badge and count in the subject. The areas filter doesn't apply to them; min_score and seasons do (D-033).
  5. Manual links to check (manual companies), short: companies whose fetch failed today first, then priority 1, 2, 3, alphabetical within each group, cut at `email.max_manual`, then "…and N more manual companies." (D-033)
  6. A one-line source-health summary, including how many listings the role-category exclusion hid (D-034).
- Only open listings are included.
- Filters come from the `email:` block in the config: areas (target-area names and/or state codes), seasons (season names plus "Not stated"), minimum score, maximum items, `max_manual`, and a role-category exclusion (D-033, D-034).
- **Role-category exclusion (D-034).** Lucas's goal is investment banking, so a listing whose title matches only categories in `email.exclude_role_categories` (shipped: `["insurance_risk"]`) is hidden from the email. A listing that also matches banking, IB, corporate finance, investments or accounting still appears. Hidden listings stay in `data/internships.json` with their scores and will show in the web app. Bank credit- and market-risk titles match `banking`, so they aren't hidden.
- If a run fails, a short failure email goes out instead. It fires on any failed step and names the step (D-033). A manual run can simulate a failure to test it (P5.1).
- The data commit runs whenever the scan succeeds, even if the email fails, so no data is lost (D-033).
- Sending method: Gmail SMTP from a separate sender account, port 587 with STARTTLS (Google support 7104828), with an app password stored only in GitHub Actions secrets (D-009, D-033). Lucas's receiving address is also a secret.

## COFFEE-CHAT CONTACTS — ENGINE B (P6) (D-004, D-008)
- **Input:** companies with new or top-scoring listings from `data/internships.json`.
- **Apollo access:** only through the official Apollo connector (OAuth) or the official API. No LinkedIn browsing or scraping.
- **Priority order:** ISU alumni (prefer finance/banking/accounting roles in the posting's city), then campus/university recruiters, then people on or near the hiring team.
- **Volume:** 15–20 candidates per day, showing name, title, company, and LinkedIn URL when available.
- Emails and phones are revealed only within `contacts.monthly_reveal_budget` (150) and `daily_reveal_cap` (5), spending first on the highest-scoring jobs.
- Search results that need no credits can list more candidates than are revealed.
- **Drafts:** a coffee-chat request for each revealed contact, under 90 words. It mentions the shared connection plus one true resume detail, asks for 15–20 minutes, and makes no referral ask.
- **Contacts log:** a private Google Sheet, so the same person is never suggested twice.
- **Output:** an email or Gmail draft to Lucas. Test whether Gmail-account search works in P6 (D-008).

## WEB APP — INSTALLABLE INTERACTIVE PWA (P7–P8) (D-031)
**Hosting:** static files on GitHub Pages; no backend, no accounts, no build server. Still $0.

**Installable:**
- Web app manifest (name, icons, theme color, standalone display) and a service worker.
- Chrome/Edge show "Install," and it opens in its own window from the dock or Start menu.
- The last fetched data is cached, so it opens offline and shows "Offline — data from {date}."

**Core (from v2.0):**
- Synced list and map (Leaflet + OpenStreetMap, clustered markers).
- Filters: search, distance, city, role, season, date range, status, source, eligibility, minimum score, remote-Iowa toggle.
- Sorting, plus a detail drawer with match reasons and all source links.
- localStorage tracker (save, status, notes, My List, export/import).
- "New since last visit" badges and a freshness/source-health indicator.
- URL-encoded filters; loading, empty, and error states.
- Accessibility (keyboard navigation, labeled controls, contrast).
- Responsive layout at 375px, light and dark modes.

**Interactive layer (new):**
- Instant filtering: results update as you type or drag, with no "Apply" button.
- Tracker board: drag cards between Saved → Applied → Interview → Offer/Rejected (localStorage only).
- Deadline timeline: a horizontal view of upcoming deadlines you can click into.
- Charts: listings by city, by role category, and by week (a small charting library, pinned).
- Keyboard shortcuts: `/` search, `j`/`k` move, `s` save, `o` open apply link, `?` help.
- Map interactions: hover a card to highlight its pin and vice versa; draw a radius from any city.
- Company pages: every listing for a company, past and present, with recurring history.

**Rules:**
- All interactivity is client-side.
- Contact data never appears (D-004).
- Few dependencies, all pinned.

## PHASES
At the end of every phase:
- Report files changed, tests run and how, results, known issues, and next step.
- Update `docs/STATUS.md`.
- Compress (D-032):
  - paste the STATUS update into 03_STATUS and new decisions into 04_DECISIONS
  - fold accepted decisions into 01_SPEC/02_CONFIG
  - run `/clear` in Claude Code
  - start a new Command Center chat

Phases:
- **P0** — Setup and salvage. DONE.
- **P1** — Plan. DONE.
- **P2** — Pipeline core. DONE.
- **P3** — Full pipeline. DONE.
- **P4** — Automation. DONE (first GitHub run green on 2026-11-03).
- **P5** — Morning email (Engine A). Merged (PR #5); a real send is not yet confirmed (see 03_STATUS).
- **P5.1** — Email polish: manual-links cap (D-033), insurance-only listings hidden from the email (D-034), part-time/term-time and off-target title filters, title location conflicts, year-only seasons, and a testable failure email.
- **P5.2** — IB coverage (D-035): research each IB-relevant firm's ATS, add the firms with legitimate public feeds, and group the rest at the top of the manual list. Comes before P6.
- **P6** — Contacts (Engine B). The Claude scheduled-task prompt, the Google Sheet log, and the credit budget.
- **P7** — PWA core. List, filters, sort, detail drawer, tracker, manifest, service worker, install, and offline; deployed on GitHub Pages.
- **P8** — Map and interactive layer. List–map sync, URL state, "new since last visit," tracker board, timeline, charts, shortcuts, and company pages.
- **P9** — QA and README.

## QA CHECKLIST
**Carried over from v2.0:**
- One command runs the pipeline from a clean clone.
- A failing source is isolated and logged.
- Rerunning creates zero duplicates.
- Fixture tests show listings moving open → possibly_closed → closed, and open → filtered.
- No marker is plotted with null coordinates.
- Relevance spot check: 20 included and 20 excluded listings with their reasons.
- A secret scan finds no keys.
- At 375px, everything works with no horizontal scroll.
- A shared URL reproduces the exact view.
- Tracker data survives a reload, and export/import round-trips.
- The README is complete.

**Added in v2.1:**
- The morning email arrives and respects the config filters; it shows only open listings.
- A failure email is sent when a run fails.
- A PII scan finds no contact data, phone numbers, or personal email in the repo.
- Engine B stays within the Apollo reveal budget.
- Eligibility fixtures pass, for example that "2028 Summer Analyst" is included.

**Added in v2.2:**
- Chrome shows "Install." The installed app opens offline with cached data.
- A Lighthouse PWA/accessibility check has no critical failures.
- Keyboard shortcuts and drag-and-drop work, and the tracker board has a keyboard alternative.
- `remote_iowa` listings appear only in their own section.

## WORKING RULES
- Simplicity over cleverness. Few dependencies, all pinned.
- Small commits with clear messages.
- Comments explain why, not what.
- Ask when intent is unclear; check the docs when a fact is unclear.
- Never silently drop a requirement.
- Compress after every phase (D-032). Project files are the memory; chats are disposable.
