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
