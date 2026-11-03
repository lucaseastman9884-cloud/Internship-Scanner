# P5.2 REPORT — IB coverage (D-035)
Built 2026-11-03 on branch `p5-2-ib-coverage`. Not pushed. No email was sent.

## Summary
| Check | Result | Detail |
|---|---|---|
| pytest, Python 3.9.6 | **Pass** | 607 passed (564 existing + 43 new) |
| pytest, Python 3.12.16, DeprecationWarnings as errors | **Pass** | 607 passed |
| actionlint | **Not run** | The download of the actionlint binary was refused by this session's permission settings. No workflow file changed in P5.2 (`git diff main -- .github` is empty), so P5.1's result (0 errors) still describes the same file. Command for Lucas is in section 3 |
| Live verification | **Done** | 47 logged requests, at least 1.085 s apart per host |
| Full run on real data, email dry run | **Done** | 31.6 minutes locally; 3 new live firms add about 14 requests |
| Secret and PII scan | **Pass** | Nothing found |

**Note on D-036:** the build prompt cites D-036, but DECISIONS.md has no D-036. The items it names (manual-links order, "a season word means not year-only") are P5.1 behavior, described in D-033 and the P5.1 report. I kept that behavior and left the number unused, so the new entries start at D-037 as the prompt asked.

## 1. Files changed
- `scanner/normalize.py`: one season word and one 2026–2030 year anywhere in a title now pair. Two seasons or two years leave the season unstated, with a reason.
- `scanner/scoring.py`: the "season: not stated" reason now says why when a title named two seasons or years. Points are unchanged.
- `scanner/config.py`: validates the optional `tags` on companies and the new `email.manual_first_tags`. Every loaded company gets a `tags` list.
- `scanner/email_report.py`: manual-list order is now failed → tagged → the rest. Tagged firms get their own "IB firms, no feed:" line in HTML and an "(IB)" marker in text.
- `config/config.yaml` and its copy in `docs/CONFIG.md`: `email.manual_first_tags: ["ib"]`, plus the docs for it and for `tags`.
- `config/companies.yaml`: 8 new firms, 8 updated entries, and `tags` documented in the header.
- `tests/test_p5_2.py` (new): registry, config, ordering, season and isolation tests.
- `docs/DECISIONS.md`: proposed D-037 to D-040, plus a note on the missing D-036.
- `docs/PLAN.md`: registry fields and counts.
- `docs/STATUS.md`: replaced (section 7).
- This report.
- Data: none. The full run wrote to a scratch copy of `data/`, so the tracked files are untouched and can't conflict with the bot's daily commits.

## 2. Firm verification table
Every request went through the pipeline's own `HttpClient`: same User-Agent, robots.txt checked first, at least 1 second per host. The careers page was always read first, and ATS hosts came only from links on it. Date for every row: 2026-11-03.

| Firm | Careers page checked | ATS + host | robots.txt | HTTP status (endpoint) | Open interns* | Action |
|---|---|---|---|---|---|---|
| Piper Sandler | www.pipersandler.com/careers (200) | Workday, pipersandler.wd501 / Piper_Sandler_Careers (link inside a urldefense.com wrapper) | Allows | 200, 39 results for "intern" | 5 | **Added** (was manual) |
| Stout | www.stout.com/en/careers (200) | Workday, stout.wd5: Stout-Careers, Stout-Experienced-Careers, Stout-Student-Careers | Allows | 200 for Student (5) and Careers (15); same 3 interns | 3 | **Added** (Student site) |
| Lincoln International | /careers/ 404 → home page → /careers-and-culture/careers/campus-early-careers/ (200) | Greenhouse, `lincolninternational` (also `switzerlandlincolninternational`, not added) | Allows (disallows only /embed/) | 200, 42 jobs | 10 | **Added** |
| Moelis & Company | www.moelis.com/careers/ (200) | Campus: TalentLink (moelis-careers.tal.net). Experienced: Workday moelis.wd1 / Experienced-Hires | Workday allows; tal.net not requested | 200, 17 results, 0 internships | 0 on Workday | **Manual** (campus needs TalentLink) |
| Baird | www.rwbaird.com/careers/ — **not requested** | Unconfirmed (hint `rwbaird` wd1 is unverified) | — | — (403 on 2026-11-02) | — | **Manual / blocked**. See D-039 |
| Houlihan Lokey | hl.com/careers/ (200, but an Incapsula bot-check page) | Unconfirmed | Allows | — | — | **Manual / blocked** |
| D.A. Davidson | www.dadavidson.com/careers (403) | Unconfirmed | robots.txt itself answered 403, which RFC 9309 treats as "no rules", so the page was requested once | 403 | — | **Manual / blocked** |
| Fireclay Partners | fireclaypartners.com/careers/ (200) | Breezy HR (fireclay-partners.breezy.hr), no adapter | Not requested | — | 1 seen on page ("IB Analyst, Current Student – Remote") | **Manual** |
| Lazard | www.lazard.com/careers/ (200) | Oracle Cloud, icbpjb.fa.ocs.oraclecloud.com (Student and Professional sites) | Not requested | — | — | **Manual** |
| Stifel | www.stifel.com/careers (200) | iCIMS, careers-stifel.icims.com | Not requested | — | — | **Manual** |
| Jefferies | www.jefferies.com/careers/ (200) | TalentLink, jefferies.tal.net | Not requested | — | — | **Manual** |
| Mesirow | www.mesirow.com/careers (200) | UKG / UltiPro, recruiting2.ultipro.com | Not requested | — | — | **Manual** |
| Kroll | /en/careers 404 → www.kroll.com/en → careers.kroll.com/en → early-careers listing (all 200) | TalentBrew front end; listing filled in by script, ATS unconfirmed | Allows | — | — | **Manual** |

