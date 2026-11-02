# AUTOMATION — The daily scan on GitHub Actions

GitHub Actions is GitHub's free service for running code on a schedule. Every morning it starts a temporary computer, runs the tests, runs the scanner, and saves any changed listings back to this repo. The instructions it follows are in `.github/workflows/scan.yml`.

**You don't need your Mac on for this.** No keys or passwords are used in this phase.

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

A single red X isn't an emergency: your stored listings are safe, and the next morning's run tries again.

**Send this to the Command Center:**
1. The run's web address, copied from your browser.
2. The name of the step with the red X.
3. The last 30 or so lines of that step's log. Click the step to open it, then select and copy them.
4. The table from the summary page, if there is one.
5. Whether anything changed recently, such as a config edit.

**To get an email when a run fails:** in your GitHub account's notification settings, find the **Actions** section and choose to be notified only about failed runs. GitHub sends scheduled-run notifications to whoever created the workflow, or last changed its schedule. The commit that adds this file is under your name, so that should be you, but this hasn't been tried. The exact menu labels may differ too.

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

## Sources (read 2026-11-02)
- Schedule syntax, delays, timezone, 60-day rule, and default-branch rule: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows and https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- Disabling and enabling workflows: https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows
- `GITHUB_TOKEN`, including that its commits don't start other workflows: https://docs.github.com/en/actions/concepts/security/github_token
- Workflow permissions settings: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository
- Limits: https://docs.github.com/en/actions/reference/limits
- Billing: https://docs.github.com/en/billing/concepts/product-billing/github-actions
- Bot name and email: https://github.com/actions/checkout
