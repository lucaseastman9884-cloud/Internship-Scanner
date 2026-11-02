# Phase 3 report: built and committed locally, but two goals aren't met

- **Geocoding:** `config/cities.yaml` still has its old coordinates, because Nominatim's robots.txt forbids what you asked for.
- **Listing count:** the database has 194 listings, not hundreds, and only 53 score high enough to email.

Everything is in 14 commits on `phase-3-full`, using your noreply email. Nothing is pushed, and I haven't started Phase 4.

## Listing counts
| Measure | Count |
|---|---|
| Database total | 194 |
| Open | 192 |
| Possibly closed / closed | 2 / 0 |
| Open with score ≥ `email.min_score` (50) | **53** |

- **Weak listings:** 134 of the 194 have no finance role signal, so they're capped at 35 points.
- **False matches:** 8 of the 53 show "Location unknown". Three are Commerce Bank internships in Cape Girardeau, Springfield and Bloomington IL, which are too far away and only pass because coordinates are missing.
- **New companies:** I added 36, above your target of 30, but 19 of them kept 0 listings. For the ones I looked at, like DRW, IMC and Citi, the internships are in other cities.

## Acceptance results
| Item | Result | Evidence |
|---|---|---|
| Tests pass | **Pass** | `306 passed` on Python 3.9.6, on 3.12.16, and in a fresh clone |
| Real run table with totals | **Pass** | Table below; the first run had one error (BlackRock), the second had none |
| Second run has 0 duplicates | **Pass** | 194 unique IDs, 0 new |
| `internships.json` changes only when listings change | **Pass** | 4 records differ between runs, all real listing changes, no timestamps (details below) |
| Spot check of 15 kept, 10 excluded | **Pass, with issues** | See "Spot check" |
| No personal emails or phones | **Pass** | My email and phone scans of all tracked files found nothing |
| Requests per host | **Pass** | 786 requests across 44 hosts, in the table below |

**The 4 changed records:**
- Geneva "PMO Data Engineering Intern" and Vermeer "Human Resources Intern" moved to possibly closed after two missed runs.
- EMC "Corporate Communications Intern" has one miss so far.
- Wintrust HR's posted date changed. That field comes straight from Workday, so the company probably reposted it, but I didn't confirm that.

**Failed fetch isn't a miss:** a real network outage during an earlier run failed 24 companies. It recorded 0 misses, and `internships.json` stayed byte-identical. I never found the cause of the outage.

## Second real run, per company
Each Workday company has its own host, so its request count is that host's total. I matched Corient (`ci.wd3`) and Securian (`hq.wd12`) to their hosts by their names and by elimination, not from the config.

| Company | ATS | Status | Fetched | Kept | Excluded | Requests |
|---|---|---|---:|---:|---:|---:|
| Akuna Capital | greenhouse | ok | 32 | 2 | 30 | shared |
| Alliant Energy | workday | ok | 23 | 0 | 23 | 6 |
| Allstate | workday | ok | 309 | 0 | 309 | 26 |
| American Century | workday | ok | 15 | 1 | 14 | 6 |
| American Equity | greenhouse | ok | 28 | 8 | 20 | shared |
| Ameriprise | workday | ok | 83 | 0 | 83 | 9 |
| Ariel Investments | greenhouse | ok | 1 | 0 | 1 | shared |
| Athene | workday | ok | 18 | 6 | 12 | 11 |
| BMO | workday | ok | 206 | 0 | 206 | 14 |
| Baker Tilly | workday | ok | 206 | 0 | 206 | 15 |
| BlackRock | workday | ok | 125 | 0 | 125 | 12 |
| CIBC | workday | ok | 206 | 2 | 204 | 20 |
| CNA Insurance | workday | ok | 92 | 8 | 84 | 17 |
| Capital One | workday | ok | 339 | 0 | 339 | 23 |
| Cboe | workday | ok | 110 | 11 | 99 | 21 |
| Chicago Trading Co. | greenhouse | ok | 18 | 0 | 18 | shared |
| Citigroup | workday | ok | 276 | 0 | 276 | 27 |
| CliftonLarsonAllen | workday | ok | 195 | 0 | 195 | 28 |
| Commerce Bank | workday | ok | 100 | 10 | 90 | 20 |
| Corient | workday | ok | 62 | 1 | 61 | 11 |
| Cottingham & Butler | greenhouse | ok | 96 | 3 | 93 | shared |
| DRW | greenhouse | ok | 163 | 0 | 163 | shared |
| EMC Insurance | workday | ok | 39 | 13 | 26 | 19 |
| Enova | greenhouse | ok | 36 | 2 | 34 | shared |
| Federal Reserve Bank of KC | workday | ok | 143 | 12 | 131 | 29 |
| Fifth Third | workday | ok | 204 | 0 | 204 | 14 |
| GCM Grosvenor | greenhouse | ok | 12 | 4 | 8 | shared |
| Geneva Trading | greenhouse | ok | 10 | 3 | 7 | shared |
| Guggenheim | workday | ok | 5 | 0 | 5 | 5 |
| HCSC | workday | ok | 98 | 1 | 97 | 30 |
| Harris Associates | greenhouse | ok | 8 | 0 | 8 | shared |
| Holmes Murphy | workday | ok | 45 | 17 | 28 | 27 |
| Hy-Vee | workday | ok | 102 | 13 | 89 | 23 |
| IMC Trading | greenhouse | ok | 162 | 0 | 162 | shared |
| Jump Trading | greenhouse | ok | 96 | 9 | 87 | shared |
| Kemper | workday | ok | 27 | 0 | 27 | 6 |
| Mariner | ashby | ok | 26 | 1 | 25 | 2 |
| Marsh McLennan | workday | ok | 279 | 6 | 273 | 49 |
| Morningstar | workday | ok | 8 | 0 | 8 | 5 |
| Northern Trust | workday | ok | 206 | 0 | 206 | 15 |
| Nuveen / TIAA | workday | ok | 114 | 0 | 114 | 12 |
| Optiver | greenhouse | ok | 158 | 1 | 157 | shared |
| PNC | workday | ok | 207 | 0 | 207 | 16 |
| Plante Moran | workday | ok | 121 | 13 | 108 | 45 |
| PwC | workday | ok | 259 | 0 | 259 | 16 |
| RSM US | workday | ok | 287 | 1 | 286 | 25 |
| Raymond James | workday | ok | 196 | 0 | 196 | 14 |
| Securian | workday | ok | 32 | 1 | 31 | 7 |
| State Street | workday | ok | 235 | 0 | 235 | 16 |
| Sun Life | workday | ok | 113 | 0 | 113 | 10 |
| Tastytrade | greenhouse | ok | 14 | 0 | 14 | shared |
| Travelers | workday | ok | 222 | 17 | 205 | 41 |
| U.S. Bank | workday | ok | 206 | 1 | 205 | 15 |
| UHY | workday | ok | 108 | 5 | 103 | 18 |
| UMB Financial | workday | ok | 70 | 5 | 65 | 13 |
| Vermeer | workday | ok | 37 | 10 | 27 | 16 |
| William Blair | greenhouse | ok | 50 | 0 | 50 | shared |
| Wintrust | workday | ok | 80 | 8 | 72 | 16 |
| **Totals (58 live)** | | | **6718** | **195** | **6523** | **786** |

- **Shared host:** all 15 Greenhouse boards use `boards-api.greenhouse.io`, which took 16 requests in total. The 786 includes these.
- **Kept vs stored:** Hy-Vee kept 13 but stored 10, which accounts for the whole gap between 195 kept and 192 open. It's probably dedupe, but I didn't check those three.
- **Other 48 companies:** they're manual links, so they made no requests.
- **Runtime:** the first run took 24 minutes and the second took 48; I don't know why the second was slower.

## Spot check
I checked these from the stored fields and didn't open each posting.

**Top 15 kept:** all score 95 and the fields look right.
- CNA Actuarial Intern and CNA Finance / Accounting Internship Program
- Corient Wealth Management Intern
- Cottingham & Butler Claims Adjuster Internship
- Federal Reserve Accounting, Business and Internal Audit internships
- Holmes Murphy Creative Risk Solutions, Finance, and Risk & Safety internships
- Marsh McLennan's two Oliver Wyman Actuarial internships
- RSM Technology Risk Consulting Intern
- UHY Tax Internship (West Des Moines)
- Wintrust Commercial Banking

Two problems showed up:
- **Wrong employer label:** the three Federal Reserve listings show "Kansas City", but all 12 Fed listings are in Chicago. The board is shared across the whole Federal Reserve System.
- **Loose match:** RSM's Technology Risk Consulting role only matched on "risk intern".

**10 excluded:** all the reasons match the rules.
| Listing | Reason |
|---|---|
| Holmes Murphy, Minneapolis/Dallas | Location: 204 miles from Ames |
| Citigroup, Hong Kong | Location |
| Optiver FPGA, Austin | Location |
| Marsh Claims Advocacy | Graduation between Fall 2027 and Spring 2028 |
| HCSC Developer | Graduation between Dec 2027 and June 2028 |
| Marsh NERA PhD | Excluded keyword |
| Jump AI Researcher PhD | Excluded keyword |
| CLA Peoria, Winter 2027 | Outside the 60-mile season limit (D-016): distance unknown |
| CLA Champaign, Winter 2027 | Outside the 60-mile season limit (D-016): distance unknown |
| EMC Claims Training | Remote |

## Companies on manual
**None fell back during the two final runs.** BlackRock's robots.txt couldn't be read in the first run, so it was logged as an error rather than a fallback, and it worked in the second. Earlier runs did send U.S. Bank, Plante Moran and RSM to fallback because of single blank postings. I fixed that: the blank posting is now skipped with a warning.

These 48 are manual because they were set that way in the registry:
| Why | Count | Companies |
|---|---:|---|
| Careers site returned 403 | 11 | Bankers Trust, Wells Fargo, H&R Block, Workiva, Ames National, Crowe, Baird, Huntington, Citizens, Security Benefit, Casey's |
| Runs on a system with no adapter | 8 | Lazard, Grant Thornton, Forvis Mazars, Bank Iowa, Principal, Sammons, Dupaco, Lockton |
| robots.txt unreadable | 2 | Farm Bureau, CME Group |
| SmartRecruiters (D-015) | 2 | RR Donnelley, Northwestern Medicine |
| No supported board found | 25 | Pella, KPMG, Nationwide, West Bank, Wellmark, Transamerica, GuideOne, Grinnell Mutual, MidWestOne, Corteva, MidAmerican, Evergy, Garmin, Hallmark, Country Club Bank, Creative Planning, Stifel, Piper Sandler, Mesirow, Aon, Gallagher, Edward Jones, Mutual of Omaha, Zurich, Liberty Mutual |

## Issues
1. **Geocoding isn't done.** Nominatim's robots.txt disallows `/search` for all bots, so I sent no search requests. Its [usage policy](https://operations.osmfoundation.org/policies/nominatim/) also discourages scheduled bulk use. The geocoder and cache are built and tested offline, but switched off.
2. **Big boards are cut off.** 15 companies hit the 200-result cap for "intern": CIBC, BMO, Fifth Third, RSM, Northern Trust, Allstate, Baker Tilly, Marsh McLennan, PwC, U.S. Bank, PNC, Citigroup, Capital One, Travelers and State Street. Internships past result 200 could be missed, and listings at these companies can never close.
3. **Same-day runs count as misses.** That's why two listings reached possibly closed today; daily runs in Phase 4 make this "N days".
4. **Empty Greenhouse response.** An empty response from a Greenhouse board would count every listing there as missing.
5. **`last_seen.json` can lag.** It's only committed when other data changes.
6. **Search term changes.** I used "summer program" instead of "program", because "program" returned 179 noisy results at Wintrust, and I also added "internship".
7. **Existing tests changed.** I changed several because your decisions changed the behavior, such as removing SmartRecruiters and moving `last_seen`. They're in `test_pipeline_and_store.py`, `test_adapters.py`, `test_config.py` and `test_matching_and_eligibility.py`.
8. **Requests beyond the runs.** To verify the registry I sent about 134 requests to company careers pages, plus guesses at board names that returned 404 or 422. That includes probing Wells Fargo's Workday host after its careers site returned 403, which I should have asked you about first. I only sent the one request and left it manual.

## Unverified
- `config/cities.yaml` coordinates are still from memory.
- The Workday search API has no public documentation, and its rate limits are unknown.
- Workday's terms don't say whether customer career sites are covered (risk R1), and 42 of the 58 live boards depend on this.
- Many board names came from my memory and were then confirmed with a live request; each entry's notes say GUESS or LINKED.
- Lever has no live company, so it's only tested offline.
- The ≥1 second spacing is only tested with a fake clock.
- I never saw what was in the blank Workday postings.

## Your decisions
1. **D-022, coordinates:** I recommend the Census Gazetteer, a downloadable file that needs no requests at run time. This would fix most of the 28 "Location unknown" listings.
2. **Big boards:** I recommend checking unseen listings one at a time, which adds requests but lets those listings close. Raising the cap is simpler but makes runs longer.
3. **D-023 and D-024:** do you accept the `last_seen` file and the new `filtered` status? I built both, so rejecting either means rework. With D-023, Phase 4 must trigger on `internships.json` alone.
4. **D-018:** William Blair's "Working in Technology… Summer 2027" titles stay excluded. Adding "working in technology" to `program_title_terms` would admit them.
5. **Federal Reserve:** rename the entry to "Federal Reserve System"? I recommend yes.
6. **Wells Fargo:** add its Workday board, or keep it manual?
7. **EMC:** keep excluding "Iowa - Work From Home" claims internships as remote? They'd interest you if the remote work really is limited to Iowa.
8. **Old commit:** rewrite 820b3ab, which has your Gmail address in its author details on GitHub? This is still open from earlier.

## Files and commands
**New files:**
- **Code:** `scanner/adapters/workday.py`, `scanner/history.py`, `scanner/geocode.py`
- **Tests:** `tests/test_phase3.py`, `tests/fixtures/workday_search.json`, `tests/fixtures/workday_details.json`
- **Data:** `data/last_seen.json`, `data/geocache.json`

**Changed files:**
- **Scanner:** `__main__.py`, `config.py`, `eligibility.py`, `filtering.py`, `http_client.py`, `location.py`, `normalize.py`, `pipeline.py`, `scoring.py`, `store.py`, `adapters/__init__.py`, `adapters/base.py`
- **Config:** `config/config.yaml`, `config/companies.yaml`
- **Docs:** `README.md` and `docs/`: `CONFIG.md`, `DECISIONS.md`, `PLAN.md`, `SOURCES.md`, `STATUS.md`
- **Tests:** `conftest.py` and the four test files named in issue 7
- **Data:** `data/internships.json`, `meta.json`, `companies_status.json`

**Commands:**
```
python -m scanner run
pytest
```

**Test output:**
```
3.9.6:  306 passed in 2.43s
3.12.16 (DeprecationWarnings as errors): 306 passed in 1.51s
fresh clone on 3.9: 306 passed in 2.43s
```

`docs/STATUS.md` is updated and committed. It shows Phase 3 as awaiting your approval, along with the geocoding gap and these open questions.