\* "Open interns" for live boards is `open_intern_count` from the full run. For Moelis it's from the single verification request.

**Log summary** (method, status, host and path; no headers):
```
17:54:07 GET 200 www.pipersandler.com/robots.txt        17:54:08 GET 200 www.pipersandler.com/careers
17:54:09 GET 200 hl.com/robots.txt                      17:54:10 GET 200 hl.com/careers/   (Incapsula page, 212 bytes)
17:54:11 GET 200 www.moelis.com/robots.txt              17:54:21 GET 200 www.moelis.com/careers/
17:54:21 GET 200 www.stout.com/robots.txt               17:54:23 GET 200 www.stout.com/en/careers
17:54:23 GET 200 www.lincolninternational.com/robots.txt 17:54:24 GET 404 www.lincolninternational.com/careers/
17:54:25 GET 403 www.dadavidson.com/robots.txt          17:54:26 GET 403 www.dadavidson.com/careers
17:54:26 GET 200 www.fireclaypartners.com/robots.txt    17:54:28 GET 200 www.fireclaypartners.com/
17:54:28 GET 200 www.stifel.com/robots.txt              17:54:29 GET 200 www.stifel.com/careers
17:54:30 GET 200 www.jefferies.com/robots.txt           17:54:31 GET 200 www.jefferies.com/careers/
17:54:31 GET 200 www.mesirow.com/robots.txt             17:54:32 GET 200 www.mesirow.com/careers
17:54:33 GET 200 www.kroll.com/robots.txt               17:54:34 GET 404 www.kroll.com/en/careers
17:54:35 GET 200 www.lazard.com/robots.txt              17:54:36 GET 200 www.lazard.com/careers/
17:55:01 GET 200 fireclaypartners.com/robots.txt        17:55:02 GET 200 fireclaypartners.com/careers/
17:55:04 GET 200 www.lincolninternational.com/robots.txt 17:55:05 GET 200 www.lincolninternational.com/
17:55:05 GET 200 www.kroll.com/robots.txt               17:55:07 GET 200 www.kroll.com/en
17:55:13 GET 200 www.lincolninternational.com/robots.txt 17:55:14 GET 200 .../careers-and-culture/careers/
17:55:15 GET 200 careers.kroll.com/robots.txt           17:55:17 GET 200 careers.kroll.com/en
17:55:40 GET 200 www.lincolninternational.com/robots.txt 17:55:41 GET 200 .../careers/campus-early-careers/
17:55:42 GET 200 careers.kroll.com/robots.txt           17:55:43 GET 200 careers.kroll.com/en/listing-page
17:56:08 GET 200 pipersandler.wd501.myworkdayjobs.com/robots.txt  17:56:09 POST 200 /wday/cxs/pipersandler/Piper_Sandler_Careers/jobs
17:56:10 GET 200 moelis.wd1.myworkdayjobs.com/robots.txt          17:56:11 POST 200 /wday/cxs/moelis/Experienced-Hires/jobs
17:56:12 GET 200 stout.wd5.myworkdayjobs.com/robots.txt           17:56:13 POST 200 /wday/cxs/stout/Stout-Student-Careers/jobs
                                                                  17:56:15 POST 200 /wday/cxs/stout/Stout-Careers/jobs
17:56:16 GET 200 boards-api.greenhouse.io/robots.txt              17:56:17 GET 200 /v1/boards/lincolninternational/jobs
47 requests (UTC, 2026-11-03). Smallest gap between two requests to one host: 1.085 s.
```
Departures from "exactly one request", stated plainly:
- Stout got two endpoint requests, one per site, because the prompt asked for both sites to be checked.
- Lincoln and Kroll took several page requests to find the careers link, each on the firm's own site.
- robots.txt was read again each time the helper script started, so Lincoln shows 4 robots reads.
- D.A. Davidson got 2 requests: robots.txt answered 403, the client treated that as "no rules" (RFC 9309), and the careers page then answered 403. Nothing more was sent to that host.
- No request went to any Oracle, iCIMS, TalentLink, UKG or Breezy host.

