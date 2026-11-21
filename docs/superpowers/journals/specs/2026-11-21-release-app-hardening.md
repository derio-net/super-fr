<!-- fr:journal-schema=4 -->
# Journal: 2026-11-21-release-app-hardening

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-21T11:34:23+00:00 input=true -->
### operator-brief · discovery · Operator brief, verbatim

Harden the release app's credential and ruleset bypass before its private key is stored, and automate the operator setup. Add a `security` lens.

Current state, checked 2026-11-20 in derio-net/super-fr:
- The operator ran `scripts/configure-main-protection.sh --stage bypass`. Repo variable FR_AUTOMATION_APP_ID=3994132 is set. Ruleset "protect main" (id 17365086) has rules [deletion, non_fast_forward] and bypass actor Integration 3994132 with bypass_mode "always".
- Secret FR_AUTOMATION_APP_KEY does not exist (`gh secret list` is empty). Because the variable is set, every release now fails at `publish` (`create-github-app-token`: "The 'private-key' input must be set to a non-empty string"; run 44683248617). Releases are blocked until this lands and the key is stored.
- `.github/workflows/release.yml:109-113` and `:298-302` mint the app token with `secrets.FR_AUTOMATION_APP_KEY` and use no `environment:`. A repo-level secret can be read by a workflow on any branch that anyone with push access pushes, so the key is not limited to code from `main`, despite what `docs/merge-protection.md` says.
- With bypass_mode "always" on the ruleset that holds deletion and non_fast_forward, a leaked key can force-push or delete `main`.
- `configure-main-protection.sh --stage bypass` sets the variable without checking that the secret exists. That is how releases got blocked.
- PR #1559 and issue #1580 listed only bypass → app release → require. They left out the runbook's steps 1–2 (install the app and generate the key; `gh secret set FR_AUTOMATION_APP_KEY`).

Asks:
1. Scope the key to a `release` environment whose deployment branch policy allows only `main`. Add `environment: release` to the two app-token jobs. A branch workflow must get no key.
2. Split the protection: one ruleset holds deletion + non_fast_forward with no bypass actors. A separate ruleset holds the required `ci-ok` check (the `require` stage), with the app as its only bypass actor. Migrate the existing "protect main" safely: never leave main unprotected between steps.
3. Write an idempotent, interactive operator script, run from the operator's own shell with their `gh`, that automates every step `gh` can do. Each step checks state first and is a no-op when already done. Every write is confirmed first. It has `--dry-run`. Steps: check the app installation and its permissions (contents and issues write only, this repo only); create or verify the environment and its branch policy; read the .pem path at a prompt, store it as the environment secret, and offer to delete the file; set FR_AUTOMATION_APP_ID last, only once the secret exists; then the ruleset stages. It must also handle the current half-done state (variable set, no secret, old combined ruleset). It must never print or log the key. Fold `configure-main-protection.sh` into it, or have it call that script, whichever is cleaner.
4. Detailed docs (`docs/merge-protection.md`) for the steps only the GitHub web UI can do: create the app if it is missing (exact permission settings), install it on the repo only, generate and download the private key, and revoke or rotate a leaked key. Also how to verify each step and how to roll back. Explain the security model: what the app can do, where the key lives, who can read it, and what a leak allows after this change.
5. Update #1580's steps in the PR body so the operator follows the new order.

Constraints: never change live repo settings, rulesets, variables or secrets yourself — the script is for the operator to run. Do not run the full suite on this host (it is loaded): run single test files only; CI is the suite evidence. Deliver a draft PR; never mark it ready or merge. Redact third-party identities.

<!-- fr:journal kind=decision scope=spec id=d-migration created=2026-11-21T11:34:23+00:00 decided_by=operator -->
### d-migration · decision · Keep "protect main", strip its bypass; the require step creates a new "require ci-ok" ruleset with check and app bypass in one write

Operator, round 1 question 1 (recommended option). Main's history rules are never touched, so main is never unprotected.

<!-- fr:journal kind=decision scope=spec id=d-tag-ruleset created=2026-11-21T11:34:23+00:00 decided_by=operator -->
### d-tag-ruleset · decision · Add a "protect release tags" ruleset on refs/tags/v* (deletion + update, no bypass)

Operator, round 1 question 2 (recommended option). A leaked key cannot move or delete a release tag; creation stays allowed.

<!-- fr:journal kind=decision scope=spec id=d-jwt-check created=2026-11-21T11:34:23+00:00 decided_by=operator -->
### d-jwt-check · decision · Prove the key belongs to the app with a locally signed JWT and GET /app before storing it

Operator, round 1 question 3 (recommended option). openssl is the only new dependency.

<!-- fr:journal kind=decision scope=spec id=d-environment created=2026-11-21T11:34:23+00:00 decided_by=operator -->
### d-environment · decision · release environment: main-only custom branch policy, can_admins_bypass false, no reviewers

Operator, round 1 question 4 (recommended option). Releases run unattended (push and daily cron).

<!-- fr:journal kind=decision scope=spec id=d-gate created=2026-11-21T11:34:23+00:00 decided_by=operator -->
### d-gate · decision · Gate tester, CI unit tests with a stub gh, one post-merge live row

Operator answered round 1 question 5 with gate devops. I then showed that fr ops apply runs only inside an ops-profile container (fr/ops/profile.py), which cannot see a host .pem or use the operator's own gh, and that adding an ops profile needs its own PR first. The operator chose option A in prose: gate tester, the script run from the operator's shell.

<!-- fr:journal kind=decision scope=spec id=d-merge-order created=2026-11-21T11:34:23+00:00 decided_by=operator -->
### d-merge-order · decision · Run the script from the PR branch before merging

Operator, round 1 question 6 (recommended option). The merge's own Release run then goes out as the app; require follows.

<!-- fr:journal kind=decision scope=spec id=d-fold-script created=2026-11-21T11:34:23+00:00 decided_by=operator -->
### d-fold-script · decision · Fold configure-main-protection.sh into one new bash script, scripts/setup-release-app.sh, and delete the old one

The operator delegated the choice. The stage semantics change (no bypass stage), so calling the old script would keep a shape that is now wrong. bash + jq + gh keeps the stub-gh test pattern.

<!-- fr:journal kind=lens scope=spec id=lens-security-1 created=2026-11-21T11:34:23+00:00 lens=security step=brainstorm -->
### lens-security-1 · lens · Operator asked for it: the change handles a GitHub App private key, a JWT, environment secrets and ruleset bypasses
