# STATUS — Current state (updated 2026-11-05)

## Phase
P0 — Setup: DONE.
P1 — Plan: DONE and approved.
P2 — Pipeline core: DONE and merged to main.
P3 — Full pipeline: DONE and merged to main.
P4 — Automation: DONE and merged to main (PR #4).
P5 — Morning email: merged to main (PR #5). P5.1 (PR #6) and P5.2 (PR #7) merged too.
P6 — Contacts (Engine B): decided in D-042 and D-043 (ACCEPTED 2026-11-03). Engine B runs outside this repo.
P7 — PWA core: merged to main (PRs #8 and #9). D-044 ACCEPTED 2026-11-05.
P8 — Look, recently posted, company hub (D-045): built on branch `p8-look-hub`, **not pushed**. D-045 and D-046 ACCEPTED 2026-11-05. D-047 (build choices) is PROPOSED. Tested locally (below). The live deploy and "Last scan ran" on GitHub are **NOT TESTED** until the merge.

## P8 — Look, recently posted, company hub (2026-11-05)
Built:
- **P7 follow-ups:**
  - `build_site_config.py` skips an unknown home or target-area city with a warning and still writes the file.
  - The Python site tests moved to `tests/site/`, marked `site`. A plain `pytest` (the Daily scan) no longer collects them; Deploy site runs `pytest -m site`.
  - The header and Today show "Last scan ran" (looked up at deploy with `gh run list` and `actions: read`) next to "Data updated", plus failed sources.
- **Config:** a `site:` block (`posted_within_days`, `default_sort`, `default_theme`, `linkedin_school_id`, `linkedin_school_name`, `manual_first_tags`, `deadline_window_days`), checked at deploy with fallbacks. Also an optional `linkedin_name` per company, set for CME Group, Chicago Trading Company and Nuveen / TIAA.
- **Pages:** `#/today` (default), `#/listings`, `#/companies`, `#/company/<id>`, `#/my-list` and `#/contacts` (placeholder); anything else shows "Not found". The nav marks the current page and becomes a bottom tab bar on phones.
  - **Today:** new; posted in 24 h (posted vs first seen); deadlines in 14 days; scan health; Remote — Iowa (only when there are any); Contacts placeholder. Open listings only, and each tile opens Listings with its filter.
  - **Listings:** a "Posted" filter (Any, 24 h, 3, 7 or 30 days), "New only", "Deadline in the next 14 days", the "Newest posted" sort, and company links. A listing's date is `date_posted` when readable, else `first_seen`, and it's always labelled "Posted" or "First seen".
  - **Companies:** all 114 registry companies plus any only in the status history; IB first, then by open listings, then name; with search.
  - **Company page:** listings grouped open → possibly closed → filtered → closed; the two LinkedIn links in Engine B's formats; an empty P9 contacts slot.
- **Design ("neon glass"):** dark first with a stored light toggle, CSS theme tokens, glass panels with a solid fallback, and a CSS-only moving background that pauses when the tab is hidden. Score gauges, signed match-reason chips and View Transitions. Nothing moves under reduced motion. Self-hosted Inter and Space Grotesk (SIL OFL).
- **PWA:** the service worker's cache is now `p8-shell-…`, and it precaches the fonts and the new modules. `companies.json` is a new network-first data file. The manifest has the new colours.

TESTED (2026-11-05, on this Mac; headless Chrome 137 through the DevTools protocol; temporary Node 24.22.2):
- `pytest`: 609 pass. It's the Daily scan's command, and it collects 0 tests from `tests/site/` (`--collect-only`). That's P7's 615 minus the 6 that moved.
- `pytest -m site`: 40 pass. That's the 6 moved P7 tests plus 34 new ones: an unknown city, last-scan time, every `site.*` key, 22 bad values falling back, the loader not checking `site:`, and `companies.json` fields.
- `node --test "tests/js/*.test.mjs"`: 64 pass (P7's 34 unchanged, plus 30 new):
  - Posted buckets with a fixed clock, the first-seen fallback and its label, future dates counting as today, and the Newest posted order.
  - Today counts (open only), and the deadline window following the setting.
  - LinkedIn links matching Engine B's formats exactly, with Wintrust, Federal Reserve, an override, "&", and a name that would strip to nothing.
  - Routing, including unknown routes and company ids.
  - XSS through a fake DOM on Today, Companies, a company page and listing cards.
  - WCAG AA contrast for 172 pairs in each theme (worst text 5.10:1 dark, 4.66:1 light).
  - The theme with blocked storage.
- Speed: 2,000 listings filter and sort in a median of 8.2 ms (Node). In the page, a filter change with drawing takes 47 ms (P7: 15 ms; the gauges cost some) and the Companies page draws in 5.3 ms. The Companies data from 2,000 listings takes 1.6 ms.
- Lighthouse 13.6.0, mobile and desktop, on Today, Listings, Companies and a company page: Accessibility 100 and Best Practices 100 on all; CLS 0 on all. Performance is 99–100 on desktop. On mobile it's 80–99, with the main content appearing at 1.7–5.3 s under simulated slow 4G (see Known limits).
- Real data in Chrome:
  - Today's New tile (15) opens Listings showing 15. The 24 h tile (6) shows 6.
  - The Posted buttons give 6 / 22 / 35 / 107 / 194.
  - The drawer has a gauge with "Score 95 of 100" and signed chips. Esc returns focus to the card. Its company link opens the company page.
  - `aria-current` is right. Searching Companies for "piper" gives 1.
- The LinkedIn links on the Wintrust, Federal Reserve, Moelis and CME Group pages match the formats exactly and open with `rel="noopener noreferrer"`.
- A hostile fixture (HTML and script in names, titles, reasons and errors, plus `javascript:` and `data:` URLs) renders as text on every page. There were no dialogs, no CSP violations, and no clickable unsafe link.
- Network: every request went to the site's own origin, the fonts included. Zero CSP violations and zero console errors.
- PWA:
  - No installability or manifest errors. The service worker is active and in control.
  - With the server stopped, Today, Companies, a company page and Listings open from cache with "Offline — data from Nov 5, 2026, 6:52 AM".
  - A changed app shows "New version available", and Reload swaps to the new cache.
- At 375 px there's no horizontal scroll on any of the 7 pages, in either theme, and the drawer is full width.
- Reduced motion: `document.getAnimations()` is empty on every page and in the drawer. With a background tab in front, the page reports hidden and all 3 background animations are paused.
- The theme toggle survives a reload. With localStorage blocked, the site works, shows the storage banner, and the toggle and tracker still work for the session.
- No emails, phone numbers, Sheet IDs, task IDs or secrets turned up in the diff or the built site.
- actionlint 1.7.12 passes on `pages.yml` and `scan.yml`.

NOT TESTED:
- The live deploy, and "Last scan ran" coming from the real `gh run list` / `workflow_run` lookup. Locally the time was passed in by hand.
- Safari and Firefox. Install on a real phone.

## Environment
- Repo: github.com/lucaseastman9884-cloud/Internship-Scanner (public)
- Local folder: ~/Documents/GitHub/Internship-Scanner (cloned with GitHub Desktop)
- Mac, Claude Code, Claude Pro, Python 3.9.6. GitHub Actions uses Python 3.12. Tests pass on both.
- Lucas is new to GitHub, terminal, and deployment: explain any step he must do himself.
- Git commits use Lucas's GitHub noreply address. The workflow commits as github-actions[bot].
- Email secrets (P5), names only: `SMTP_USERNAME`, `SMTP_APP_PASSWORD`, `EMAIL_TO`. They live only in GitHub Actions secrets.
- Live site: https://lucaseastman9884-cloud.github.io/Internship-Scanner/

## Done
- P1: docs/PLAN.md, config files, first company registry, decisions D-009 to D-014.
- P2: the `scanner` package, Greenhouse, Lever, and Ashby adapters, normalization, eligibility, filtering, scoring, dedupe, upsert, data files, and offline tests.
- P3: Workday adapter with manual fallback; open → possibly_closed → closed; filtered status; recurring programs; full companies_status.json; scoring in config; registry grown to 106 companies.
- P4: decisions D-022 to D-030 and the empty-response guard; Census Gazetteer coordinates; remote_iowa tag; Workday cap of 500 with a per-listing check before a miss; daily workflow; commit-on-change and summary scripts; docs/AUTOMATION.md.
- P5, P5.1, P5.2: morning email, failure email, manual-link cap, IB coverage (114 companies, 61 live, 16 tagged `ib`). Details in DECISIONS D-033 to D-041 and docs/reports/P5_2_REPORT.md.
- P7: the installable web app (list, instant filters, drawer, tracker, offline). D-044.
- P8: see above. D-045, D-046, proposed D-047.

## How to run
From the project folder, after the one-time setup in README.md:
- Run the pipeline: `python -m scanner run` (about 30 to 35 minutes, because of the polite delays)
- Preview the email: `python -m scanner email --dry-run`, then open `outputs/email_preview.html`
- Run the tests: `pytest` (the scanner's; never uses the network). The web app's tests: `pytest -m site`, plus `node --test "tests/js/*.test.mjs"` (Node isn't installed on this Mac; they run on GitHub before every deploy).
- Try the site locally: `python scripts/stage_site.py _site`, then `python -m http.server 8000 --directory _site`, and open http://localhost:8000
- Run it on GitHub: see docs/AUTOMATION.md

## Current coverage (data of 2026-11-05)
- 224 listings, 194 open. Every listing has a `date_posted`; none states a deadline, so "Deadlines soon" is empty on real data (tested with fixtures).
- 114 companies (61 live, 53 manual). The goal of "hundreds of qualifying listings" is **still not met** (see Open questions).

## Next
1. Push `p8-look-hub` with GitHub Desktop, open the PR, and merge it.
2. Wait for **Deploy site** to go green in the Actions tab, then check the live site (the P8 report lists the steps). Accept or change D-047.
3. Per D-032: compress, `/clear`, and start **P9 — private contacts after Google sign-in** (D-046).

## Open questions
- Raise `email.max_top_open`, or show IB listings separately? Plante Moran's IB listing qualifies but ranks 14th.
- Which adapter, if any, comes next? TalentLink would unlock Jefferies and Moelis (D-040).
- Does a commit by github-actions[bot] count as "repository activity" for GitHub's 60-day rule? GitHub's docs don't say. The weekly keepalive assumes yes.
- Commerce Bank lists some internships by street address only. Should a company's known cities be used for this?

## Known limits
- The Workday cap is per search term, not per company in total. 10 big boards still hit 500 for "intern."
- Stout is fetched from its student site only.
- D-025's "403 means gone" rests on two real postings seen on 2026-11-02.
- A failed run commits nothing, including what the healthy companies found.
- On a day with no commit, `meta.json`, `last_seen.json`, and `companies_status.json` aren't saved (D-023). Since P8 the site shows "Last scan ran" separately, so this is visible.
- A second run on the same day counts as a miss. Runs are counted, not days.
- A filtered listing keeps its old score and location label until it's next kept.
- The role-category exclusion reads titles only. `location_conflict` reads "City, ST" text only.
- If Gmail itself refuses to send, the failure email can't get through either.
- Web app:
  - Tracker data and the theme choice live in one browser. Clearing site data deletes them unless the tracker was exported.
  - Mobile Lighthouse Performance is about 80 on most pages: under simulated slow 4G, the main content waits for `data/internships.json`. Locally the whole load takes about 25 ms.
  - With `site.default_theme: "light"`, a first visit flashes dark until `site_config.json` loads (no inline scripts under the CSP; D-047).
  - The fonts are the Latin subset; other characters fall back to system fonts.
  - An unknown target-area city still stops the scanner's own config check (out of P8's scope); only the site script tolerates it.
- UNVERIFIED items are listed in PLAN sections 5 and 7.
