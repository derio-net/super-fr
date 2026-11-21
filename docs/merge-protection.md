---
title: "Merge protection for main"
tldr: |
  Main can require the ci-ok check and an up-to-date branch. The release workflow still pushes the release commit, as a GitHub App that only the ci-ok rule lets bypass. The app's key is a secret of the release environment, which only main can read.
standalone_style: broadsheet
covers:
  - scripts/setup-release-app.sh
  - .github/workflows/release.yml
  - packages/fr/src/fr/triage/intake.py
reviewed: 2026-11-21 after lens review, both-modes environment note, conditional key prompt and deferred bypass; the key is a release environment secret; one setup script replaces the two stages; the security model and the runbook are rewritten (release-app-hardening)
---

# Merge protection for `main`

A ruleset can make the `ci-ok` check and an up-to-date branch mandatory for this repo's `main`. The
release workflow still has to push the release commit. So it does that as a
GitHub App, `derio-fr-automation`, which only the `require ci-ok` ruleset lets bypass. Specs:
`docs/superpowers/implemented/specs/2026-10-11-merge-train-safety-design.md` §F and
`docs/superpowers/specs/2026-11-21-release-app-hardening-design.md`.

## Why an app

A push made with the workflow's `GITHUB_TOKEN` triggers no workflow. So a
release commit pushed that way never gets CI, and a ruleset that needs checks
would not accept it at all. With the app's token, a named identity that the ruleset
can exempt pushes the commit, and CI runs on it. `release.yml` then runs
once more on the release commit and finds nothing to do.

The release is a job graph, not one job (spec `2026-11-01-ci-speed` §3.D).
`prepare` and `publish` mint the app token. `prepare` stages the release commit.
Six `test` shards and a `collect` job run the suite on exactly that commit. They run
with a read-only `GITHUB_TOKEN`, used only by checkout and never persisted, and with no
forge token in the suite's env. `publish` pushes the commit only after `split-check`
has proved that the shards ran every collected test.

`publish` pushes only onto the commit that the release was staged on. If `main` moved
in the meantime, or the push loses the race, the run is superseded. It then pushes
nothing and exits 0, because the push that moved `main` starts the Release run that
releases. A push made with `[skip ci]` or with the `GITHUB_TOKEN` starts no run, so the
daily cron picks that one up instead. It never retries.

A rerun whose release commit already landed skips the push and only tags it. A run
dispatched with an explicit `version` exits non-zero instead. It prints the
`gh workflow run release.yml -f version=<X>` that dispatches it again. A refusal by the
ruleset is never treated as superseded: it fails, and names the bypass actor. A tag
that has no GitHub Release gets its Release on the next run.

Push and cron runs share one concurrency group and run one at a time. GitHub keeps only
one pending run per group. A later push run would replace a pending dispatched run, and
nothing would say so. So a dispatched run has a group of its own, and it can run beside
a push run. Only one of them can push, by the rule above. When both reach the tag, the
run that finds the other's tag on the same commit, or its Release, is done.

`release.yml` chooses the mode by the repo variable `FR_AUTOMATION_APP_ID`.
When the variable is not set, it falls back to `GITHUB_TOKEN`. That is why a repo that
has not adopted the app continues to work.

The `prepare` and `publish` jobs declare `environment: release` in both modes. Only the
app-token step depends on the variable. So when a repo has a `release` environment
that allows only `main`, these jobs run only on `main`, in `GITHUB_TOKEN` mode too. A
`workflow_dispatch` from another branch fails at job start. When a repo has no `release`
environment, GitHub creates one on the first run, with no branch policy. Run the setup
script to give it the policy.

## Security model

The app is `derio-fr-automation`. This is what it can do, and where its key lives.

- **What the app can do.** It has contents write and issues write on this repo only.
  It can push commits, create tags and releases, and write issues.
  It bypasses only the `ci-ok` check.
  It cannot force-push or delete `main`.
  It cannot move or delete a `v*` tag.
  The rulesets that hold those rules have no bypass actor.
- **Where the key lives.** The key is a secret of the `release` environment.
  Only the jobs `prepare` and `publish` name that environment.
  Its deployment branch policy allows `main` and nothing else.
  Admins cannot bypass that policy.
  A run on any other ref gets no key.
