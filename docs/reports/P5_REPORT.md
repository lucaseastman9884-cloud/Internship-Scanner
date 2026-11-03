# Phase 5 report — Morning email (Engine A)
Branch `phase-5-email`, from `main` at b743974 (2026-11-03). Committed locally, **not pushed**.

## Results at a glance
| Check | Result | Detail |
|---|---|---|
| pytest, Python 3.9.6 | **Pass** | 488 passed (442 before P5 + 46 new) |
| pytest, Python 3.12.16, DeprecationWarnings as errors | **Pass** | 488 passed |
| actionlint 1.7.12 | **Pass** | 0 errors, exit 0. Its optional shellcheck and pyflakes checkers weren't installed |
| Dry run on the real `data/internships.json` | **Pass** | `outputs/email_preview.html` (37 KB) and `.txt` written; nothing sent |
| Missing-secrets run on the real data | **Pass** | Yellow warning naming all three secrets, exit 0, `data/` unchanged |
| Secret and PII scan | **Pass** | See below |
| Real email sent through Gmail | **Not tested** | It **should work**, but it has never run. It needs the secrets and a run on GitHub |
| Failure email on GitHub | **Not tested** | Same |

## What was built
- **`scanner/email_report.py`** builds the email from `data/internships.json`, `data/meta.json` and the `email:` block, and sends it with `smtplib` only.
  - Subject: `Internships — {n} new ({date})`, with the date in America/Chicago. `n` counts every new listing that passes the filters, including any beyond `max_new`.
  - Sections, in order: **New since last email** (by score) → **Deadlines in the next 14 days** (soonest first) → **Top open matches** → **Remote — Iowa** (left out when there are none) → **Check these manually** → a one-line **source health** summary.
  - **Status first:** only `status == "open"` listings get through, before any score check (D-024). Then `min_score`, `seasons` and `areas`, with `max_new` and `max_top_open` as limits. All values come from config.
  - Each listing shows its title, company, city and state (or "Location unknown"), season (or "Season not stated"), score, top 2 match reasons by points, and an apply link.
  - The HTML uses inline CSS only, with no `<style>` block, because Gmail strips those. It has a plain-text alternative. Every value is HTML-escaped, and only `http(s)` links are used.
  - **Failure email:** `Scan failed ({date})`, with the run link and which steps failed. It reads no config or data, because those may be what broke.
- **"New since last email":** after a successful send, `data/meta.json` gets an `email` record holding `last_sent_at`, `sent_date`, and the ids of listings first seen that day. It holds no addresses or other personal data. The pipeline now carries this record over when it rewrites `meta.json`. Before any record exists, "new" means first seen within `new_badge_days`.
- **CLI:**
  - `python -m scanner email` sends.
  - `--dry-run` writes `outputs/email_preview.html` and `.txt` instead of sending.
  - `--failure --run-url URL --outcome step=result` sends the failure email.
  - `outputs/` is gitignored.
- **Workflow:** the steps run in this order: tests → scan → **Send morning email** → commit → summary → **Send failure email** (`if: failure()`).
  - The three secrets go, as `env:` entries, only to the two email steps. They never appear in a command line, and nothing prints them.
  - The commit step now runs `if: !cancelled() && steps.scan.outcome == 'success'`, so a Gmail problem never loses the day's data. A failed test or scan still can't reach the commit.
  - The run summary gained an email line.
- **Config validation:** the `email:` block is now fully checked. Unknown keys, negative limits, area names that aren't in `target_areas` or aren't state codes, and season names that aren't in `seasons` or `"Not stated"` are all rejected. **No config values changed and no keys were added.**

