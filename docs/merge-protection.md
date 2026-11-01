# Merge protection for `main`

This repo's `main` can require the `ci-ok` check and an up-to-date branch. The
release workflow still has to push the release commit, so it does that as a
GitHub App, `derio-fr-automation`, which the ruleset lets bypass. Spec:
`docs/superpowers/specs/2026-10-11-merge-train-safety-design.md` §F.

## Why an app

A push made with the workflow's `GITHUB_TOKEN` triggers no workflow, so a
release commit pushed that way never gets CI, and a ruleset that requires checks
would refuse it outright. With the app's token the commit is pushed by a named
identity that the ruleset can exempt, and CI runs on it. `release.yml` then runs
once more on the release commit and finds nothing to do.

The release is a job graph, not one job (spec `2026-11-01-ci-speed` §3.D).
`prepare` and `publish` mint the app token; `prepare` stages the release
commit, six `test` shards and a `collect` job run the suite on exactly that
commit with no token at all, and `publish` pushes it only after `split-check`
has proved the shards ran every collected test. `publish` pushes only onto the
commit the release was staged on. If `main` moved in the meantime, or the push
loses the race, the run is superseded: it pushes nothing and exits 0, because
the push that moved `main` starts the Release run that releases. It never
retries. A run dispatched with an explicit `version` exits non-zero instead and
prints the `gh workflow run release.yml -f version=<X>` that re-dispatches it.
A refusal by the ruleset is never treated as superseded: it fails, naming the
bypass actor.

`release.yml` chooses the mode by the repo variable `FR_AUTOMATION_APP_ID`.
Unset, it falls back to `GITHUB_TOKEN`, which is why a repo that has not
adopted any of this keeps working.

## Residual risk

The release token is a ruleset bypass actor, so it can push to `main` past the
rules. It is scoped to this repo with contents and issues write only, minted
per job and revoked when the job ends, never persisted in the checkout's git
config, and withheld from the staged test run (`release.py` strips every forge
token from that subprocess and authenticates only its two `git push` calls).
Anything else that can run in the release job could still read it, so the job
runs only trusted code from `main`.

## Operator steps, in order

1. **Install the app.** In the org, install `derio-fr-automation` on the repo
   with contents write access. Generate a private key in the app's settings
   (the one step that needs the web UI).
2. **Store the key.** `gh secret set FR_AUTOMATION_APP_KEY < key.pem`, then
   delete the file. Nothing in the script below reads it.
3. **Stage `bypass`.**

       scripts/configure-main-protection.sh --repo OWNER/REPO --stage bypass --dry-run
       scripts/configure-main-protection.sh --repo OWNER/REPO --stage bypass

   This sets the variable `FR_AUTOMATION_APP_ID` and adds the app to the
   `protect main` ruleset as an always-bypass actor. The existing rules are
   merged, never overwritten.
4. **Cut a release as the app.** Merge a change with a fragment, or run the
   `Release` workflow by hand. Confirm the new `v*` tag's commit has a CI run.
5. **Stage `require`.**

       scripts/configure-main-protection.sh --repo OWNER/REPO --stage require

   This adds the `ci-ok` required check with "require branches to be up to
   date". It refuses until the bypass is in place and the newest `v*` tag's
   commit has a push-event run triggered by the app. `--force` skips only that
   release check, never the bypass check.

Both stages are idempotent: a second run reports that nothing changed. Run them
in this order, because requiring `ci-ok` before the release can bypass it would
make the next release fail with a protection refusal (`release.py` reports it
by name).

## Adopting this in another repo

Copy the pieces the repo needs: a `ci-ok` aggregate job in its CI (run on
`merge_group` too if it uses a merge queue), the `app-token` step and the
`steps.app-token.outputs.token || github.token` expression from `release.yml`,
and the script, whose ruleset name (`protect main`), app slug and variable name
are constants at the top. Install the app on the repo, then follow the steps
above with `--repo`.

## What the wave driver does with it

Nothing to configure. If the base branch's rules include a merge queue, the
driver enqueues an approved batch rather than merging it directly, reads the
queue's state each pass, and raises a `queue-ejected` need if the queue drops
it. If the rules require up-to-date branches, the driver updates the PR branch
before it merges. See spec §D and §E.