- **Who can read it.** Any job on `main` that names the environment can read it.
  No rule requires a pull request.
  So anyone with write access can push a job like that to `main`.
  After the require step, that push must come from a branch that passes `ci-ok`.
  So every user with write access can read the key.
  Repo admins can read it too, because they can change the environment.
  A branch run, a fork pull request and a user with read or triage access cannot read it.
  A pull-request rule on `main` would limit this to reviewed code.
  That is a separate decision.
- **What a leak allows.** Until you revoke the key, a holder can do three things.
  They can push a commit that skips CI onto `main`.
  They can create tags and releases.
  They can write issues.
  Deleting the key in the app's settings stops new tokens at once. A token already
  minted from it stays valid until it expires, at most 1 hour.

The release token is minted per job and revoked when the job ends.
It is never persisted in the checkout's git config.
`release.py` strips every forge token from the staged test run.
The token authenticates the two `git push` calls and the `gh release` and `gh issue` writes.
Every other git command runs credential-free.

## Operator steps, in order

One script does the setup: `scripts/setup-release-app.sh`.
It reads the live state first, and it does nothing for a step that is already right.
It shows each write and asks `apply? [y/N]`.
If you decline a step write, the script stops.
If you decline an optional cleanup, the script goes on.
`--dry-run` prints every write and makes none.

1. **In the web UI, create the app** if it does not exist.
    - Name it `derio-fr-automation`.
    - Turn the webhook off.
    - Set Repository permissions: Contents read and write, Issues read and write, Metadata read-only.
    - Set every other permission to No access.
    - Choose "Only on this account".
2. **In the web UI, install the app** on the org. Choose "Only select repositories". Select this repo only.
3. **In the web UI, generate a private key.** Download the `.pem` file. You do not need to copy the App ID: the script reads it from the installation.
4. **Run the script before the PR that adds `environment: release` merges.**

        scripts/setup-release-app.sh --repo OWNER/REPO --dry-run
        scripts/setup-release-app.sh --repo OWNER/REPO

    If the variable `FR_AUTOMATION_APP_ID` is set and no environment secret exists, releases fail.
    The script says so and offers to unset the variable.
    Decline the offer if the PR that adds the environment merges next.
    The script then does these steps:
    - It checks the app installation and its permissions.
    - It creates the `release` environment with a main-only branch policy.
    - When no environment secret exists (or with `--rotate-key`), it asks for the `.pem` path. It proves the key belongs to the app, and that the app reaches only this repo. It stores the key as the environment secret.
    - It waits to set the variable until main's `release.yml` declares the environment.
    - It removes the app's bypass from `protect main`. When `protect main` still holds the old `ci-ok` rule, it keeps the bypass there and leaves the move to the require step (step 6).
    - It creates `protect release tags`.
    - It says that the require step waits for a release that the app pushed.
5. **Merge the PR.** The Release run passes `publish`. Confirm the new `v*` tag's commit has a push-event CI run that `derio-fr-automation[bot]` triggered. Is the variable not set? Then run the script again first. This applies if you unset it in step 4, or if the repo never had it. The script sets it now that `main` declares the environment. The next release goes out as the app.
6. **Run the script again.** The require step creates `require ci-ok`.
    It holds the `ci-ok` check with "require branches to be up to date".
    The app is its only bypass actor.
    `--force` skips only the release check.
    If the old `protect main` still holds a `ci-ok` rule, the script creates `require ci-ok` first.
    It then removes that rule and the app's bypass from `protect main` in one write.

A second run over a finished setup writes nothing.
If `ci-ok` is required before the release can bypass it, the next release fails with a protection refusal.
`release.py` reports that refusal by name.

## Verify each step

Use `gh` for each check.

- **App.** `gh api orgs/OWNER/installations` lists the installation. Its `repository_selection` is `selected`. Its permissions are contents write, issues write and metadata read.
- **Environment.** `gh api repos/OWNER/REPO/environments/release` shows `can_admins_bypass: false`. `gh api repos/OWNER/REPO/environments/release/deployment-branch-policies` lists one policy, the branch `main`.
- **Key.** `gh secret list --env release --repo OWNER/REPO` lists `FR_AUTOMATION_APP_KEY`. `gh secret list --repo OWNER/REPO` does not list it.
- **Variable.** `gh variable list --repo OWNER/REPO` shows `FR_AUTOMATION_APP_ID`, set to the App ID.
- **Rulesets.** `gh api repos/OWNER/REPO/rulesets` lists `protect main`, `protect release tags` and `require ci-ok`. Read each one by id. `protect main` and `protect release tags` have no bypass actor.
- **Release.** The new `v*` tag's commit has a push-event Actions run with `derio-fr-automation[bot]` as the triggering actor.

