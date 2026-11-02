# PLAN — Internship Scanner (written in Phase 1, updated in Phase 2, 2026-11-02)
Approved by Lucas. SPEC.md and DECISIONS.md remain the source of truth; if this plan disagrees with them, they win.

"Tested" below means we ran it on 2026-11-02. "Documented" means an official page says so. They are reported separately on purpose (SPEC constraint 5).

## 1. Repo structure
Items marked *(later)* do not exist yet.

```
config/config.yaml          Lucas's settings
config/companies.yaml       Company registry
config/cities.yaml          Local city table for distance checks until P3 geocoding
docs/                       SPEC, STATUS, CONFIG, DECISIONS, SOURCES, PLAN
scanner/                    Python package; run with: python -m scanner run
  __main__.py                 Command line
  pipeline.py                 The runner; isolates failures per company
  config.py                   Loads and validates the YAML files
  http_client.py              Shared client: User-Agent, ≤1 request/second/host, robots.txt, one retry
  adapters/base.py            The common adapter interface
  adapters/greenhouse.py, lever.py, ashby.py, smartrecruiters.py; workday.py, usajobs.py (later)
  normalize.py, location.py, eligibility.py, filtering.py, scoring.py, store.py, text.py
  geocode.py                  (later, P3)
  email/                      (later, P5) HTML email and sending
tests/fixtures/             Saved sample responses, so tests make no network calls
data/                       internships.json, meta.json, companies_status.json; geocache.json (P3)
                            excluded_last_run.json is a local debug report and is not committed
.github/workflows/          (later, P4) Daily and manual runs
web/                        (later, P7) Static site
```

## 2. Config schema
`config/config.yaml` is an exact copy of the block in docs/CONFIG.md, so that file defines the values.

| Key | Type | Used for |
|---|---|---|
| `profile` | `grad_date`, `degree`, `school` (strings) | Eligibility |
| `home`, `radius_miles` | city/state, integer | Distance filter |
| `target_areas` | list of `name`, `center`, `radius_miles` | Always-included areas |
| `include_whole_states` | list of state codes | Always-included states |
| `remote` | `include`, `exclude`, or `separate` | Remote handling |
| `seasons` | list of strings | Season filter |
| `role_categories` | map of category to keyword list | Role matching and scoring |
| `must_be_one_of` | list of strings | At least one must match |
| `exclude_keywords` | list of strings | Disqualifying terms |
| `eligibility.exclude_if_restricted_to_grad_years` | list of years | D-006 |
| `status` | `possibly_closed_after_missed_runs`, `closed_after_missed_runs` | Closing logic (N, M) |
| `new_badge_days` | integer | "New" window (X) |
| `email` | `min_score`, `max_new`, `max_top_open`, `deadline_window_days`, `areas`, `seasons` | Email filters |
| `contacts` | budget and priority settings | Engine B only |

`config/companies.yaml` holds a top-level `companies:` list. Each entry has `name`, `ats`, `board`, `cities`, `priority`, and `notes`.
- `ats`: `greenhouse`, `lever`, `ashby`, `smartrecruiters`, `workday`, or `manual`
- `board`: a slug, a Workday career-site URL, or a careers URL when `manual`
- `priority`: 1 to 3

The loader will reject unknown keys and bad values with a clear message. No setting is hard-coded elsewhere.

## 3. Data model
**`data/internships.json`** holds a list of listings with the fields in SPEC "DATA MODEL": `id`, `company_id`, `title`, `company`, `ats`, `location_raw`, `city`, `state`, `country`, `lat`, `lng`, `is_remote`, `sources[]`, `apply_url`, `date_posted`, `deadline`, `first_seen`, `last_seen`, `status`, `season`, `role_category`, `eligibility{status, reason}`, `relevance_score`, `match_reasons[]`, `description_snippet`, `recurring`, `last_known_open`.

Rules: `date_posted` and `deadline` are null unless the source states them. Listings are never deleted.

Added for the closing logic: `missed_runs` (integer), the count of consecutive runs a listing was absent. **A failed fetch must not count as a miss**; otherwise one outage would mark a company's listings closed.

**`data/meta.json`** describes one run: `run_started`, `run_finished`, `adapters[]` (`company`, `ats`, `ok`, `listings_fetched`, `error`, `fallback_link`), and totals.

**`data/companies_status.json`** has one entry per company ever checked, never deleted: `company_id`, `last_checked`, `open_intern_count`, `last_intern_posting_seen`, `fetch_health`.

No contact data appears in any of these (D-004).

## 4. Adapter interface
There is one interface for every source (`scanner/adapters/base.py`). `fetch` returns normalized listings, built with `normalize.new_listing`, or raises.

```python
class Adapter:
    name = ""                                      # "greenhouse", "lever", ...
    def fetch(self, company, wants_detail=None):
        """Return every job on the company's board, or raise."""
```

`wants_detail` lets a source that needs one request per description ask only for relevant jobs. The runner (`scanner/pipeline.py`) owns failure handling, so an adapter cannot break a run: it catches any error per company, records it in `meta.json`, and continues.

- `manual` companies make no network call. They become "check manually" links in the email.
- When a Workday company fails, its careers link also moves to the "check manually" section (D-002).
- Adapters only fetch and shape data. Filtering, scoring, and dedupe happen afterwards, in one place.

## 5. Verified source table
Checked 2026-11-02. "Live test" is one small unauthenticated request. **Doc pages were read for API details; separate company-wide terms were reviewed only where the ToS column says so.**

**robots.txt, added in Phase 2 (Phase 1 did not check API hosts):** `boards-api.greenhouse.io` disallows only `/embed/`. `api.lever.co` allows all with `Crawl-delay: 1`. `api.ashbyhq.com` returned 401, which RFC 9309 treats as no rules. **`api.smartrecruiters.com` allows LinkedInBot and disallows everyone else, so the HTTP client blocks our calls (D-015).** Its "Live test" result below came from requests made before this was known.