## 3. Tests run
```
.venv/bin/python -m pytest -q                                          # Python 3.9.6  → 607 passed in 7.7s
<scratchpad>/v312/bin/python -W error::DeprecationWarning -m pytest -q -p no:cacheprovider   # Python 3.12.16 → 607 passed in 5.9s
```
actionlint was not run (see Summary). To run it yourself after installing it (`brew install actionlint`): `actionlint .github/workflows/*.yml`.

New tests in `tests/test_p5_2.py` (43), by acceptance test:
- **2. Registry:** every entry has the required fields, a valid `ats` and priority 1–3; `tags` is a list of strings when present. The real registry loads (114 companies). The new firms use the verified sources, and all 16 IB-tagged firms have priority 1. Bad tags are rejected (5 cases); `tags` is optional; a misspelled `tag` key is rejected.
- **Config:** `manual_first_tags` is present; bad values (4 cases) and a missing key are rejected.
- **3. Manual order:**
  - failed → IB-tagged → priority 1, 2, 3;
  - an IB firm that failed today is listed with the failures;
  - the cap of 10 gives "…and 40 more" and renders the IB line;
  - `manual_first_tags: []` matches a copy of the P5.1 sort, at caps 10 and 100.
- **4. Season:** 16 title cases, including every case the prompt listed:
  - "2028 PMCF Investment Banking Summer Analyst" → Summer 2028;
  - "Summer 2028 Analyst" → Summer 2028;
  - "2028 Analyst Program" → season_year 2028 and season "Not stated";
  - "2027 Summer / 2028 Winter Program" → Not stated.

  Also tested: the conflict reason appears in `match_reasons`; a conflicting title doesn't take a season from its description; the Plante Moran title gets +25. All P5.1 season fixtures pass unchanged.
- **5. Isolation:** a new Workday IB firm answering 403 becomes `manual_fallback`, the Greenhouse company in the same run still keeps its listing, and the failed firm is first in the email's manual list, ahead of an IB manual firm and a non-IB manual firm.
- **8. PII:** a grep of all 69 tracked files (except the Census file) for personal email domains, key/token shapes, private keys and assignments to the three secret names, plus phone shapes in changed files. Nothing found. The existing repo-wide secret tests pass (9).

## 4. Results (full run and email dry run, 2026-11-03, nothing sent)
| Item | Result | |
|---|---|---|
| Total runtime | 1,894 s = **31.6 min** locally (18:04–18:36 UTC). The first GitHub run took 27.6 min | TESTED |
| Added by new firms | About 14 requests (Piper Sandler 8, Stout 5, Lincoln 1), roughly 20 seconds. Projected GitHub run: about 28 min, far under 60 | Measured; the projection is SHOULD WORK |
| New IB-category listings | 2, both from **Lincoln International**: "2028 Summer Analyst Intern \| CAG" and "\| M&A", Chicago, score 95, `investment_banking` | TESTED |
| Other new listings from new firms | **Piper Sandler**: "2027 Summer Internship Program – Public Finance", Des Moines and Leawood KS, score 85, `corporate_finance`. Stout: 0 kept (its 3 interns are in Cleveland, San Diego and DC) | TESTED |
| Excluded on purpose (rules unchanged) | Lincoln "2027 M&A Summer Associate Intern" (excluded keyword); Piper "IB Summer Associate – Chicago" (no internship term; summer associate roles are for MBA students) | TESTED |
| Plante Moran "2028 PMCF Investment Banking Summer Analyst" | Score **48 → 75**, above `min_score` 50, season Summer 2028. **It isn't in today's email**: it's not new (first seen 2026-11-02), and it ranks 14th among top open matches, while `max_top_open` is 10 | TESTED |
| Email | Subject "Internships — 5 new". New 5 (Lincoln ×2, Piper ×2, PNC), top open 10, remote Iowa 0, manual 10 + "…and 44 more", 19 insurance-only hidden | TESTED (dry run) |
| Database after run | 215 listings, 193 open, 57 open at or above 50 (was 209 / 188 / 53) | TESTED (scratch copy) |
| Workday 500 cap | No new board hit it; no new firm logged a warning | TESTED |

