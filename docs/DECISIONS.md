# DECISIONS — Decision log
Newest at the bottom. Status: PROPOSED / ACCEPTED / REJECTED (Lucas decides). Lucas may revise any decision; record changes as new entries.

## D-001 — No Google searches as a data source (ACCEPTED 2026-11-02)
The old task ran automated `site:` Google searches. Google's ToS prohibits automated queries, and recent runs found zero usable listings. Pull jobs directly from each company's ATS public job-board API instead.

## D-002 — Workday public career-site JSON (ACCEPTED 2026-11-02, option A)
Workday's `/wday/cxs/{tenant}/{site}/jobs` endpoint is public and login-free but undocumented. Use it politely: only listed companies, ≤1 request/second/host, identifying User-Agent, respect robots.txt, once per day. If a tenant blocks or changes format, fall back to a "check manually" link in the email and log it in `meta.json`.

## D-003 — Two engines (ACCEPTED 2026-11-02)
Engine A (Python on GitHub Actions, no LLM) collects jobs. Engine B (Claude scheduled task + Apollo connector) finds contacts. Core pipeline stays LLM-free.

## D-004 — Contact data stays private (ACCEPTED 2026-11-02)
Contact names, emails, phones, and LinkedIn URLs never go in the public repo or site — only the morning email/draft and a private Google Sheet.

## D-005 — Morning email before web app (ACCEPTED 2026-11-02)
Build the email (P5) before the UI (P7–P8).

