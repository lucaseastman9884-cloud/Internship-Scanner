# Phase 4 report: built and passing locally, but not yet run on GitHub

All five acceptance items pass, but **the workflow has never run on GitHub Actions**. It can only run after you merge it, so that first manual run is the real test. All Phase 3 decisions are recorded and implemented.

Everything is in 9 commits on `phase-4-automation`, counting the one that adds this report. They use your noreply email, and nothing is pushed. I haven't started Phase 5.

## Acceptance results
| Item | Result | Evidence |
|---|---|---|
| pytest on Python 3.9 and 3.12 | **Pass** | 442 passed on each, and in a fresh clone |
| One real local run | **Pass** | Exit 0, 36 minutes, 58 of 58 live companies fetched, 0 failures |
| 3 Commerce Bank listings excluded | **Pass** | All 3 are now `filtered`, with real distances (below) |
| Workflow YAML validated | **Pass** | actionlint 1.7.12 found 0 errors and exited 0; its two optional checkers, shellcheck and pyflakes, weren't installed |
| No personal emails or phones | **Pass** | Scan of tracked files below; git history wasn't scanned |
| `docs/AUTOMATION.md` exists | **Pass** | Added and committed |

**Real run totals:** fetched 10,163, kept 192, excluded 9,971, using 981 requests across 44 hosts. No requests went to Wells Fargo, Nominatim or SmartRecruiters.

**Commerce Bank:**
| Listing | Location | Distance from Ames |
|---|---|---|
| Commercial Banking, Cape Girardeau | Cape Girardeau, MO | 391 miles |
| Commercial Banking, Springfield | Springfield, **MO** | 334 miles |
| Business Banking, Illinois | Bloomington, IL | 264 miles |

You listed Springfield IL, but the real listing is in Springfield MO. My Phase 3 report left the state off that one. The tests cover both cities.

**"Location unknown":** 23 open listings remain, down from 28. Both groups are allowed under D-022:
- 13 are at Plante Moran, which lists its office as "Chicago Riverside Plaza".
- 10 are at EMC, which lists only "Iowa".

**Personal data scan:** no Gmail address and no phone numbers. The only email-shaped text my scan matched is `t@example.invalid`, a fake address in `tests/test_phase4.py`. The bot's public noreply address is also in `scripts/commit_data.py`. Your Gmail is still in old commit 820b3ab, as D-030 accepts.

## Listing counts
| Measure | Phase 3 | Now |
|---|---:|---:|
| Database total | 194 | 209 |
| Open | 192 | 190 |
| Filtered | 0 | 16 |
| Possibly closed | 2 | 3 |
| Closed | 0 | 0 |
| Open with score ≥ `email.min_score` (50) | 53 | **54** |
| Open, tagged `remote_iowa` | 0 | 1 |

- **Hundreds of listings:** this goal is still not met. The useful number is closer to 54.
- **What moved:** Plante Moran's kept count rose from 13 to 26, because its Chicago office now counts. Travelers fell from 17 to 8, because St. Paul and St. Louis can now be measured and are too far.
- **Remote Iowa:** the one listing is EMC's "Claims Intern - Workers' Compensation".
- **Worth a look:** CNA's "Finance / Accounting Internship Program (Summer 2027)" scored 95 in Phase 3 and now has one miss. D-025's check says its posting is gone.

## What you must do on GitHub
Full detail is in `docs/AUTOMATION.md`.

1. Open GitHub Desktop and check that **Current Branch** says `phase-4-automation`.
2. Click **Publish branch**.
3. Click **Preview Pull Request**, then **Create Pull Request**. Your browser opens.
4. Click **Create pull request**, then **Merge pull request**, then **Confirm merge**.
5. Back in GitHub Desktop, switch to `main`, then click **Fetch origin** and **Pull origin**.
6. On GitHub, click the **Actions** tab. If it asks you to enable workflows, click the button.
7. Click **Settings**, then **Actions**, then **General**. Check that Actions and GitHub-made actions are allowed. Leave **Workflow permissions** as it is.
8. Click **Actions**, then **Daily scan**, then **Run workflow**. Keep the branch on `main` and click the green **Run workflow** button.
9. Wait about an hour, then click the run and read its summary page.
10. If it fails with a `403` on **Commit data if listings changed**, go back to the setting in step 7, choose **Read and write permissions**, click **Save**, and run it again.
11. If you get a red X for any other reason, send the Command Center the items listed in section 5 of `docs/AUTOMATION.md`.

