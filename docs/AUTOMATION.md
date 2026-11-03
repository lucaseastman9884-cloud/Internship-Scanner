# AUTOMATION — The daily scan on GitHub Actions

GitHub Actions is GitHub's free service for running code on a schedule. Every morning it starts a temporary computer, runs the tests, runs the scanner, and saves any changed listings back to this repo. The instructions it follows are in `.github/workflows/scan.yml`.

**You don't need your Mac on for this.** The only passwords it uses are the three email secrets in section 10, which live in GitHub's secrets store and never in a file.

## 1. Push this branch and merge it
The workflow can't run until it's on `main`, because GitHub only offers the **Run workflow** button and the schedule for files on the default branch.

1. Open **GitHub Desktop**.
2. At the top, check that **Current Branch** says `phase-4-automation`.
3. Click **Publish branch** at the top. If it says **Push origin** instead, click that.
4. Click **Preview Pull Request**, then **Create Pull Request**. Your browser opens on GitHub.
5. Click **Create pull request**.
6. Click **Merge pull request**, then **Confirm merge**.
7. Back in GitHub Desktop, click **Current Branch** and choose `main`.
8. Click **Fetch origin**, then **Pull origin**.

## 2. Turn on Actions and check its permissions
1. On GitHub, open the repo and click the **Actions** tab. If GitHub asks you to enable workflows, click the button to enable them.
2. Click the **Settings** tab, then **Actions**, then **General** in the left sidebar.
3. Under **Actions permissions**, check that Actions is allowed and that actions from GitHub are allowed. The workflow uses `actions/checkout` and `actions/setup-python`, both made by GitHub.
4. Under **Workflow permissions**, you can leave the read-only default. The workflow asks for permission to save its data in its own file, and GitHub's docs say the file's setting overrides this default.
5. Change it only if a run fails with a `403` on its **Commit data if listings changed** step. In that case choose **Read and write permissions**, click **Save**, and run the workflow again.

## 3. Run it by hand
1. Click the **Actions** tab.
2. In the left sidebar, click **Daily scan**.
3. On the right, click **Run workflow**.
4. Leave the branch set to `main`, and click the green **Run workflow** button.
5. Wait a few seconds and refresh the page. A new run appears with a yellow circle, which means it's running.

A run takes about an hour, because the scanner waits between requests on purpose. You can close the page while it runs.

## 4. Read a run
1. Click the **Actions** tab, then click the run's name.
2. The **summary** page shows a table: companies fetched, new listings, listings at or above your minimum score, failures, and manual fallbacks. Below it, a line says whether data was saved.
3. Yellow warnings on that page name each company that failed that day.
4. For more detail, click **scan** on the left. Each step opens to show its log. **Run scanner** has the full per-company table.

Icons on the Actions tab:

| Icon | Meaning | What to do |
|---|---|---|
| Green check | The run worked. Single companies may still have warnings | Nothing |
| Green check with yellow warnings | The run worked, and those companies failed today. They get another try tomorrow, and their listings aren't counted as missing | Nothing, unless the same company keeps failing |
| Yellow circle | Still running | Wait |
| Red X | The run failed, and **no data was saved** that day | See section 5 |

## 5. If you see a red X
One of these happened:
- A test failed. The scanner didn't run.
- The scanner crashed.
- More than half of the live companies failed. This usually means something big, like GitHub's computers being blocked or a network problem.
- The run hit its 90-minute limit.
- The data couldn't be saved.
- The morning email couldn't be sent (Gmail refused the login, for example). The data **is** still saved in this case. See section 10.

A single red X isn't an emergency: your stored listings are safe, and the next morning's run tries again.

**Send this to the Command Center:**
1. The run's web address, copied from your browser.
2. The name of the step with the red X.
3. The last 30 or so lines of that step's log. Click the step to open it, then select and copy them.
4. The table from the summary page, if there is one.
5. Whether anything changed recently, such as a config edit.

**Failure email:** once the email secrets are set (section 10), a red X also sends you a short "Scan failed (date)" email with a link to the run. If the failure was Gmail itself refusing to send, that email can't get through either, so the Actions tab stays the reliable record.

**GitHub's own notice:** in your GitHub account's notification settings, find the **Actions** section and choose to be notified only about failed runs. GitHub sends scheduled-run notifications to whoever created the workflow, or last changed its schedule. The commit that adds this file is under your name, so that should be you, but this hasn't been tried. The exact menu labels may differ too.

## 6. Why you must click Pull origin first
The bot now saves to `main` on GitHub on its own. So GitHub often has newer files than your Mac. If you edit an old copy, Git may refuse your push or report a conflict.

**Every time, before you work locally:**
1. Open **GitHub Desktop**, and choose the `main` branch.
2. Click **Fetch origin**.
3. If the button changes to **Pull origin**, click it.
4. Then make your changes, such as editing `config/config.yaml`.

**Don't edit files in `data/` by hand.** The bot owns them, and a hand edit is the likeliest cause of a conflict. `data/reference/` is the exception, and it rarely changes.

## 7. When it runs
- **Time:** 5:33 AM Central, every day. It's set with `timezone: 'America/Chicago'`, so it stays at 5:33 through the change between standard and daylight time.
- **Without that line:** schedules run in UTC, which is 6 hours ahead of Central in winter (CST) and 5 hours ahead in summer (CDT). A fixed UTC time would move by an hour twice a year: 11:33 UTC is 5:33 AM in winter but 6:33 AM in summer.
- **Why :33:** GitHub says scheduled runs can be delayed at busy times, including the start of each hour. Avoiding :00 and :30 lowers that risk, but a delay can still happen. Don't expect it to the minute.

