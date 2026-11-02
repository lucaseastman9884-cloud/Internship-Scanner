# STATUS — Current state (updated 2026-11-02)

## Phase
P0 — Setup: DONE.
P1 — Plan: DONE and approved.
P2 — Pipeline core: DONE and merged to main.
P3 — Full pipeline: built on branch `phase-3-full`, **not pushed, awaiting Lucas's approval**. One Part D item is not done (see "Not done"). Do not start P4 until approved.

## Environment
- Repo: github.com/lucaseastman9884-cloud/Internship-Scanner (public)
- Local folder: ~/Documents/GitHub/Internship-Scanner (cloned with GitHub Desktop)
- Mac, Claude Code, Claude Pro, Python 3.9.6. Tests also pass on Python 3.12.
- Lucas is new to GitHub, terminal, and deployment: explain any step he must do himself.
- Git commits use Lucas's GitHub noreply address.

## Done
- P1: docs/PLAN.md, config files, first company registry, decisions D-009 to D-014.
- P2: the `scanner` package, Greenhouse, Lever, and Ashby adapters, normalization, eligibility, filtering, scoring, dedupe, upsert, data files, and offline tests.
- P3: Workday adapter with manual fallback; open → possibly_closed → closed; filtered status; recurring programs; full companies_status.json; D-015 to D-021; all scoring points moved to config; geocoder with cache (built, switched off); registry grown to 106 companies.

## How to run
From the project folder, after the one-time setup in README.md:
- Run the pipeline: `python -m scanner run` (about 25 to 50 minutes, because of the polite delays)
- Run the tests: `pytest` (never uses the network)

## Current coverage (real run, 2026-11-02)
- 106 companies: 58 fetched live (42 Workday, 15 Greenhouse, 1 Ashby) and 48 manual links.
- Database: 194 listings, 192 open, 2 possibly_closed, 0 closed. **53 open at or above email.min_score (50).**
- The goal of "hundreds of qualifying listings" is **not met**. 134 of the 194 have no finance role signal (capped at 35), so the useful number is closer to the 53.
- No live company uses Lever, so that adapter is tested with fixtures only.

## Not done
- **Part D, replacing `config/cities.yaml` coordinates with Nominatim results.** Nominatim's robots.txt disallows `/search` for all bots, and its policy calls scheduled bulk use "strongly discouraged." The geocoder is built and tested offline but is off (`geocoding.enabled: false`). No `/search` request was sent. Coordinates are still approximate and from memory (UNVERIFIED). Waiting on D-022.

## Next
Lucas reviews P3 and decides the open questions below. Then P4 — Automation (see SPEC "PHASES").

## Open questions
- **D-022:** how to get coordinates. Recommended: the Census Gazetteer, a downloadable file with no requests at run time.
- **D-023:** last_seen moved to `data/last_seen.json`, so internships.json changes only when listings change. P4 must trigger on internships.json alone.
- **D-024:** the added `filtered` status (on the board, but no longer passes our filters).
- **Big boards:** 15 companies hit the 200-result cap for "intern." Real interns past rank 200 could be missed, and these companies cannot count misses, so their listings never close. Fix options: check unseen listings one at a time, or raise the cap.
- **D-018:** William Blair's "Working in Technology ... Summer 2027" titles stay excluded because they have none of the listed words. Adding "working in technology" to `program_title_terms` would admit them.
- **Federal Reserve:** the board is shared by the whole Federal Reserve System. All 12 listings are in Chicago but appear under "Federal Reserve Bank of Kansas City." Rename the entry, or keep it?
- **Wells Fargo:** stays manual because the careers site answered 403. Its Workday host answered one test request. Add it or not?
- **EMC:** "Iowa - Work From Home" claims internships are excluded as remote. Keep that?
- **Git email:** commit 820b3ab, already on GitHub, records Lucas's Gmail. Rewrite that one commit?
- Apollo Gmail-account search and monthly reset — test in P6.

## Known limits
- 28 listings show "Location unknown." 8 of them score at or above 50, including Commerce Bank in Cape Girardeau, Springfield, and Bloomington IL, which are really too far away. Coordinates (D-022) fix most of these.
- A second run on the same day counts as a miss. Daily runs in P4 make this "N days."
- `last_seen.json` is only committed when other data changes, so it can lag.
- An empty Greenhouse board response would count as every listing missing.
- Many board names in the registry were guessed, then verified with a live request. Each entry's notes say GUESS or LINKED. Cities marked "expected" were not observed.
- UNVERIFIED items are listed in PLAN sections 5 and 7.
- Python 3.9 no longer gets security updates; P4 should run on 3.12.