From then on, click **Fetch origin** and **Pull origin** every time before you work locally, because the bot now saves to `main`.

## Where I differed from your request
1. **Schedule:** you said cron is UTC, but GitHub's current docs now offer a `timezone` option. So I used `33 5 * * *` with `timezone: 'America/Chicago'`, which stays at 5:33 AM Central all year. A fixed UTC time would be 11:33 UTC, which is 5:33 AM in winter (CST) and 6:33 AM in summer (CDT). actionlint accepts the option, but it hasn't run on GitHub yet.
2. **D-025 cap:** you called it a per-company cap, but it's per search term, as the setting's name says. A per-company total could let "intern" use it all up before "internship" ever ran.
3. **D-025 check:** only Workday does it. Greenhouse, Lever and Ashby return the whole board, so a listing's absence from the board is already the proof.
4. **Cities file:** `config/cities.yaml` stays, with names only, because postings like a bare "Waukee" have no state to look up.
5. **Red X and data:** when more than half of companies fail, nothing is committed, including what the healthy companies found. The next run finds it again.

## Decisions as built
- **D-022:** coordinates come from the 2026 Census Gazetteer in `data/reference/`, with its source URL, year and checksum in a README.
- **D-023, D-024, D-026, D-028, D-030:** recorded as you decided.
- **D-025:** I sampled real postings first. Two taken-down postings at Vermeer and EMC returned **403**, a made-up path returned 404, and open postings on those hosts returned 200. So a 403 means "gone" only in this one check, which runs after that host has answered the run's search. Any other failed check is never a miss. In the real run, 4 listings were missed, 0 were confirmed still open, and 0 checks failed.
- **D-027:** I also moved the 12 stored listings and the status entry to the new ID.
- **D-029:** a new `tags` list holds `remote_iowa`. These listings score the same location points as other Iowa listings.
- **Empty-response guard:** the threshold of 3 is in config as `status.empty_response_min_open`.

**One bug found and fixed:** closed listings gained a miss on every run. That would have changed `internships.json`, and caused a commit, every day forever. They now stay unchanged.

## GitHub facts checked
Read 2026-11-02; links are in `docs/AUTOMATION.md`.

| Question | What the docs say |
|---|---|
| Schedule delays | Runs can be delayed at high load, including the start of each hour. The schedule runs only on the default branch |
| 60-day rule | In public repos, scheduled workflows are disabled after 60 days with no repository activity |
| Do bot commits count? | **Not stated.** "Activity" isn't defined. Other projects rely on bot commits, but that's not confirmation |
| `GITHUB_TOKEN` | Limited to this repo. Listing `contents: write` sets everything else to none. Its commits don't start other workflows, so there's no loop |
| Limits | 6 hours per job; a queued job is cancelled after 24 hours; standard runners are free in public repos |

**Keepalive:** daily commits may not happen, because listings can go quiet for weeks. So if the repo has had no commit for 7 days, the bot commits `data/meta.json` alone. If the schedule stops anyway, `docs/AUTOMATION.md` has the steps to re-enable it.