## Decisions I made (please confirm or overrule)
1. **Branch base.** You said to branch from up-to-date main. `docs-sync-d031-d032` isn't merged, or even pushed, so P5 doesn't include its 3 commits. Both branches edit `docs/STATUS.md`, so expect a conflict there. P5's STATUS already contains everything the docs-sync version says, so when you resolve it, **keep the P5 version**.
2. **Remote — Iowa listings appear only in their own section** (D-029 "show it separately"). They aren't repeated in New or Top, but they get a NEW badge and count in the subject. They skip the `areas` filter, since they have no place on a map, but `min_score` and `seasons` still apply.
3. **Top open matches skips listings already shown under New**, so nothing is listed twice. New listings past `max_new` can still appear there, with a NEW badge.
4. **Meaning of `areas` and `seasons` when they aren't `"all"`.** `areas` takes `target_areas` names and/or state codes. `seasons` takes season names plus `"Not stated"`. 117 of 189 open listings give no season, so a seasons list without `"Not stated"` drops most of them. This is documented in docs/CONFIG.md.
5. **Manual links:** all 48 are on one compact line of links. Companies that failed today are listed first under "Couldn't be fetched today", then the rest by priority. The brief said a "short list". Cutting it down would need a new `email:` setting, which I didn't add. It's an open question in STATUS.
6. **Port 587 with STARTTLS**, not 465 with SSL. Google's personal-account page lists 587 for TLS/STARTTLS.
7. **The failure email fires on any failed step:** tests, scan, email or commit. Its body names the step. Its subject is still "Scan failed".
8. **Two P4 tests changed on purpose.** `test_workflow_uses_no_secrets` became "secrets only in the email steps". The `if:` rule now allows the commit, summary and failure-email conditions. The safety property, that a failed test or scan can't commit, is still asserted.

## Dry-run section counts (real data, 2026-11-03)
```
Subject: Internships — 53 new (2026-11-03)
Section counts: new 25, new_total 53, deadlines 0, top_open 10, remote_iowa 1, manual 48
```
- **New 25 of 53:** no email has been sent yet, and every listing was first seen on 2026-11-02, inside `new_badge_days` (3). So all 53 open listings scoring 50 or more count as new: 52 on site and 1 remote. 25 are shown, the `max_new` limit, and the email says "27 more".
- **Deadlines 0:** no stored listing states a deadline.
- **Remote — Iowa 1:** EMC "Claims Intern - Workers' Compensation" (score 85).
- **Source health line:** "58 of 58 live companies fetched (42 Workday, 15 Greenhouse, 1 Ashby), 0 failed, 48 manual. Scan finished 12:12 AM CST." That was the time of the first, manual run.
- The first real email will look like this. Later ones show only what's new since the last send.

