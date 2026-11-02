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

## D-015 — SmartRecruiters API and robots.txt (PROPOSED 2026-11-02)
`api.smartrecruiters.com/robots.txt` allows LinkedInBot and disallows every other crawler (`User-agent: *`, `Disallow: /`), even though SmartRecruiters documents a public Posting API. SPEC constraint 2 says to respect robots.txt, so the adapter is built and tested offline, the shared HTTP client blocks it in live runs, and RR Donnelley and Northwestern Medicine appear in `meta.json` as blocked with a "check manually" link. Options: (A) keep respecting robots.txt, and ask SmartRecruiters whether the rule is meant to cover this API; (B) Lucas decides the documented API is exempt, which would change SPEC constraint 2. Recommendation: A.