## Issues
1. **GitHub's computers may be treated differently.** Careers sites might block requests from cloud servers even though they answer from your home connection. If over half refuse, the run goes red. I can't test this until the first run.
2. **Possibly missed listings:** 10 big boards still hit 500 for "intern": BMO, RSM, Baker Tilly, Marsh McLennan, PwC, U.S. Bank, PNC, Citigroup, Capital One and State Street. Internships past result 500 could be missed. Listings on those boards can now close, though.
3. **Thin evidence for 403:** "403 means gone" rests on two sampled postings. If it's wrong, a listing would wrongly reach possibly closed, but it reopens if it appears again.
4. **Same-day runs:** a manual run on the same day as the scheduled one counts as a miss, because runs are counted, not days.
5. **Lagging files:** on days with no commit, `meta.json`, `last_seen.json` and `companies_status.json` aren't saved (D-023), so `consecutive_failures` can undercount. The run's summary page still has that day's numbers.
6. **Stale fields:** a filtered listing keeps its old score and location label. The 3 Commerce Bank listings still show 75 points and "Location unknown". Phase 5 must filter by status first.
7. **Wrong reason text:** street-address locations can be misdescribed. "811 Main, Flr 12" says "outside the United States". The listing is correctly excluded, because no city can be read, but the wording is wrong.
8. **Older tests changed:** 6 tests in `tests/test_phase3.py` and 2 in `tests/test_pipeline_and_store.py`, all because your decisions changed the behavior. For example, Lombard IL is now measured instead of unknown.
9. **Requests beyond the run:** about 9 to Vermeer and EMC for the 403 test, plus one Gazetteer download and a few header and robots checks at census.gov. GitHub's API and releases were used for the action versions and actionlint.
10. **Dependencies:** `requirements.txt` pins PyYAML and pytest, but not the packages pytest pulls in.

## Open questions
1. Should SPEC.md be edited to match D-022 and D-024? It still describes Nominatim and three statuses. I left it alone, since `docs/DECISIONS.md` records the changes.
2. Should a company's known cities be used for street-address locations? Only a few listings are affected, and the two Commerce Bank ones are the only finance-adjacent ones I saw.

## Unverified
- The workflow's behavior on GitHub, including the `timezone` option, pip caching, the push, and failure emails. The commit script was tested against local git repositories only.
- Whether bot commits satisfy the 60-day rule.
- The exact button labels in GitHub Desktop and GitHub's notification settings, which I wrote without checking them.
- A live case of D-025 finding a listing still open; that path is tested offline only.
- Census reuse terms: the Gazetteer page has no statement. I relied on 17 U.S.C. § 105 and the Census Bureau's TIGER/Line documentation, and `data/reference/README.md` says so.
- Lever still has no live company.

## Files and commands
**New files:**
- **Workflow and scripts:** `.github/workflows/scan.yml`, `scripts/commit_data.py`, `scripts/run_summary.py`
- **Code:** `scanner/gazetteer.py`
- **Data:** `data/reference/2026_Gaz_place_national.txt`, `data/reference/README.md`
- **Docs:** `docs/AUTOMATION.md`, `docs/reports/P4_REPORT.md`
- **Tests:** `tests/test_phase4.py`

**Changed files:**
- **Scanner:** `__main__.py`, `adapters/base.py`, `adapters/workday.py`, `config.py`, `filtering.py`, `history.py`, `location.py`, `normalize.py`, `pipeline.py`, `scoring.py`, `store.py`
- **Config:** `config/cities.yaml`, `config/companies.yaml`, `config/config.yaml`
- **Docs:** `README.md`, `docs/CONFIG.md`, `docs/DECISIONS.md`, `docs/PLAN.md`, `docs/SOURCES.md`, `docs/STATUS.md`
- **Tests:** `tests/test_phase3.py`, `tests/test_pipeline_and_store.py`
- **Data:** `data/internships.json`, `data/last_seen.json`, `data/meta.json`, `data/companies_status.json`

**Commands:**
```
python -m scanner run
pytest
actionlint -verbose .github/workflows/scan.yml
python scripts/commit_data.py
python scripts/run_summary.py --tests success --scan success --commit-action data
```

The last two are run by the workflow. actionlint was a free download kept outside the repo.

**Test output:**
```
Python 3.9.6:  442 passed in 6.79s
Python 3.12.16 (DeprecationWarnings as errors): 442 passed in 5.18s
fresh clone on 3.9: 442 passed in 7.37s
```

**Workflow validation output:**
```
verbose: Found 0 parse errors in 0 ms for .github/workflows/scan.yml
verbose: Rule "shellcheck" was disabled: exec: "shellcheck": executable file not found in $PATH
verbose: Rule "pyflakes" was disabled: exec: "pyflakes": executable file not found in $PATH
verbose: Found total 0 errors in 1 ms for .github/workflows/scan.yml
actionlint exit code: 0
```

`docs/STATUS.md` is updated and committed. It shows Phase 4 as awaiting your approval, along with the coverage numbers, open questions and known limits.