| Source | Endpoint | Auth | Rate limits | ToS notes | Doc URL | Live test | Rec |
|---|---|---|---|---|---|---|---|
| Greenhouse | `GET boards-api.greenhouse.io/v1/boards/{board_token}/jobs` (`?content=true` for descriptions) | None for GET (documented) | Not stated | None on doc page. Overall terms UNVERIFIED | https://docs.greenhouse.io/job-board.html (old developers.greenhouse.io URL redirects here) | 200; 3 registry boards | USE |
| Lever | `GET api.lever.co/v0/postings/{site}?mode=json` (`skip`, `limit`; EU host exists) | None stated for GET; published postings are "publicly viewable" | Not stated for GET. The only documented limit, 2 per second, is for application POSTs | None on doc page. Overall terms UNVERIFIED | https://github.com/lever/postings-api | 200 on `leverdemo`; no registry company uses it yet | USE |
| Ashby | `GET api.ashbyhq.com/posting-api/job-board/{name}` (`includeCompensation=true` optional) | Not stated | Not stated | None on doc page. Overall terms UNVERIFIED | https://developers.ashbyhq.com/docs/public-job-posting-api | 200 on `ashby`; no registry company uses it yet | USE, low priority |
| SmartRecruiters | `/postings` and `/postings/{postingId}` documented. **Full URL `api.smartrecruiters.com/v1/companies/{id}/postings` comes from our test, not the docs read: UNVERIFIED** | Docs: API key or OAuth supported; a special scope is needed only for internal postings. No-auth public access not stated, but worked in testing | UNVERIFIED: a Rate Limiting guide exists; contents not retrieved | None on doc page. Overall terms UNVERIFIED | https://developers.smartrecruiters.com/docs/posting-api ; https://developers.smartrecruiters.com/docs/endpoints | 200 with no credentials; 2 registry boards | **BLOCKED by robots.txt** pending D-015; adapter built and tested offline only |
| Workday CXS | `POST {tenant}.wdN.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs` with JSON `appliedFacets`, `limit`, `offset`, `searchText` | None in testing | **UNVERIFIED** (no public documentation; use D-002's ≤1 per second) | **See risk R1.** Workday site terms prohibit scraping and unconsented apps on its "Sites"; they do not say whether customer career sites are covered | **Endpoint: UNVERIFIED, no official doc.** Terms: https://www.workday.com/en-us/legal/site-terms.html | 200 and robots.txt allows the path on all 16 registry boards | USE politely under D-002, pending D-010 |
| USAJOBS | `GET data.usajobs.gov/api/Search` (`HiringPath=student` or `graduates`) | Required headers: `Host`, `User-Agent` (**the email used to request the key**), `Authorization-Key`. Whether the key is free: UNVERIFIED on the pages read | 10,000 rows per query, 500 per page; OPM may add limits without notice | Public Data may be reused. Encourages naming USAJOBS as the source and disclosing no OPM endorsement; link to the official posting; do not circumvent limits or share credentials | https://developer.usajobs.gov/api-reference/get-api-search ; /guides/authentication ; /guides/rate-limiting ; /guides/terms-of-service (same host) | 401 without key, as expected. Search itself untested | LATER |
| Oracle Cloud, iCIMS, Jobvite, Avature, Taleo, Paylocity, UKG | Varies | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED: not researched | Not tested | LATER; `manual` for now (D-011) |
| Community internship lists | Varies | None | N/A | Sample only: SimplifyJobs showed no license on its repo page and focuses on tech roles. Other lists UNVERIFIED | https://github.com/SimplifyJobs/Summer2026-Internships (redirected content describes Summer 2027) | Page read only | HOLD (D-013) |
| Google `site:` search | None | N/A | N/A | Prohibited per D-001. Not re-checked in P1: UNVERIFIED | UNVERIFIED | Not used | SKIP |
| LinkedIn, Indeed, Handshake, Glassdoor | None | N/A | N/A | Prohibited per SPEC. Not re-checked in P1: UNVERIFIED | UNVERIFIED | Not used | SKIP |

**What "Not stated" means:** the page we read gave no limit. It does not mean unlimited. Every adapter stays at ≤1 request per second regardless.

## 6. Company registry result
44 companies: the 19 seeds plus 25 additions. **21 have confirmed boards** (16 Workday, 3 Greenhouse, 2 SmartRecruiters) and 23 are `manual`. As of P2, only the 3 Greenhouse boards are fetched live: Workday arrives in P3, and SmartRecruiters is blocked by robots.txt (D-015).

- All ATS hints in STATUS.md that could be checked held up. Pella's Oracle hint could not be confirmed.
- American Equity (Greenhouse) and William Blair (Greenhouse) offer the cleanest official feeds among target firms.
- Cities are labeled "observed" or "expected" in each entry's notes. Several additions are **not yet confirmed to hire interns in a target city**, because their pages were blocked or only the first 20 results were sampled. P3's first full run will settle this for those with live boards.

## 7. Morning email method
**Recommendation: Gmail SMTP with an app password (D-009).** Set up in P5, not now.

| | Gmail SMTP + app password | Resend free | Brevo free |
|---|---|---|---|
| Cost | $0 | $0 | UNVERIFIED |
| Limit | 500 emails/day (documented) | 100/day, 3,000/month | UNVERIFIED |
| Own domain needed | No | **Yes**, which usually costs money and conflicts with $0 | UNVERIFIED |
| Card required | No card involved with a Gmail account | Not stated | UNVERIFIED |
| Fit for 2 emails/day to Lucas | Yes | Blocked by domain requirement | Unknown |

Why Gmail: Lucas already has it, no domain is needed, and one or two emails a day is far under the limit. Python's standard library can send it, so no dependency is added.

The trade-off, stated plainly:
- Google says app passwords "aren't recommended and are unnecessary in most cases," because an app password gives access to the account. It suits an unattended script, which cannot do "Sign in with Google," but it must be protected.
- Mitigation: it lives only in GitHub Actions secrets, and it can be revoked at any time. **A separate Gmail account just for sending limits the damage if the password ever leaked.** That is optional, and Lucas would create it himself.
- It needs 2-Step Verification on, and it is unavailable if that uses security keys only or the account has Advanced Protection.
- Secrets are not passed to workflows triggered from forks (documented), so strangers cannot obtain them through a fork.

Sources:
- App passwords: https://support.google.com/mail/answer/185833
- Sending limit: https://support.google.com/mail/answer/22839
- SMTP host and ports (`smtp.gmail.com`, 465 SSL or 587 TLS): https://knowledge.workspace.google.com/admin/gmail/send-email-from-a-printer-scanner-or-app. **This page is written for Workspace admins; confirmation for personal accounts is UNVERIFIED and will be tested in P5.**
- Resend: https://resend.com/pricing and https://resend.com/docs/dashboard/domains/introduction
- GitHub secrets: https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets
- Brevo's pricing page returned only a title and its help center returned 403, so everything about Brevo is UNVERIFIED.

## 8. Architecture decisions and trade-offs
| Decision | Why | Trade-off |
|---|---|---|
| JSON files in git, not a database (SPEC) | $0, simple, full history, works with GitHub Pages | Files grow; large diffs each day. Acceptable at hundreds to thousands of listings |
| Fetch the whole board, then filter locally | Workday and SmartRecruiters text search are fuzzy; one logic path for all sources | More requests on big boards: at 20 per page, RSM's ~650 jobs takes ~33 requests, ~35 seconds |
| Runner catches all adapter errors | Meets "one failing source never breaks the run" | A broad catch can hide bugs, so every failure must surface in `meta.json` and the email's health line |
| Word-boundary keyword matching (D-012) | Plain substring matching lets "intern" match "International" and "Internal" | Slightly more logic and test fixtures |
| `manual` for ATSs without adapters (D-011) | Honest coverage, no scraping of unsupported sites | 23 of 44 companies are links, not listings, until more adapters exist |
| Personal email kept out of User-Agent | The repo is public; SPEC constraint 3 | Our User-Agent names the project URL. USAJOBS requires an email, so that value will come from a secret |
| Standard-library SMTP and few dependencies | SPEC working rules | Slightly more code than a vendor SDK |
| Build P2 with every non-Workday adapter | Delays Workday until P3 | Only 3 boards run live in P2, so results are thin until then |
| Store only listings that pass the filters | Keeps the public database to Lucas's targets | A listing excluded today is not in history if config widens later, though the next run picks it up if still posted. `excluded_last_run.json` holds the rest locally |
| Non-finance internships are kept, scored low | SPEC filters on internship terms, location, season, and eligibility; relevance is the score's job | The database includes roles like IT interns; the email's `min_score` keeps them out of the morning email |
| Scoring point values live in `scoring.py` | Lucas asked to keep config otherwise identical in P2 | Tension with "no value hard-coded"; move to config when calibrated in QA if wanted |

## 9. Risks
| # | Risk | Severity | Response |
|---|---|---|---|
| R1 | **Workday terms.** Updated 08/13/2026, they prohibit scraping and unconsented apps on "Sites," and "Workday APIs" without a separate agreement. "Sites" is defined around www.workday.com and associated pages and includes "the Workday APIs." They do not say whether customer career sites or the CXS endpoint are covered. This is a plain reading, not legal advice | High, because 16 of 21 live boards rely on it | D-002 stands until Lucas decides. D-010 asks him to reconfirm before P3. No Workday code before then. Fallback: manual links |
| R2 | Workday's undocumented endpoint could change or block us | Medium | D-002 fallback; isolated adapter; `meta.json` logging |
| R3 | False matches, e.g. "Internal Audit" or "International Tax Senior" passing `must_be_one_of` | Medium; seen live | D-012, plus fixtures from those real titles |
| R4 | Off-season missed: "Spring 2027" and "Winter 2027" internships exist on live boards (Corient, UHY) | Resolved | Added with lower weights (D-014) |
| R5 | Shared boards return irrelevant locations: the Federal Reserve board spans multiple Reserve Banks | Low | Location filter handles it; the `cities` field is informational |
| R6 | GitHub schedule can be delayed or dropped under load; it is disabled after 60 days with no repo activity, and the docs do not define "activity" | Medium | Manual trigger; verify in P4 per D-007. Engine B must handle Engine A running late |
| R7 | Leaked app password | Medium | Secrets only, secret scan, revocable, optional dedicated account |
| R8 | **Personal email in git commit history.** Existing commit 820b3ab records Lucas's Gmail as author | Medium | His git setup now uses GitHub's private noreply address, so new commits are safe. That one commit stays public unless Lucas chooses to rewrite it (see STATUS) |
| R9 | Company careers pages block our identified requests (Bankers Trust, Wells Fargo, H&R Block, Workiva, Ames National returned 403) | Low | Respect the block; `manual` |
| R10 | Rate limits are undocumented for most sources | Low | ≤1 per second per host, once daily, back off on 429 |
| R11 | SPEC says Engine B "sends or drafts" email, while constraint 7 says outreach is drafts only | Low | Reading it as: the email goes only to Lucas, and outreach stays drafts. To confirm in P6 |
| R12 | Registry goes stale as companies change ATS | Low | Failures show in `fetch_health`; discovery list per SPEC |
| R13 | SmartRecruiters robots.txt blocks 2 companies | Medium | D-015; they appear as blocked with a "check manually" link |
| R14 | `config/cities.yaml` is incomplete and its coordinates are approximate, written from memory. A listing in a missing city outside Iowa is excluded | Medium | Logged under `unresolved_locations` in `meta.json`; geocoding in P3 replaces this |
| R15 | Job descriptions could contain a person's name or contact details | Medium | Only a scrubbed snippet is stored: emails, phones, and profile links are removed, and sentences inviting contact are dropped. A bare name in other text would not be caught, so the QA PII scan matters |
| R16 | P3's closing logic must tell "gone from the board" apart from "filtered out after a config change" and from a failed fetch | Medium | Handle explicitly when building status transitions in P3 |