## Sources for the Gmail SMTP settings (read 2026-11-03)
- **Personal Gmail accounts:** https://support.google.com/mail/answer/7104828. It lists "Outgoing Mail (SMTP) Server: smtp.gmail.com · Requires SSL: Yes · Requires TLS: Yes (if available) · Requires Authentication: Yes · Port for TLS/STARTTLS: 587". It says work or school accounts should ask their admin.
- **Workspace admin page:** https://knowledge.workspace.google.com/admin/gmail/send-email-from-a-printer-scanner-or-app. It names `smtp.gmail.com` and says "For SSL, enter 465. For TLS, enter 587." It requires authentication with an app password.
- **Google developers:** https://developers.google.com/workspace/gmail/imap/imap-smtp says "The outgoing SMTP server, smtp.gmail.com, supports TLS", with 465 for SSL and 587 for TLS.
- **App passwords:** https://support.google.com/mail/answer/185833. They need 2-Step Verification. They're unavailable with security-key-only 2SV, a work or school account, or Advanced Protection. They're created at https://myaccount.google.com/apppasswords. Changing the account password revokes them.
- **GitHub secrets:** https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets. Settings → Secrets and variables → Actions → New repository secret. Secrets aren't passed to runs from forks.
- The sending limit (500 per day, https://support.google.com/mail/answer/22839) comes from P1 and wasn't re-read. We send one or two a day.

## Secret names the code expects (exact)
| Name | Value |
|---|---|
| `SMTP_USERNAME` | The sending Gmail account's full address |
| `SMTP_APP_PASSWORD` | Its 16-letter app password. Spaces are removed by the code |
| `EMAIL_TO` | The receiving address (your inbox). Several can be comma-separated |

## Secret and PII scan
Scope: every tracked file plus the new untracked ones, except the Census Gazetteer file, and the dry-run outputs.
- **Email addresses:** only `t@example.invalid` (an existing P4 test and report), `@example.com` test values, and the bot's `noreply` address. Lucas's address appears nowhere. The dry-run outputs contain no email address.
- **Token and key patterns** (GitHub, AWS, Google API, Slack, private keys) and quoted password assignments: none.
- **Phone-number patterns outside `data/`:** none. `data/` didn't change in P5.
- **Logs:** a missing-secret run prints only the variable names. An SMTP error is printed with every secret value replaced by its name, and a test checks this with a fake error that echoes the username and password. GitHub also masks secret values in logs.
- A new test, `test_no_secret_values_or_addresses_in_tracked_text_files`, fails if a personal-domain address appears in a tracked file, or if any of the three names is given a literal value instead of `${{ secrets.… }}`.

## Tests added (tests/test_phase5.py, 46 tests)
- **Status:** only open listings appear. Filtered, possibly_closed and closed listings are excluded, including a filtered one with a stale score of 100 and a deadline.
- **Filters and limits:** the `min_score` boundary, `max_new` and `max_top_open`, sorting by score, seasons (including "Not stated"), and areas (by target area, by state, and a "Location unknown" listing that names Chicago). Bad `email:` values are rejected, and no `email:` value is hard-coded.
- **Deadline window:** yesterday is out, today is in, the last day is in, the day after is out, and junk values are ignored. Chicago's date is used: at 03:00 UTC a deadline is still "today". Sorted soonest first.
- **Remote — Iowa:** absent with no such listing, and absent when its only listings are filtered or below the minimum score. Present with one, kept only in its own section, counted in the subject, with a NEW badge.
- **Empty day:** "0 new" renders in HTML and text. The subject format is checked.
- **Rendering:** each listing shows the required fields and only its top 2 reasons. HTML is escaped, `javascript:` links are dropped, and there's no `<style>` block.
- **Manual and health:** manual-link order, the health line, and an empty meta.
- **"New since last email":** the `new_badge_days` fallback, the recorded send including a same-day listing found later, and the record contents. The pipeline keeps the record.
- **Sending, always mocked:** an autouse fixture replaces `smtplib.SMTP` and `SMTP_SSL` with a class that raises, and conftest blocks sockets.
  - The send uses smtp.gmail.com:587, STARTTLS before login, and a password with its spaces removed. The message has both text and HTML parts.
  - A missing secret, for each of the three, skips with exit 0, logs names only, and leaves meta untouched.
  - An SMTP failure exits 1 with secrets redacted.
  - A successful send records the time, and the next day's email says "0 new".
- **Dry run and CLI:** the preview is written, nothing is sent, meta is untouched, and `outputs/` is gitignored.
- **Failure email:** subject, link and steps. It skips without secrets and needs no config.
- **Workflow:** secrets reach only the two email steps and never a `run:` line. The steps are ordered scan < email < commit < failure email. The failure step is `if: failure()`, and the commit is gated on the scan's success.

## Commands run
```
source .venv/bin/activate
pytest                                                   # Python 3.9.6: 488 passed in 6.52s
<scratchpad>/v312/bin/python -W error::DeprecationWarning -m pytest   # Python 3.12.16: 488 passed in 5.18s
<scratchpad>/al/actionlint .github/workflows/scan.yml    # exit 0
python -m scanner email --dry-run
python -m scanner email --failure --dry-run --run-url https://github.com/x/y/actions/runs/1 --outcome scan=failure
env -u SMTP_USERNAME -u SMTP_APP_PASSWORD -u EMAIL_TO python -m scanner email   # warning, exit 0
```
The 3.12 environment and actionlint are kept outside the repo, as in P4.

## Files changed
- **New:** `scanner/email_report.py`, `tests/test_phase5.py`, `docs/reports/P5_REPORT.md`
- **Code:**
  - `scanner/__main__.py`: the `email` subcommand.
  - `scanner/config.py`: `email:` validation.
  - `scanner/pipeline.py`: keeps `meta.email`.
  - `scripts/run_summary.py`: the email line.
- **Workflow:** `.github/workflows/scan.yml`
- **Tests:** `tests/test_phase4.py`, where two workflow tests were updated (see decision 8).
- **Docs and config:**
  - `README.md`
  - `docs/AUTOMATION.md`: the new section 10, plus failure-email notes.
  - `docs/CONFIG.md`: a section explaining the `email:` settings. The YAML block is unchanged.
  - `docs/PLAN.md`: the repo tree, and section 7's SMTP line is now documented rather than UNVERIFIED.
  - `docs/STATUS.md`
  - `.gitignore`: adds `outputs/`.
- **Not changed:** `config/*.yaml`, `data/`, scoring, adapters.

## Known issues
- **The real send is untested.** It should work: the host, port and STARTTLS follow Google's page, and the code uses `smtplib` the standard way. But Gmail may still refuse a first sign-in from GitHub's servers, for example with a security alert in the sending account. If so, the log shows `SMTPAuthenticationError` and the data is still saved.
- **If Gmail refuses, the failure email fails too.** The run's red X and GitHub's own notifications remain the fallback.
- **Same-day reruns:** a listing first found by a second run on the day of a send is correctly shown as new the next time. If the second run doesn't change `internships.json`, that day's send record isn't committed (D-023). That's harmless, because no listing was added.
- **The manual-links block is long:** 48 links.
- **SPEC's MORNING EMAIL section** still lists 5 sections and doesn't mention Remote — Iowa. Per D-032 it should be updated after approval. I didn't edit SPEC in this phase.
- **Location labels:** several Plante Moran listings say "Schaumburg, IL" because of how their multi-location postings resolved in P4. The email shows what the data says.

## STATUS.md
Updated. It shows P5 as built on `phase-5-email`, not pushed and awaiting approval, with no real email sent yet. It includes the secret names, the dry-run counts, the next steps, the new open question about manual links, and two new known limits.

## What you need to do (step by step)

### A. Make a Gmail account just for sending (skip if you have one)
1. Create a new Gmail account yourself, used only by this project (D-009). Don't use your personal one.
2. In that account, turn on **2-Step Verification**: Google Account → Security → 2-Step Verification.
3. Go to https://myaccount.google.com/apppasswords while signed in to **that** account. Type the name `Internship Scanner` and click **Create**.
4. Copy the 16-letter password and keep the tab open for step B. Don't save it in any file.

### B. Add the three secrets on GitHub
1. Open https://github.com/lucaseastman9884-cloud/Internship-Scanner and click **Settings**.
2. In the left sidebar, under **Security**: **Secrets and variables** → **Actions**.
3. On the **Secrets** tab, click **New repository secret**. Name: `SMTP_USERNAME`. Secret: the sending account's address. Click **Add secret**.
4. Click **New repository secret** again. Name: `SMTP_APP_PASSWORD`. Secret: the 16-letter password. Click **Add secret**.
5. Click **New repository secret** again. Name: `EMAIL_TO`. Secret: your personal address. Click **Add secret**.
6. You should now see three secrets listed. GitHub never shows their values again, which is normal.

### C. Merge the docs-sync branch first (recommended)
`docs-sync-d031-d032` exists only on your Mac.
1. In GitHub Desktop, switch **Current Branch** to it and click **Publish branch**.
2. Click **Preview Pull Request** → **Create Pull Request** → **Create pull request**, then **Merge pull request** → **Confirm merge**.

### D. Push P5 and open the PR
1. In GitHub Desktop, set **Current Branch** to `phase-5-email`.
2. Click **Publish branch**.
3. Click **Preview Pull Request**, then **Create Pull Request**. Your browser opens.
4. If GitHub says there are conflicts in `docs/STATUS.md` (from step C), click **Resolve conflicts**. Keep the P5 text, the block that mentions "P5 — Morning email". Delete the `<<<<<<<`, `=======` and `>>>>>>>` lines and the other version. Then click **Mark as resolved** → **Commit merge**. If that's confusing, send me the screen and I'll guide you.
5. Click **Create pull request**, then **Merge pull request** → **Confirm merge**.
6. Back in GitHub Desktop, switch to `main`, then **Fetch origin** → **Pull origin**.

### E. Start a manual test run
1. On GitHub, click the **Actions** tab, then **Daily scan** in the left sidebar.
2. Click **Run workflow**, leave the branch as `main`, and click the green **Run workflow** button.
3. Wait about 30 to 60 minutes. Then open the run and click **scan** → **Send morning email**.
   - **"Email sent: Internships — … new (…)":** check your inbox, and the spam folder.
   - **"Missing secret(s): …":** a name is misspelled. Fix it in step B and run again.
   - **`SMTPAuthenticationError`:** recheck the app password, and look for a Google security alert in the sending account.
4. The failure email is tested offline only. Breaking the password won't test it, because the failure email uses the same login and would fail too. A missing secret only gives a yellow warning, by design. A real test needs the tests or the scan to fail, so it's simplest to confirm it the first time a run goes red. If you want a deliberate test sooner, ask, and I'll suggest a safe, temporary way.
5. Tell me what happened. Until then, the real send counts as "should work", not "tested".
