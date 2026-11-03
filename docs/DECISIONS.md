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

## D-022 — Coordinates come from the Census Gazetteer (ACCEPTED 2026-11-02)
`nominatim.openstreetmap.org/robots.txt` disallows `/search` for all crawlers, and its usage policy (https://operations.osmfoundation.org/policies/nominatim/) strongly discourages periodic requests. So Nominatim stays off. Coordinates come from the U.S. Census Bureau's Gazetteer places file, downloaded once and stored in `data/reference/` with its source URL and year. City and state are looked up offline.
`config/cities.yaml` keeps city and state names only, for postings that give no state. Its memory-based coordinates are gone.
A listing with an unknown distance never passes a distance check. It stays as "Location unknown" only if it is in Iowa or names a target metro. Anything else is excluded with the reason "location unknown". The geocoder code stays, tested offline and switched off.

## D-023 — last_seen has its own file (ACCEPTED 2026-11-02)
A per-listing `last_seen` date changes for every listing, every day, so it lives in `data/last_seen.json`, keyed by listing `id`. The SPEC data model still holds once the two files are joined, which `store.load_listings` does. The automation decides whether to commit from `internships.json` alone.
Trade-off: on a day with no commit, `last_seen.json`, `meta.json`, and `companies_status.json` are not saved, so they can lag by the days since the last commit.

## D-024 — "filtered" status (ACCEPTED 2026-11-02)
A status beyond SPEC's `open | possibly_closed | closed`, for a listing still on its board that current config rejects. `filtered_reason` says why. It returns to `open` if config changes back, and it can still close if it leaves the board.

## D-025 — Larger Workday cap, and check a listing before counting it missing (ACCEPTED 2026-11-02)
`workday.max_results_per_term` rises from 200 to 500. Before a Workday listing counts as missing, its own posting is requested.
- Open (200, and not marked closed): not a miss. Its count resets, and a possibly_closed listing returns to open.
- Gone (403, 404, 410, or `posted`/`canApply` false): a miss, even when the search hit its cap. So listings on big boards can now close.
- Anything else (server error, timeout, unexpected reply): a failed check, never a miss.
Built this way because of a live test on 2026-11-02: two postings taken down from Vermeer and EMC answered 403, a made-up path answered 404, and open postings on the same hosts answered 200. So 403 counts as gone only in this check, right after the same host answered that run's search. Everywhere else a 403 still means blocked.
Limits: the cap is per search term, as the setting's name says, not per company in total. Greenhouse, Lever, and Ashby have no such check, because they return the whole board, so the board is already the proof.

## D-026 — William Blair "Working in Technology" titles stay excluded (ACCEPTED 2026-11-02)
No change. They have a season and year, but none of the `program_title_terms`.

## D-027 — "Federal Reserve System" (ACCEPTED 2026-11-02)
Renamed from "Federal Reserve Bank of Kansas City", because the board is shared by the whole system. Each listing's city comes from its posting. `company_id` becomes `federal-reserve-system`, and stored data was moved to it.

## D-028 — Wells Fargo stays manual (ACCEPTED 2026-11-02)
No more requests to any Wells Fargo host.

## D-029 — Remote listings tied to Iowa get their own section (ACCEPTED 2026-11-02)
`remote: "separate"` and `remote_allowed_states: ["IA"]`. A remote listing tied to Iowa, such as "Iowa - Work From Home", is kept with `is_remote: true` and the tag `remote_iowa` in a new `tags` list, so the email and UI can show it separately. All other remote listings stay excluded. It scores `whole_state_or_home_radius` for location.

## D-030 — Commit 820b3ab is not rewritten (ACCEPTED 2026-11-02)
That old commit keeps its author details.

## Empty-response guard (ACCEPTED 2026-11-02)
For any adapter, a company that returns 0 jobs after having at least `status.empty_response_min_open` (3) open listings counts as a failed fetch. No misses are counted, and it is logged as an error and shown as a warning.

## D-033 — P5 email behavior choices (ACCEPTED 2026-11-03)
Confirms the P5 build's choices:
- Remote — Iowa listings appear only in their own section. They get a NEW badge and count in the subject. The areas filter doesn't apply to them; min_score and seasons do.
- Top open matches excludes listings already shown under New.
- `email.areas` accepts target-area names and/or state codes. `email.seasons` accepts season names plus "Not stated" (most listings state no season).
- Gmail SMTP uses port 587 with STARTTLS (Google support 7104828).
- The failure email fires on any failed step and names the step.
- The data commit runs whenever the scan succeeds, even if the email fails, so no data is lost.
- The manual-links block stays as built for now. A follow-up will add an `email.max_manual` cap.
Spec impact: none beyond 01_SPEC v2.2's MORNING EMAIL section (already 6 sections).
Built in P5.1: `email.max_manual` (10). Failed-today companies come first, then priority 1, 2, 3, alphabetical within each group, then "…and N more manual companies."

## D-034 — Email focuses on banking; insurance/actuarial stay in the database only (ACCEPTED 2026-11-03)
Lucas's goal is investment banking, so actuarial, insurance and claims roles are noise in the email.
- The scanner keeps collecting and scoring the `insurance_risk` category, so those listings stay in `data/internships.json` and will show in the web app.
- The email hides listings whose ONLY role match is `insurance_risk`, via a config list (proposed key `email.exclude_role_categories: ["insurance_risk"]`, final name set in P5.1).
- A listing that also matches banking, IB, corporate finance, investments or accounting still appears.
- Bank risk roles: confirm in P5.1 how bank credit or market-risk titles are categorized, so they aren't hidden by mistake.
Spec impact: MORNING EMAIL filters gain a role-category exclusion. 02_CONFIG `email:` block gains the key.
Built in P5.1: the key is `email.exclude_role_categories`. Only categories matched in the title count; `early_career` is a signal, not a role, so it doesn't keep an insurance listing in the email. "credit risk" and "market risk" were added to `role_categories.banking`, which is listed before `insurance_risk`, so such titles get `role_category: banking` and are shown. The health line says "{n} insurance-only listings hidden."

## D-035 — IB coverage is the top scanner priority (ACCEPTED 2026-11-03)
Lucas wants many more investment banking opportunities. This is the first work after P5.1 and comes before P6 contacts.
- Research which ATS each IB-relevant firm uses: currently-manual Lazard, Piper Sandler, Baird, Stifel and Mesirow, plus new IB firms in or near the target areas (Chicago, Kansas City, Des Moines, Dubuque).
- Use only legitimate public feeds (D-001, D-002, D-015).
- Add the firms that have feeds. The rest stay manual links, grouped at the top of the manual list.
Spec impact: COMPANY REGISTRY grows. A new phase P5.2 (IB coverage) is inserted before P6.

Note (P5.2): the P5.2 build prompt cites D-036 for the P5.1 email-polish items (manual-links order, season-word rule), but no D-036 was ever written to this file. Those items are described by D-033's "Built in P5.1" line and docs/reports/P5_1_REPORT.md. The number is left unused so later entries stay as numbered in the P5.2 report.

## D-037 — Company tags and IB-first manual links (PROPOSED 2026-11-03, P5.2)
`config/companies.yaml` entries may carry an optional `tags` list of words. Every firm whose core business is investment banking or deal advisory is tagged `ib`, and has priority 1. That is 16 firms: Baird, D.A. Davidson, Fireclay Partners, Guggenheim Partners, Houlihan Lokey, Jefferies, Kroll, Lazard, Lincoln International, Mesirow, Moelis & Company, Piper Sandler, Raymond James, Stifel, Stout and William Blair. Universal banks with IB arms (Citi, BMO, CIBC and others) aren't tagged, because their manual or live status doesn't depend on IB.
`email.manual_first_tags: ["ib"]` orders the manual list:
1. failed today;
2. always-manual companies with a listed tag;
3. the other always-manual companies.

Within each group: priority, then alphabetical. Then `max_manual` (10) and "…and N more." The email gives the tagged group its own line, "IB firms, no feed:". `[]` restores exactly the P5.1 order, and a test checks that.
Trade-off: there are exactly 10 IB-tagged manual firms today, so on a day with failures, some IB links move into "…and N more."

## D-038 — Season and year pair anywhere in a title (PROPOSED 2026-11-03, P5.2)
One season word and one year anywhere in a title now pair, when the year is 2026–2030. "2028 PMCF Investment Banking Summer Analyst" becomes Summer 2028. Side by side, or up to 2 words apart, any year still pairs, as before.
A title naming two different season words ("Fall 2027/Winter 2028") or two different years ("Summer 2027 … 2028 graduates") gets no season. It also doesn't take one from the description, because that would still be a guess. The score's reason says why: "season: not stated (title names more than one season (Fall, Winter), so none was picked)". A title with any season word is still never year-only.
Effect on stored data at the time of the change: two stored listings change. Plante Moran's IB Summer Analyst gets +25 instead of +8 for its season, and GCM Grosvenor "2027 IT-Product & Strategy Summer Intern" goes 18 → 35, held by `no_role_cap`. Among the last run's excluded listings, 79 titles gain a season (58 Citigroup, 14 Marsh McLennan, 4 Optiver, and 1 each from Plante Moran, U.S. Bank and UHY) and 11 lose one (9 RSM "Fall 2027/Winter 2028", 1 Jump Trading "Winter/Spring 2027", 1 Citigroup title naming 2026 and 2027). A check of D-018's program-title rule against every one of these titles found none whose kept or excluded status changes.

## D-039 — P5.2 feed and manual changes (PROPOSED 2026-11-03)
Verified from each firm's own careers page, one endpoint request each:
- Now live: Piper Sandler (was manual) on Workday `pipersandler.wd501/Piper_Sandler_Careers`; Stout on Workday `stout.wd5/Stout-Student-Careers`; Lincoln International on Greenhouse `lincolninternational`.
- Manual, no adapter for their ATS: Lazard (Oracle), Stifel (iCIMS), Jefferies (TalentLink), Mesirow (UKG/UltiPro), Fireclay Partners (Breezy HR), Moelis & Company (campus on TalentLink; its Workday site lists experienced roles only, with no internships).
- Manual, blocked or unreadable: Houlihan Lokey (Incapsula bot check), D.A. Davidson (403), Kroll (script-filled TalentBrew site, ATS unconfirmed).
- Baird: kept manual without a new request. Its careers host returned 403 on 2026-11-02, and the `rwbaird` Workday hint didn't come from a company page. **Lucas to decide:** allow one fresh request to www.rwbaird.com/careers/ to look for the ATS link (still one identified request, no header changes), or leave it manual.

## D-040 — P5.2 scope calls (PROPOSED 2026-11-03)
- Five Elms Capital is not added, because it's private equity only, outside D-035. It can be added later if Lucas approves it.
- Adapter candidates for a later decision, ordered by how many IB firms each would unlock: TalentLink (Jefferies, Moelis), then Oracle Cloud (Lazard, plus Grant Thornton per D-011), iCIMS (Stifel, plus Principal and Sammons per D-011), UKG (Mesirow) and Breezy HR (Fireclay). Each would need its docs, terms and robots.txt checked first.
