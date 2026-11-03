# Phase 5.1 report — Email polish
Branch `p5.1-email-polish`, from `main` at 44cb4d8 (2026-11-03). 9 commits, **not pushed**. Tested offline only.

## Results at a glance
| Check | Result | Detail |
|---|---|---|
| pytest, Python 3.9.6 | **Pass** | 564 passed (488 before + 76 new) |
| pytest, Python 3.12.16, DeprecationWarnings as errors | **Pass** | 564 passed |
| actionlint 1.7.12 | **Pass** | 0 errors, exit 0. Its optional shellcheck and pyflakes checkers aren't installed |
| Secret and PII scan of tracked files | **Pass** | No personal addresses, keys, secret values or phone numbers |
| All acceptance fixtures | **Pass** | `tests/test_p5_1.py`, listed below |
| Pipeline rerun twice on the same data | **Pass** | 0 new, 0 duplicates, 0 status changes, `internships.json` byte-identical |
| Sample email | **Saved** | `docs/reports/P5_1_sample_email.html`, made from fixtures, example links only |
| `simulate_failure` on GitHub | **Should work, not tested** | Validated by actionlint, tests on the workflow file, and inspection. You need to run it |

## Files changed
- **Code:** `scanner/config.py`, `scanner/normalize.py`, `scanner/location.py`, `scanner/store.py`, `scanner/filtering.py`, `scanner/scoring.py`, `scanner/email_report.py`
- **Workflow:** `.github/workflows/scan.yml`
- **Config:** `config/config.yaml` (and its copy in `docs/CONFIG.md`)
- **Tests:** `tests/test_p5_1.py` (new), `tests/test_phase4.py` (adds the new step to the list of steps that have conditions)
- **Docs:** `docs/SPEC.md` (replaced with v2.2, then folded), `docs/DECISIONS.md`, `docs/CONFIG.md`, `docs/PLAN.md`, `docs/AUTOMATION.md`, `docs/STATUS.md`, `docs/reports/P5_1_sample_email.html`, this report
- **Data:** none. `data/` wasn't touched. The next daily scan applies the new rules (see "What changes on the next scan").

## What was built
**A. Manual-links cap.** `email.max_manual: 10`. Order: companies that failed today (alphabetical), then the manual ones by priority 1, 2, 3 (alphabetical within each). After the cap: "…and N more manual companies." The section header still shows the total, e.g. "Check these manually (48)".

**B. Insurance-only listings hidden (D-034).** `email.exclude_role_categories: ["insurance_risk"]`.
- A listing is hidden only when **every** role category its **title** matches is in that list.
- `early_career` counts as a program-level signal, not a role, so "Sophomore Actuarial Intern" is still hidden.
- A title with no category match isn't touched by this rule.
- The listings stay in `data/internships.json` with their scores.
- `"credit risk"` and `"market risk"` were added to `role_categories.banking`. `banking` comes before `insurance_risk` in config, so "Credit Risk Intern" gets `role_category: banking` and shows.
- The source-health line ends with "{n} insurance-only listings hidden." n counts open listings that passed every other email filter.

**C. Two filters.**
- `exclude_keywords_outside_home: ["part-time", "term-time"]`. These match as whole words, with a hyphen or a space ("Part Time"). Such a listing is kept only within `radius_miles` (150) of Ames. If it's already stored, it becomes `filtered` with a reason such as "Title says 'part-time', kept only within 150 miles of home; this is 305". If it's new, it isn't stored.
- `scoring.title_penalty_keywords: { technology: -30, marketing: -30 }`. Each one adds a reason such as "-30 title: 'technology' is off-target". The 0–100 bounds and `no_role_cap` still apply afterwards.

**D. Location conflict.** The title is read for "City, ST" as text and never geocoded (D-022). If it names a different place from the kept location, the listing gets the tag `location_conflict`, and the email shows "Overland Park, KS (title says Cincinnati, OH)".

**E. Year-only seasons.** A title with a year from 2026 to 2030 and no season word stores `season_year` (an integer). `season` stays null, so it is still "Not stated" for `email.seasons`. The email shows "2028 · season not stated". Scoring is unchanged.

**F. Failure-email test.** The manual run gains a checkbox, `simulate_failure` (boolean, default false). When it's ticked, a step right after **Run tests** fails on purpose. Then **Run scanner** and **Send morning email** are skipped (they have no `if`, so GitHub's default `success()` applies), and **Commit** is skipped too, because it requires `steps.scan.outcome == 'success'`. **Send failure email** (`if: failure()`) then reports "simulated failure: failure". Steps are in docs/AUTOMATION.md, section 10.