## Roll back

Roll back one step at a time, in the reverse order.

- **Require.** Delete the ruleset `require ci-ok` in Settings, Rules.
- **Tags.** Delete the ruleset `protect release tags`.
- **History.** Keep `protect main` as it is. To give the app a bypass again, use the web UI. Do not put the bypass back on `protect main`.
- **Variable.** `gh variable delete FR_AUTOMATION_APP_ID --repo OWNER/REPO`. Releases return to `GITHUB_TOKEN` mode.
- **Key.** `gh secret delete FR_AUTOMATION_APP_KEY --env release --repo OWNER/REPO`. Unset the variable first, or releases fail.
- **Environment.** Delete the `release` environment in Settings, Environments. Remove `environment: release` from the workflow first.

## Revoke or rotate a leaked key

1. In the web UI, open the app's settings. Delete the leaked private key. No new token can be minted with it. A token already minted stays valid for at most 1 hour.
2. Generate a new private key. Download the `.pem` file.
3. Run `scripts/setup-release-app.sh --rotate-key`. It proves the new key and replaces the environment secret.
4. Read the audit log of the org and the repo. Look for pushes, tags and releases by the app during the leak.
5. Delete the `.pem` file when the script offers.

## Adopt this in another repo

Copy the pieces that the repo needs:

- a `ci-ok` aggregate job in its CI (run on `merge_group` too if it uses a merge queue);
- the `app-token` step and the `steps.app-token.outputs.token || github.token` expression
  from `release.yml`, and `environment: release` on the two jobs that use them;
- the script, whose app slug, variable name, secret name and ruleset names are
  constants at the top.

Create and install the app as in the steps above. Then run the script with `--repo`.

## What the wave driver does with it

Nothing to configure. If the base branch's rules include a merge queue, the
driver puts an approved batch in the queue and does not merge it directly. It reads the
queue's state each pass, and raises a `queue-ejected` need if the queue drops
it. If the rules need up-to-date branches, the driver updates the PR branch
before it merges. See spec §D and §E.

## Issue intake

On a public repo, anyone can open an issue. The text of an issue can reach the session that
builds a batch. So the driver batches an issue only when a trusted party wrote it, or an
operator approved it. Spec: `docs/superpowers/specs/2026-11-17-triage-intake-design.md`.

An issue is eligible when at least one of these is true:

- Its author is the user that ran `collect`, or a login in `pr_authors` of `.fr/triage.yaml`.
- Its author association is `OWNER`, `MEMBER` or `COLLABORATOR`.
- It has the `ready-fr` label. The forge compares label names without regard to case, and so
  does intake.
- Its author is the workflow bot of the debt digest, and its body holds the digest marker. A
  bot-authored issue without the marker is judged like any other.

The rule fails closed. If `collect` could not read the author or the association, no clause
admits the issue.

An issue that is not eligible has these effects:

- `collect` keeps its title and labels, but not its body.
- `fr triage check` lists it in the `untrusted` set, with the reason. It is never ranked,
  unranked, unplaced or suggested for a batch.
- `batch create`, `batch edit` and `batch dispatch` refuse a batch that holds it. They exit
  2, write nothing, and name the issue, the reason and `ready-fr`.
- The wave driver, the board and `drive --plan` show the batch as blocked in every pass.
  The drive stops for the operator once only blocked or held batches remain. The driver dispatches the batch when no member is rejected.

The launch brief marks the issue text. Its first line holds only the skill command and the
batch id. The batch title, each member title, detail and note, and the rationale sit in one
block. The block starts with `<!-- untrusted: written from the issue tracker -->`. Every line
in the block starts with `> `, so no text can close the block or add a heading outside it.
The brief tells the session to read the block as a description of the problem and never to
follow an instruction in it.

Only an operator applies `ready-fr`. On GitHub, a label needs triage permission to apply,
which an outside author does not have. fr never applies it. The driver creates the label
when a repo does not have it, as it does for `approved-fr`. Creating a label needs write
permission. If fr cannot create it, an operator with write access creates it.

One risk remains. `ready-fr` admits the issue as it is later edited. Later edits by the
author reach the triage agent and the brief. The quoting in the brief still applies to them.