## D-006 — Season year is not class year (ACCEPTED 2026-11-02)
A Summer 2028 internship normally targets 2029 graduates (Lucas's class). Exclude only when a posting explicitly rules out a May 2029 graduate; keep unclear listings flagged.

## D-007 — Public repo (ACCEPTED 2026-11-02)
GitHub Actions is free for standard runners in public repos; GitHub Pages hosts the site. Secrets only in Actions secrets. Risk: scheduled workflows in public repos are disabled after 60 days with no repo activity — verify in P4 that daily data commits count.

## D-008 — Apollo budget (ACCEPTED 2026-11-02)
Apollo account registered with Gmail; shows 210 credits (20 used). Apollo's docs say free accounts need a work email for certain search/enrichment endpoints. Budget 150 reveals/month (~5/day). Test in P6 whether connector search works on a Gmail account; whether credits reset monthly.

## D-009 — Morning email via Gmail SMTP with an app password (ACCEPTED 2026-11-02)
No domain or new service needed, well under the 500/day limit, and Python's standard library can send it. Resend requires a domain you own, which conflicts with $0; Brevo could not be verified. Google discourages app passwords in general. Set up in P5. Details in PLAN section 7.
Sending uses a separate Gmail account used only for sending; Lucas's personal inbox only receives. The app password is created in P5 and stored only in GitHub secrets.

## D-010 — Reconfirm Workday use before P3 (ACCEPTED 2026-11-02: keep D-002, option A)
Workday's site terms (updated 08/13/2026) prohibit scraping and unconsented apps on its "Sites," and use of "Workday APIs" without a separate agreement. They do not say whether customer career sites or the CXS endpoint are covered. D-002 stays in force, but Lucas should reconfirm it knowing this. Options: (A) keep D-002, or (B) treat Workday companies as manual links. Recommendation: A, because the pages are public and use is one polite read per day, with the risk accepted knowingly. P2 uses no Workday code, so nothing is lost by deciding before P3. This is not legal advice.

## D-011 — ATSs without an adapter are `manual` for now (ACCEPTED 2026-11-02)
Oracle Cloud, iCIMS, Avature, Taleo, Paylocity, and UKG companies become "check manually" links, and the true ATS is recorded in `notes`. Revisit by company value after P3; Oracle (Lazard, Grant Thornton) and iCIMS (Principal, Sammons) are the first candidates, subject to checking their docs and terms.

## D-012 — Keyword matching uses word boundaries (ACCEPTED 2026-11-02)
Live boards show "intern" matching "International" and "Internal." `must_be_one_of` and `exclude_keywords` will match whole words or phrases, case-insensitively, in code rather than by changing config values. Real titles from Phase 1 become test fixtures in P2.

## D-013 — Hold community lists (ACCEPTED 2026-11-02)
SPEC allows only openly licensed lists. The one list sampled showed no license on its repo page and focuses on tech roles. Do not use community lists as a data source until a specific list's license is confirmed.

## D-014 — Spring 2027 and Winter 2027 seasons (ACCEPTED 2026-11-02)
Add Spring 2027 and Winter 2027. They fall during Lucas's sophomore spring semester, so they are realistic only near Ames/Des Moines. Include them but score them lower than Summer 2027 and Summer 2028.

## D-015 — Respect SmartRecruiters' robots.txt (ACCEPTED 2026-11-02)
`api.smartrecruiters.com/robots.txt` allows LinkedInBot and disallows every other crawler, even though SmartRecruiters documents a public Posting API. Respect it. RR Donnelley and Northwestern Medicine stay manual links, and no more requests go to that API. The adapter file stays, tested offline but unregistered, so the pipeline cannot call it.

## D-016 — Off-season 2027 listings stay near home (ACCEPTED 2026-11-02)
Spring 2027 and Winter 2027 listings are only kept within 60 miles of home (config: `seasons[].max_miles_from_home`). This makes D-014's "realistic only near Ames/Des Moines" a real limit. A multi-city posting counts by its closest city. If the distance is unknown, the listing is not kept, because it cannot be shown to be within the limit.

## D-017 — Claims and underwriting roles (ACCEPTED 2026-11-02)
Add role keywords "claims adjuster", "claims", and "underwriting intern" under `insurance_risk`.

## D-018 — Program titles without the word "intern" (ACCEPTED 2026-11-02)
A title counts as an internship/program if it contains an internship term, or a season+year pattern (e.g., "Summer 2027", "2028 Summer") with "analyst", "program", "associate program", or "scholar" (config: `program_title_terms`).
Finding when built: William Blair's real "Working in Technology (WiT) ... - Summer 2027" titles have a season and year but none of those words, so this rule does not admit them. Tests record that. Adding "working in technology" to `program_title_terms` would admit them; see STATUS.

## D-019 — Remove BGM Group (ACCEPTED 2026-11-02)
Removed from `config/companies.yaml` because both domains are parked.

## D-020 — Scoring points live in config (ACCEPTED 2026-11-02)
Scoring points move from `scanner/scoring.py` into a `scoring:` block in `config/config.yaml` and `docs/CONFIG.md`. No scoring numbers are hard-coded in code; a test checks this.

## D-021 — Cap for listings with no role match (ACCEPTED 2026-11-02)
Listings with no role-category match stay in `internships.json` but are capped at `scoring.no_role_cap` (default 35), so they never reach the email by default.

## D-022 — Nominatim's robots.txt disallows geocoding (PROPOSED 2026-11-02)
Phase 3 asked for Nominatim geocoding under its usage policy (https://operations.osmfoundation.org/policies/nominatim/, read 2026-11-02). Two findings conflict with that:
- `nominatim.openstreetmap.org/robots.txt` has `User-agent: *` with `Disallow: /search`. The usage policy does not mention robots.txt. SPEC constraint 2 says to respect robots.txt, and D-015 applied that to a documented API.
- The policy treats scheduled scripts as bulk use, strongly discourages periodic requests, and caps them at 4 per minute rather than 1 per second.

So no request has gone to `/search`. The geocoder and its cache are built and tested offline, and `geocoding.enabled` is false. `config/cities.yaml` keeps its approximate coordinates, because they could not be replaced. While geocoding is off, an unlisted city in a nearby state is kept as "Location unknown", and an unlisted city elsewhere or with no state is excluded and logged in `meta.json`.
Options: (A) use a static file instead: the US Census Bureau's Gazetteer lists coordinates for US places, needs no live service, and would be read locally; (B) Lucas decides robots.txt is aimed at crawlers and exempts this one service, which changes SPEC constraint 2 and which D-015 chose not to do; (C) stay as is. Recommendation: A, subject to checking the Census file's terms and adding it for review.

## D-023 — last_seen moves to its own file (PROPOSED 2026-11-02)
Phase 3 asks that `internships.json` change only when listings change. A per-listing `last_seen` date changes for every listing, every day, so it now lives in `data/last_seen.json`, keyed by listing `id`. The SPEC data model still holds once the two files are joined by `id`, which `store.load_listings` does. For P4: decide the "commit only when data changes" check on `internships.json` alone, since `last_seen.json`, `meta.json`, and `companies_status.json` change every run. Trade-off: on a day with no commit, those three files are not saved, so a stored `last_seen` can lag by the days since the last commit.

## D-024 — "filtered" status (PROPOSED 2026-11-02)
Phase 3 adds a status beyond SPEC's `open | possibly_closed | closed`: `filtered`, for a listing still on its board that current config rejects. `filtered_reason` says why. It returns to `open` if config changes back, and it can still close if it leaves the board.
