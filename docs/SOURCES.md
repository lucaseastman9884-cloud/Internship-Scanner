# SOURCES — Candidate data sources (research 2026-11-02; Phase 1 must re-verify against official docs)

| Source | Endpoint | Auth | Status | Rec |
|---|---|---|---|---|
| Greenhouse Job Board API | `boards-api.greenhouse.io/v1/boards/{slug}/jobs` | None | Official (developers.greenhouse.io/job-board.html) | USE |
| Lever Postings API | `api.lever.co/v0/postings/{slug}?mode=json` | None | Official (github.com/lever/postings-api) | USE |
| Ashby Job Posting API | `api.ashbyhq.com/posting-api/job-board/{slug}` | None | Official (developers.ashbyhq.com) — mostly tech | USE (low priority) |
| SmartRecruiters public postings | `api.smartrecruiters.com/v1/companies/{id}/postings` | None | Documented API, but its robots.txt disallows all but LinkedInBot (see D-015, PLAN section 5) | BLOCKED |
| Workday career-site JSON | POST `{tenant}.wdN.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs` | None | Unofficial; same feed the careers page uses | USE politely (D-002) |
| Oracle Cloud / iCIMS / Jobvite | varies | varies | Verify per vendor | LATER |
| USAJOBS API | federal | free key | Official | LATER |
| Community internship lists (GitHub) | varies | None | Check license | VERIFY |
| Google `site:` search | — | — | Prohibited by Google ToS | SKIP |
| LinkedIn / Indeed / Handshake / Glassdoor | — | — | Scraping prohibited | SKIP |

## Contacts
Apollo via official connector (Engine B only). Never in this repo.

## Email sending (verify in Phase 1)
- Gmail SMTP + app password in a GitHub secret (requires 2-Step Verification).
- A free transactional provider with no card required, as fallback.
