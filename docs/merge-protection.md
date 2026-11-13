---
title: "Merge protection for main"
tldr: |
  Main can require the ci-ok check and an up-to-date branch. The release workflow still pushes the release commit, as a GitHub App the ruleset lets bypass.
standalone_style: broadsheet
covers:
  - scripts/configure-main-protection.sh
  - .github/workflows/release.yml
reviewed: 2026-11-11 docs-currency phase 3
---

# Merge protection for `main`

A ruleset can make the `ci-ok` check and an up-to-date branch mandatory for this repo's `main`. The
release workflow still has to push the release commit. So it does that as a
GitHub App, `derio-fr-automation`, which the ruleset lets bypass. Spec:
`docs/superpowers/implemented/specs/2026-10-11-merge-train-safety-design.md` §F.

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
ruleset is never treated as superseded: it fails, and names the bypass actor.

`release.yml` chooses the mode by the repo variable `FR_AUTOMATION_APP_ID`.
When the variable is not set, it falls back to `GITHUB_TOKEN`. That is why a repo that
has not adopted any of this continues to work.

## Residual risk

The release token is a ruleset bypass actor, so it can push to `main` past the
rules. It is scoped to this repo with contents and issues write only. It is minted
per job and revoked when the job ends, and never persisted in the checkout's git
config. It is kept from the staged test run (`release.py` strips every forge
token from that subprocess). The token authenticates the two `git push` calls and the
`gh release` and `gh issue` writes. Every other git command runs credential-free.

Anything else that can run in the release job could still read it, so the job
runs only trusted code from `main`.

## Operator steps, in order

1. **Install the app.** In the org, install `derio-fr-automation` on the repo
   with contents write and issues write access. Generate a private key in the app's settings
   (the one step that needs the web UI).
2. **Store the key.** `gh secret set FR_AUTOMATION_APP_KEY < key.pem`, then
   delete the file. Nothing in the script below reads it.
3. **Stage `bypass`.**

       scripts/configure-main-protection.sh --repo OWNER/REPO --stage bypass --dry-run
       scripts/configure-main-protection.sh --repo OWNER/REPO --stage bypass

   This sets the variable `FR_AUTOMATION_APP_ID` and adds the app to the
   `protect main` ruleset as an always-bypass actor. The script merges the
   rules that are already there, and never overwrites them.
4. **Cut a release as the app.** Merge a change with a fragment, or run the
   `Release` workflow by hand. Confirm the new `v*` tag's commit has a CI run.
5. **Stage `require`.**

       scripts/configure-main-protection.sh --repo OWNER/REPO --stage require

   This adds the `ci-ok` required check with "require branches to be up to
   date". It stops with an error until the bypass is in place.
   It also stops until the newest `v*` tag's commit has a push-event run that the app triggered.
   `--force` skips only that release check, never the bypass check.

Both stages are idempotent: a second run reports that nothing changed. Run them
in this order. If `ci-ok` is a required check before the release can bypass it, the next
release fails with a protection refusal (`release.py` reports it by name).

## Adopt this in another repo

Copy the pieces that the repo needs:

- a `ci-ok` aggregate job in its CI (run on `merge_group` too if it uses a merge queue);
- the `app-token` step and the `steps.app-token.outputs.token || github.token` expression
  from `release.yml`;
- the script, whose ruleset name (`protect main`), app slug and variable name are
  constants at the top.

Install the app on the repo, then follow the steps above with `--repo`.

## What the wave driver does with it

Nothing to configure. If the base branch's rules include a merge queue, the
driver puts an approved batch in the queue and does not merge it directly. It reads the
queue's state each pass, and raises a `queue-ejected` need if the queue drops
it. If the rules need up-to-date branches, the driver updates the PR branch
before it merges. See spec §D and §E.