## 8. What gets saved, and the 60-day rule
- **Listings changed:** everything in `data/` is committed by `github-actions[bot]`.
- **No listing changed:** nothing is committed. So the Actions page, not the commit history, is the record that a scan ran.
- **Keepalive:** if the repo has no commit for 7 days, the bot commits `data/meta.json` alone.

Why the keepalive exists: GitHub automatically turns off scheduled workflows in a public repo after 60 days with no repository activity. Its docs don't define "activity," or say whether a bot's commit counts. Other projects rely on bot commits for this, so it should work, but it's **not confirmed**. Listings may also go quiet for weeks, so a weekly commit is a cheap safeguard.

**If the schedule ever stops:**
1. Click the **Actions** tab, then **Daily scan**.
2. If a banner says the workflow was disabled, click **Enable workflow**.

**Trade-off of committing only on change (D-023):** on a day with no commit, `meta.json`, `last_seen.json`, and `companies_status.json` aren't saved. They can lag behind by a few days until the next commit. That day's numbers are still on the run's summary page.

## 9. Cost and limits
- Standard GitHub-hosted runners are free in public repos, so this costs $0.
- A job may run for up to 6 hours. Ours stops itself at 90 minutes.
- A run waiting in line is cancelled after 24 hours. A second run waits for the first to finish rather than overlapping it.

## 10. The morning email (Phase 5)
After a successful scan, the **Send morning email** step emails you a summary. It sends from a separate Gmail account used only for sending (D-009), to your personal inbox.

### The three secrets
The code reads exactly these names. Spelling and capitals must match.

| Secret name | What to paste as its value |
|---|---|
| `SMTP_USERNAME` | The sending Gmail account's full address |
| `SMTP_APP_PASSWORD` | That account's 16-letter app password. Spaces are fine; the code removes them |
| `EMAIL_TO` | The inbox that should receive the email (yours). Several can be separated by commas |

If any is missing, the run stays green: the email step logs a yellow warning naming the missing secret and skips sending. The values are never printed, and GitHub also hides secret values in logs.

### Make the app password (in the sending account)
1. Sign in to the **sending** Gmail account, not your personal one.
2. Turn on 2-Step Verification for it. Google only offers app passwords with it on, and not if it uses security keys only or has Advanced Protection.
3. Go to https://myaccount.google.com/apppasswords, type a name such as "Internship Scanner", and click **Create**.
4. Copy the 16-letter password Google shows. You won't be able to see it again, but you can always make a new one.

### Add the secrets to GitHub
1. On GitHub, open the repo and click **Settings** (under the repo name).
2. In the left sidebar, under **Security**, click **Secrets and variables**, then **Actions**.
3. On the **Secrets** tab, click **New repository secret**.
4. Type `SMTP_USERNAME` as the **Name**, paste the value into **Secret**, and click **Add secret**.
5. Repeat for `SMTP_APP_PASSWORD` and `EMAIL_TO`.

Secrets are never given to runs started from someone else's copy (fork) of the repo, so strangers can't read them.

### Try it without sending
On your Mac, `python -m scanner email --dry-run` writes the email to `outputs/email_preview.html` (open it in a browser) and `outputs/email_preview.txt`. It sends nothing and needs no secrets. `outputs/` is ignored by git.

### "New since last email"
After a send, the time and the ids of the listings already covered go into `data/meta.json` under `email`. No address or other personal data is stored. Before the first send, "new" means first seen within `new_badge_days`. On a day when no listing changed, nothing is committed (section 8), so that record isn't saved. That is harmless: no listing was added that day, so the next email still shows exactly what's new.

### If the email doesn't arrive
- Open the run's **Send morning email** step. "Email sent" means Gmail accepted it, so check spam first.
- "Missing secret(s)": add the named secret.
- `SMTPAuthenticationError`: the username or app password is wrong, or the app password was removed. Changing the sending account's Google password also removes its app passwords. Make a new one and update `SMTP_APP_PASSWORD`.
- To stop the emails, delete the secrets, or remove the app password in the sending account.

## Sources (read 2026-11-02, email sources 2026-11-03)
- Schedule syntax, delays, timezone, 60-day rule, and default-branch rule: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows and https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- Disabling and enabling workflows: https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows
- `GITHUB_TOKEN`, including that its commits don't start other workflows: https://docs.github.com/en/actions/concepts/security/github_token
- Workflow permissions settings: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository
- Limits: https://docs.github.com/en/actions/reference/limits
- Billing: https://docs.github.com/en/billing/concepts/product-billing/github-actions
- Bot name and email: https://github.com/actions/checkout
- Gmail SMTP for personal accounts (`smtp.gmail.com`, TLS/STARTTLS on port 587, authentication required): https://support.google.com/mail/answer/7104828
- Gmail SMTP ports (465 for SSL, 587 for TLS), Workspace admin page: https://knowledge.workspace.google.com/admin/gmail/send-email-from-a-printer-scanner-or-app
- App passwords: https://support.google.com/mail/answer/185833
- Repository secrets, and forks not receiving them: https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets
