# STATUS — Current state (updated 2026-11-02)

## Phase
P0 — Setup: DONE.
P1 — Plan: DONE, **awaiting Lucas's approval**. Do not start P2 until approved.

## Environment
- Repo: github.com/lucaseastman9884-cloud/Internship-Scanner (public)
- Local folder: ~/Documents/GitHub/Internship-Scanner (cloned with GitHub Desktop)
- Mac, Claude Code v2.1.316, Claude Pro
- Lucas is new to GitHub, terminal, and deployment: explain any step he must do himself.

## Done
- Spec, config, decisions (D-001–D-008), and source research written in docs/.
- P1: docs/PLAN.md, config/config.yaml, config/companies.yaml (44 companies: 21 live boards, 23 manual), .gitignore, README stub, proposed decisions D-009–D-013.
- P1 work is committed locally on branch `phase-1-plan`. Not pushed; Lucas pushes with GitHub Desktop.

## Seed companies (from the old Internship Log)
Bankers Trust, Wintrust Financial, Federal Reserve Bank of Kansas City, CIBC, Corient, Commerce Bank, UHY, Northwestern Medicine, RR Donnelley, Pella, BMO, Fifth Third, Lazard, CliftonLarsonAllen, Forvis Mazars, American Equity, Bank Iowa, BGM Group, KPMG.
ATS check results are in config/companies.yaml.

## Next
Lucas reviews docs/PLAN.md and decides D-009–D-013. Then P2 — Pipeline core (see SPEC "PHASES").

## Open questions
- Email sending method: Gmail SMTP recommended (D-009). Awaiting decision.
- Workday terms: reconfirm D-002 before P3 (D-010).
- Seasons: live boards show Spring 2027 and Winter 2027 internships, which `seasons` in the config does not include. Add them? Config left exactly as written until Lucas decides.
- Git email: commit 820b3ab, already on GitHub, records Lucas's Gmail as author, and his git setup would add it to future commits. P1 commits used his GitHub noreply address. He needs to turn on GitHub's email privacy, and decide whether to rewrite that one commit.
- BGM Group: which firm is it, bgmcpa.com or bgmgroup.com?
- Apollo Gmail-account search and monthly reset — test in P6.

## Known limits of P1 verification
- UNVERIFIED items are listed in PLAN section 5 and section 7.
- Many `cities` values are "expected," not observed. Each entry's notes say which.