Rendered manual-links block (text version):
```
Check these manually (54)
------------------------
- Holmes Murphy (couldn't be fetched today: error): https://holmesmurphy.wd1.myworkdayjobs.com/HolmesMurphyCareers
- Baird (IB): https://www.rwbaird.com/careers/
- D.A. Davidson (IB): https://www.dadavidson.com/careers
- Fireclay Partners (IB): https://fireclaypartners.com/careers/
- Houlihan Lokey (IB): https://hl.com/careers/
- Jefferies (IB): https://www.jefferies.com/careers/
- Kroll (IB): https://careers.kroll.com/en
- Lazard (IB): https://icbpjb.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/en/sites/LazardStudentCareers/jobs
- Mesirow (IB): https://recruiting2.ultipro.com/MES1003MFAC/JobBoard/69451223-cdce-4faf-9407-23a2cd5ac83b/?q=&o=postedDateDesc
- Moelis & Company (IB): https://www.moelis.com/careers/
…and 44 more manual companies.
```
The HTML version puts "Couldn't be fetched today: Holmes Murphy" on its own line, then "IB firms, no feed:" with the nine IB firms. Holmes Murphy failed with a transient HTTP 520, which has nothing to do with P5.2.

Changes to stored listings in this run, and their cause:
- **From P5.2's season rule, 2 listings:** Plante Moran PMCF (48 → 75) and GCM Grosvenor "2027 IT-Product & Strategy Summer Intern" (18 → 35, held by `no_role_cap`, so it can't reach the email).
- **From P5.1 rules being applied to stored data for the first time,** as the old STATUS predicted, 15 listings:
  - Plante Moran "2027 Summer Wealth Management Marketing Intern", 75 → 45;
  - RSM "Technology Risk Consulting Intern", 95 → 65;
  - Akuna "Accounting Intern (Term-Time, Part-Time)" → filtered;
  - several CNA, Cboe, Athene, Wintrust, Commerce Bank and Federal Reserve technology/marketing titles, which lost 13–30 points each.

## 5. Known issues and risks
- **IB links can be cut on bad days.** There are exactly 10 IB-tagged manual firms and `max_manual` is 10. Today one unrelated failure pushed Stifel into "…and 44 more." Options: raise `max_manual` to 12–15, or accept it (D-037).
- **Plante Moran's IB listing qualifies but isn't shown** because of `max_top_open` (10). Changing that cap is outside this phase.
- **Baird stays a link without a fresh check** (D-039 asks Lucas whether to allow one request).
- **Houlihan Lokey and D.A. Davidson are blocked** (bot check and 403). They stay links, and no further requests go to either host.
- **Stout:** Stout-Careers and Stout-Student-Careers listed the same interns today. Only the student site is fetched, so an intern posted only on Stout-Careers would be missed.
- **Lincoln's apply links** come from Greenhouse's `absolute_url` and start with `http://` on lincolninternational.com. They work as links but aren't https.
- **Run-time:** about 28 minutes is projected on GitHub. Not measured there yet.
- **D.A. Davidson, Houlihan Lokey, Kroll, Moelis, Jefferies and Baird cities are "expected"**, not observed.
- **Season rule side effects** (D-038): titles like "Fall 2027/Winter 2028" now show no season. Among stored listings, only GCM Grosvenor's score changed, and it stays below 50.
- **actionlint not run** this phase (the workflow is unchanged).

## 6. Proposed decisions (also in docs/DECISIONS.md, PROPOSED)
- **D-037 — Company tags and IB-first manual links.** Optional `tags`; 16 IB/advisory firms tagged `ib` at priority 1; `email.manual_first_tags: ["ib"]`. Order: failed → tagged → rest, each by priority then name. `[]` restores P5.1.
- **D-038 — Season and year pair anywhere in a title** (2026–2030). Two seasons or two years → "Not stated", with the reason in `match_reasons` and no fallback to the description. Within 2 words, any year still pairs as before.
- **D-039 — Feed and manual changes.**
  - Piper Sandler: manual → Workday.
  - New feeds: Stout (Workday) and Lincoln (Greenhouse).
  - New manual links: Moelis, Houlihan Lokey, D.A. Davidson, Fireclay, Jefferies, Kroll.
  - Lazard, Stifel and Mesirow are confirmed manual, with their ATS recorded.
  - **Your call:** allow one fresh request to Baird's careers page, or keep Baird manual.
- **D-040 — Scope calls.** Five Elms Capital not added (PE-only). Adapter candidates by IB value: TalentLink (Jefferies, Moelis), then Oracle (Lazard), iCIMS (Stifel), UKG (Mesirow), Breezy (Fireclay).

## 7. STATUS update
The full replacement text is now in `docs/STATUS.md`.

## 8. Git steps for Lucas
- Branch: **`p5-2-ib-coverage`** (5 local commits on top of main).
- One-line summary: **"P5.2: add IB firms (Piper Sandler, Stout, Lincoln live; 10 IB manual links first), pair seasons anywhere in a title."**
- In GitHub Desktop: Current Branch → `p5-2-ib-coverage` → **Publish branch** → **Create Pull Request**, then merge it on GitHub after reading this report.