**G. Docs.**
- SPEC.md is now the v2.2 text, with D-033 to D-035 folded in. MORNING EMAIL gains the role-category exclusion and `max_manual`. COMPANY REGISTRY notes P5.2. PHASES gains P5.1 and P5.2 before P6.
- D-033 to D-035 are added to DECISIONS, each with a "Built in P5.1" line.
- CONFIG, PLAN, AUTOMATION and STATUS are updated.

## Decisions I made (please confirm or overrule)
1. **Two keys beyond the brief.** `scoring.title_penalty_exempt_categories: ["investment_banking"]` exists so the code doesn't hard-code a category name (D-020). The brief also said bank-risk titles must not be hidden; the new banking keywords already handle that.
2. **The category name in the health line** is the first word of each excluded category: `insurance_risk` gives "insurance-only".
3. **Remote jobs are exempt from the part-time rule**, since there's no commute. An **unknown distance doesn't pass**, the same as D-016. Today this affects no real listing.
4. **A year with any season word anywhere in the title isn't "year-only".** Example: "2028 PMCF Investment Banking Summer Analyst" gets no `season_year` (see Known issues).
5. **SPEC phase lines.** The pasted v2.2 text said P4 was "awaiting the first GitHub run" and listed P5 without a state. I changed these to P4 DONE and P5 merged (PR #5), with a real send not confirmed, to match STATUS. The rest of the text is verbatim, apart from markdown formatting and the folds. A line at the top maps 01_SPEC… to the repo's file names.

## Acceptance tests (all in `tests/test_p5_1.py`, all pass)
| Fixture | Result |
|---|---|
| 48 manual companies, `max_manual` 10 | 10 shown: 3 failed first, then priority 1 alphabetically; "…and 38 more manual companies." in HTML and text |
| Title matching only `insurance_risk` | Hidden from the email; still `open` in `internships.json` (pipeline fixture) |
| `insurance_risk` + `banking` ("Underwriting and Commercial Banking Intern") | Shown |
| "Credit Risk Intern", "Market Risk Summer Intern" | `role_category: banking`, shown |
| "Accounting Intern (Term-Time, Part-Time)" in Chicago / in Ames | Chicago: `filtered` with reason (pipeline, config changed between runs). Ames: `open` |
| "Technology Risk Consulting Intern" | −30 with reason "-30 title: 'technology' is off-target" |
| "2027 Technology Investment Banking Summer Analyst" | No penalty (also "Technology Banking Summer Analyst", "Technology M&A Intern") |
| "Intern, Tax- Cincinnati, OH" at "Cincinnati, OH; Overland Park, KS" | Kept at Overland Park, KS; tag `location_conflict`; email shows "(title says Cincinnati, OH)" |
| "2028 Audit or Tax Intern" | `season` null ("Not stated"), `season_year` 2028, "+8 season: not stated" unchanged, email "2028 · season not stated", still matched by `email.seasons: ["Not stated"]` |
| Sample email from fixtures | Shows all of the above; no "@" anywhere; saved to `docs/reports/P5_1_sample_email.html` |
| Pipeline run, then a same-day rerun, then a next-day run | 0 new, 7 listings throughout, all status counts 0, file byte-identical |

Also tested: bad values for every new key are rejected with a clear message; empty lists turn each rule off; penalty values come from config; the floor of 0 and `no_role_cap` still hold; `title_place` doesn't match "Remote (IL, CA, NY)" or "Intern, IT Security"; the workflow input is a boolean defaulting to false, and its step sits right after the tests.

## Tests run (exact commands)
```
.venv/bin/python -m pytest -q                                                  # Python 3.9.6
<scratchpad>/v312/bin/python -W error::DeprecationWarning -m pytest -q -p no:cacheprovider   # Python 3.12.16
<scratchpad>/al/actionlint -verbose .github/workflows/scan.yml
python -m scanner email --dry-run --out-dir <scratchpad>/realrun                # real data, nothing sent
```
```
Python 3.9.6:  564 passed in 8.84s
Python 3.12.16: 564 passed in 25.46s
actionlint: Found total 0 errors ... exit 0
```
The secret/PII scan was a grep over every tracked file, except the Census file, for personal email domains, key and token shapes, private keys, assignments of the three secret names, and phone-number shapes in changed files. Nothing was found. The existing repo-wide test, `test_no_secret_values_or_addresses_in_tracked_text_files`, also passes.

Network use in P5.1: one GET of Mariner's public Ashby board (D below), with the project's User-Agent, and one read of GitHub's docs page on contexts.

## TESTED vs "should work"
- **Tested offline:** everything in A–E, the config validation, the email rendering, the failure email naming the simulated step, the workflow's structure, and rerun safety.
- **Tested on real data (dry run, nothing sent):** B hides 19 open listings, the subject goes from 53 new to 34, and Remote — Iowa goes from 1 to 0, because its only listing is an EMC claims role. Manual links: 10 shown + "…and 38 more".
- **Should work, not run:** the `simulate_failure` path on GitHub. GitHub's docs say `inputs` exists only for `workflow_dispatch` and reusable runs, and that a missing property evaluates to an empty string, so a scheduled run skips the step. Source: https://docs.github.com/en/actions/reference/workflows-and-actions/contexts (read 2026-11-03).
- **Not tested:** any real email send. That still needs the secrets and a run on GitHub.

## B — every open listing the email now hides
None of these is a bank role. All are insurance, actuarial, claims, or risk-control work, plus RSM's IT-risk consulting.

| Company | Title | Location | Score |
|---|---|---|---:|
| CNA Insurance | Actuarial Intern – Summer 2027 | Chicago, IL | 95 |
| Cottingham & Butler | 2027 Summer Claims Adjuster Internship | Dubuque, IA | 95 |
| Holmes Murphy | Creative Risk Solutions Intern - Summer 2027 | West Des Moines, IA | 95 |
| Holmes Murphy | Risk & Safety Intern - Summer 2027 | Waukee, IA | 95 |
| Marsh McLennan | Oliver Wyman Actuarial - Internship - Summer 2027 | Chicago, IL | 95 |
| Marsh McLennan | Oliver Wyman Actuarial - Life Internship - Summer 2027 | Chicago, IL | 95 |
| RSM US | Technology Risk Consulting Intern - Summer 2027 | Chicago, IL | 95 (65 after C) |
| EMC Insurance | Claims Intern - Workers' Compensation | Remote (Iowa) | 85 |
| EMC Insurance | Intern - Fast Track Claims | Location unknown | 85 |
| EMC Insurance | Intern- Claims (Data) | Location unknown | 85 |
| EMC Insurance | Intern- Claims (Property) | Location unknown | 85 |
| Travelers | Bond and Specialty Insurance Intern: Underwriting Professional Development Program | Chicago, IL | 68 |
| Travelers | Business Insurance Intern: Underwriting Professional Development Program (UPDP) | Overland Park, KS | 68 |
| Travelers | Business Insurance Intern: Underwriting Professional Development Program (UPDP) | Downers Grove, IL | 68 |
| Travelers | Risk Control Intern | Overland Park, KS | 68 |
| Travelers | Risk Control Intern | Chicago, IL | 68 |
| EMC Insurance | Claims Intern - Medical Management | Location unknown | 58 |
| EMC Insurance | Intern-Claims | Location unknown | 58 |
| EMC Insurance | Underwriting Intern | Location unknown | 58 |

Bank-risk check: no open listing today has "credit risk" or "market risk" in its title. Plante Moran's "2027 Risk and Accounting Advisory Services Consulting Internship" matches accounting as well as insurance_risk, so it still shows. Athene's "Risk Co-op" matches no category and isn't affected.

## C — before/after scores for affected open listings
Before is the stored score. After is that listing's stored points plus the penalty, with the bounds and the no-role cap applied: what the next scan will store.

| Company | Title | Location | Rule | Before | After |
|---|---|---|---|---:|---:|
| RSM US | Technology Risk Consulting Intern - Summer 2027 | Chicago, IL | technology −30 | 95 | 65 (also hidden by B) |
| Plante Moran | 2027 Summer Wealth Management Marketing Intern | Location unknown | marketing −30 | 75 | **45**, drops below 50 |
| Plante Moran | 2027 Business Technology Advisory Consulting Intern | Location unknown | technology −30 | 48 | 18 |
| Commerce Bank | Intern - Commercial Marketing (Summer 2027) | Kansas City, MO | marketing −30 | 35 | 15 |
| Federal Reserve System | Summer 2027 Intern - Marketing, Communications, Journalism Majors | Chicago, IL | marketing −30 | 35 | 10 |
| Holmes Murphy | Information Technology Intern - Summer 2027 | West Des Moines, IA | technology −30 | 35 | 10 |
| Holmes Murphy | Marketing Intern - Summer 2027 | West Des Moines, IA | marketing −30 | 35 | 10 |
| Wintrust Financial | Wintrust 2027 Summer Internship: Information Technology | Rosemont, IL | technology −30 | 35 | 15 |
| CNA Insurance | Technology Internship Program (Data Analytics) | Chicago, IL | technology −30 | 18 | 0 |
| CNA Insurance | Technology Internship Program (AI Engineering / Agile Product Design / Cybersecurity / Data Engineering / Software Engineering), 5 listings | Chicago, IL | technology −30 | 13 | 0 |
| Athene | Product Marketing Intern | West Des Moines, IA | marketing −30 | 13 | 0 |
| Cboe Global Markets | Marketing Intern | Chicago, IL | marketing −30 | 13 | 0 |
| Plante Moran | 2027 Marketing Intern - Client Experience | Location unknown | marketing −30 | 0 | 0 |
| Plante Moran | 2027 Marketing Technology Intern | Location unknown | both, −60 | 0 | 0 |
| **Akuna Capital** | **Accounting Intern (Term-Time, Part-Time)** | Chicago, IL (305 mi) | part-time filter | 68, open | **filtered** |

Only the Plante Moran marketing intern leaves the email because of C. RSM's listing is hidden by B anyway. Every other change is to listings already below 50.

## D — root cause of Mariner's location
**Not a parser bug.** On 2026-11-03 I fetched Mariner's public Ashby board once. The posting "Intern, Tax- Cincinnati, OH" has `location: "Cincinnati, OH"` and `secondaryLocations: [{"location": "Overland Park, KS"}]`. The adapter joins both into "Cincinnati, OH; Overland Park, KS". Then, by design, the resolver keeps the city that qualifies best: Overland Park is in the Kansas City metro, while Cincinnati is outside every area. The source's location is kept, so the listing gets `location_conflict` and the email notes "(title says Cincinnati, OH)". Across all 209 stored listings, this is the only one flagged. Whether Mariner would really place a tax intern in Overland Park is a question for Mariner.

## What changes on the next scan
The rules in B and A act on the email right away. C, D and E need the pipeline to rewrite each record, which the next daily scan does for every open listing:
- new scores
- the Akuna listing becomes `filtered`
- Mariner gets its tag
- `season_year` appears on 21 open Plante Moran year-only titles plus Athene's "Derivates Operations Co-op (2027)"
- some listings change `role_category` if they match "credit risk" or "market risk" (none open today)

Expect a bigger-than-usual data commit that day. A second run then changes nothing (tested on fixtures).

## Known issues and the next step
- **Season detection misses a far-off season word.** "2028 PMCF Investment Banking Summer Analyst" (Plante Moran) has 3 words between the year and "Summer". The title pattern allows 2, so the listing is "Season not stated" and scores 48, just under the email's 50. That's an IB role you'd want. Fixing it is a scoring change, which P5.1 ruled out, so it's in STATUS's open questions for P5.2.
- The role-category exclusion reads titles only. A title such as EMC's "Insurance Intern" matches no category, so it isn't hidden. It scores below 50 anyway.
- `location_conflict` only reads the "City, ST" shape, and it can be fooled by a two-letter word that is also a state code (e.g. "…, MD" meaning Managing Director). Among stored listings it flags only Mariner.
- The run summary for a simulated failure says "The scan did not finish (skipped)". That's accurate but generic.
- **Next:** you push this branch and merge the PR. Then run **Daily scan** by hand with `simulate_failure` ticked and confirm the "Scan failed" email arrives. Then do a normal run and check the morning email. After that, compress per D-032 and start P5.2 — IB coverage (D-035).

## STATUS.md update text
The full new `docs/STATUS.md` is committed. These are the parts that changed:

> **Phase:** P5 merged (PR #5), real send not confirmed. **P5.1 — Email polish: built on branch `p5.1-email-polish`, not pushed, awaiting Lucas's approval. Tested offline only.** P5.2 — IB coverage (D-035): next.
>
> **Done (P5.1):** manual links capped at `email.max_manual` (10), failed first, then priority 1–3, then "…and N more manual companies." (D-033); insurance-only listings hidden from the email and counted in the health line, still in the data (D-034); "credit risk"/"market risk" match banking; part-time/term-time titles kept only within 150 miles of home; technology/marketing titles −30 unless IB; `location_conflict` tag and "(title says …)" note; `season_year` and "2028 · season not stated"; `simulate_failure` checkbox to test the failure email.
>
> **Coverage:** P5.1 dry run on current data: 34 new (25 shown), 9 top open, 0 remote Iowa, 10 manual + "…and 38 more", 19 insurance-only hidden. After the next scan, Plante Moran's Wealth Management Marketing Intern drops 75 → 45 and Akuna's Chicago part-time accounting intern becomes filtered.
>
> **Next:** 1. Push and merge P5.1. 2. Run Daily scan with `simulate_failure` ticked; check the "Scan failed" email; then a normal run and the morning email. 3. Compress per D-032 and start P5.2 — IB coverage.
>
> **New open question:** season pairing allows only 2 words between year and season, so "2028 PMCF Investment Banking Summer Analyst" (score 48) is "Season not stated". Change it in P5.2?
>
> **New known limits:** the role-category exclusion reads titles only; `location_conflict` reads "City, ST" text only.
