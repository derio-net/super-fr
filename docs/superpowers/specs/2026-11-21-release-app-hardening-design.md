# Release app hardening and operator setup

## Background

The release workflow can push as the `derio-fr-automation` GitHub App (spec
`2026-10-11-merge-train-safety` §F), so a ruleset that requires the `ci-ok`
check can let the release commit through. The state of `derio-net/super-fr` on
2026-11-20:

- `scripts/configure-main-protection.sh --stage bypass` has run. The repo
  variable `FR_AUTOMATION_APP_ID` is set, and the ruleset "protect main"
  (`deletion`, `non_fast_forward`) lists the app as a bypass actor with
  `bypass_mode: always`.
- No secret `FR_AUTOMATION_APP_KEY` exists. Because the variable is set, every
  release fails at `publish` (`create-github-app-token`: the private-key input
  is empty). Releases are blocked.
- `.github/workflows/release.yml` mints the app token in `prepare` and `publish`
  from `secrets.FR_AUTOMATION_APP_KEY` with no `environment:`. A repository
  secret is readable by a workflow on any branch that anyone with push access
  pushes, so the key is not limited to code from `main`.
- The bypass sits on the ruleset that holds `deletion` and `non_fast_forward`,
  so a leaked key can force-push or delete `main`.
- `--stage bypass` sets the variable without checking that the key exists.
  That is how releases got blocked.
- PR #1559 and issue #1580 list only bypass → app release → require. They leave
  out installing the app, generating the key and storing it.

## Requirements

R1. In `.github/workflows/release.yml` the two jobs that mint the app token
(`prepare`, `publish`) declare `environment: release`. No other job declares
that environment or reads `FR_AUTOMATION_APP_KEY`.

R2. The release key is an environment secret of `release`. The environment's
deployment branch policy is a custom policy that allows exactly the branch
`main`, with `can_admins_bypass: false`, no required reviewers and no wait
timer. A workflow run on any other ref gets no key.

R3. One interactive operator script, `scripts/setup-release-app.sh`, replaces
`scripts/configure-main-protection.sh`, which is deleted. It runs from the
operator's own shell with their `gh`, against `--repo OWNER/REPO` (default: the
current repo).

R4. The script runs its steps in a fixed order: app, environment, key,
variable, history ruleset, tag ruleset, require. Each step reads the live state
first and is a no-op, saying so, when the state is already correct. A second run
over a finished setup writes nothing.

R5. Every write is shown and confirmed first, with a default of no. A declined
write stops the script, so no later step runs on a half-made state.
`--dry-run` reads the state, prints each write that it would make, and writes
nothing.

R6. The app step checks that `derio-fr-automation` is installed on the owner,
that its `repository_selection` is `selected`, and that its permissions are
exactly contents write, issues write and metadata read. It reads the
installation's repository list and requires exactly this repo. When `gh`
cannot read that list, the script prints the installation's settings URL and
asks the operator to confirm that only this repo is selected. Any other
permission, or `all` repositories, stops the script and names the web UI fix.

R7. The environment step creates `release` when it is absent and corrects it
when its policy differs from R2. It adds a `main` branch policy and removes any
other branch or tag policy.

R8. The key step reads the `.pem` path at a prompt. It refuses a file that is
not a PEM private key. It proves the key belongs to the app: it signs a
short-lived JWT locally with `openssl` and calls `GET /app`, which must return
the app's id. Only then does it store the file as the `release` environment
secret `FR_AUTOMATION_APP_KEY`, from the file on stdin, and offer to delete the
file. It is a no-op when the environment secret exists, unless the operator
asks to replace it (`--rotate-key`).

R9. The script never prints, logs or passes in argv the key or the JWT. The key
reaches only `openssl` (by path) and `gh secret set` (on stdin). The JWT reaches
only the `Authorization` header, read by `curl` from a file descriptor.

R10. A repository-level secret `FR_AUTOMATION_APP_KEY` is reported as a leak
path and the script offers to delete it, once the environment secret exists.

R11. The variable step sets `FR_AUTOMATION_APP_ID` to the installation's app id
only when the `release` environment secret exists. The script finds the
half-done state, where the variable is set and no environment secret exists, before any
other step. It then says that releases are failing, and offers to unset the
variable, which brings releases back to `GITHUB_TOKEN` mode. When the key step
then succeeds in the same run, the variable step sets the variable again.

R12. The history step makes "protect main" hold `deletion` and
`non_fast_forward` with no bypass actors. It removes the app's bypass from the
existing ruleset in place and keeps its id and every other rule. It creates
the ruleset when absent. No write in any step removes either rule from it.

R13. The tag step makes a ruleset "protect release tags" on `refs/tags/v*`
that holds `deletion` and `update`, with no bypass actors. The app can still
create a tag.

R14. The require step makes a ruleset "require ci-ok" on the default branch.
It holds a `required_status_checks` rule for `ci-ok`, with "require branches to
be up to date", and lists the app as its only bypass actor (`always`). It
creates the ruleset with its rule and its bypass actor in one write.
It runs only when all of these hold: R12's history ruleset has no bypass actor,
the environment secret and the variable exist, and the newest `v*` tag's commit
has a push-event run triggered by the app. When the release check fails, the
step says what it waits for and the script exits 0. `--force` skips only the
release check. When "protect main" still holds a `required_status_checks` rule
from the old script, the step creates "require ci-ok" first and then removes
that rule from "protect main".

R15. `docs/merge-protection.md` documents the steps that need the GitHub web
UI. These are: create the app if it is missing, with its exact permission settings;
install it on this repo only; generate and download the private key; revoke or
rotate a leaked key. It also says how to verify each step and roll it back, the order to follow (the
script before this PR's merge, an app-pushed release, then the require step),
and the security model: what the app can do, where the key lives, who can read
it, and what a leak allows after this change.

R16. The PR body replaces the operator steps of #1580 with the new order.

## Design

### Workflow (R1, R2)

`prepare` and `publish` gain `environment: release`. GitHub then hands the jobs
the environment's secrets only when the run's ref passes the branch policy, and
refuses the job on any other ref. `secrets.FR_AUTOMATION_APP_KEY` resolves to
the environment secret. The app-token step's `if: vars.FR_AUTOMATION_APP_ID !=
''` is unchanged, so a repo with no variable keeps `GITHUB_TOKEN` mode. The
environment applies in that mode too, and it is harmless on `main`. The header
comment and `tests/unit/test_release_workflow.py` pin the shape: exactly those
two jobs declare the environment, and only they reference the secret.

A job that names an environment that does not exist creates it with no
protection. This is why the runbook runs the script before this PR merges
(R15). The script also corrects an environment that was created that way (R7).

### Script (R3-R14)

The script is bash, `jq` and `gh`, like the script it replaces. The tests can then use the same stub
`gh` on `PATH` (`tests/unit/test_setup_release_app.py`). It takes `--repo`,
`--dry-run`, `--force` and `--rotate-key`. Prompts read stdin. The script
runs with `set -euo pipefail` and never with `set -x`.

```
preflight   half-done check (R11): variable set, no env secret -> offer unset
1 app       installation, selection, permissions, repo list (R6)
2 env       release + main-only policy, no admin bypass (R7)
3 key       prompt path, PEM check, JWT GET /app, gh secret set --env (R8-R10)
4 variable  FR_AUTOMATION_APP_ID, only if the env secret exists (R11)
5 history   "protect main": deletion + non_fast_forward, no bypass (R12)
6 tags      "protect release tags": v* deletion + update, no bypass (R13)
7 require   "require ci-ok" + app bypass, after an app-pushed release (R14)
```

Each step reads state, prints `ok: <what>` when nothing is needed, or prints
the intended write (method, path, body with no secret) and asks `apply? [y/N]`.
`--dry-run` prints `would: …` and continues as though the write were made, so
the whole plan shows in one run.

The JWT is `{"alg":"RS256","typ":"JWT"}` and `{"iat": now-60, "exp": now+540,
"iss": <app id>}`, base64url-encoded with `openssl base64`, signed with
`openssl dgst -sha256 -sign <path>`. `curl` reads the header from a process
substitution (`-H @<(…)`), so the JWT is never in argv. `GET
https://api.github.com/app` must answer with the app id. The step reports a
mismatch or an HTTP error with the status only, never the body.

### Security model (R15)

After this change:

- **What the app can do.** Contents write and issues write on this repo only. It
  can push commits, create tags and releases, and write issues. It bypasses only
  the `ci-ok` check. It cannot force-push or delete `main`, or move or delete a
  `v*` tag, because those rulesets have no bypass actor.
- **Where the key lives.** In the `release` environment secret. Jobs on `main`
  that declare the environment can read it. A branch workflow cannot.
- **Who can read it.** Code on `main`, which reaches `main` only through a
  reviewed PR. Repo admins can change the environment, so they can also reach
  the key.
- **What a leak allows.** Until the key is revoked: pushing a commit that skips
  CI onto `main`, creating tags and releases, writing issues. Revoking it in the
  app's settings ends that at once.

## Verification

gate: tester
- release-key-environment-scoped: none — (R1) a CI unit test reads `release.yml` and pins that exactly `prepare` and `publish` declare `environment: release` and only they reference the secret
- setup-script-app-check: none — (R6) CI unit tests with a stub `gh`: exact permissions, selected repos, the unreadable-list confirm, and each refusal
- setup-script-environment: none — (R2, R7) CI unit tests with a stub `gh`: create, correct and keep the environment and its main-only policy
- setup-script-key-never-printed: none — (R8, R9, R10) CI unit tests with a stub `gh` and `curl` and a test key made by `openssl`: the JWT check, the env secret write from stdin, and no key or JWT byte in any output, log or argv
- setup-script-variable-last: none — (R11) CI unit tests with a stub `gh`: the half-done state, the refusal without the secret, and the set after it
- setup-script-rulesets: none — (R12, R13, R14) CI unit tests with a stub `gh`: bypass stripped in place, the tag ruleset, require's preconditions and its order when the old rule is present
- setup-script-idempotent-confirmed: none — (R4, R5) CI unit tests with a stub `gh`: a rerun writes nothing, a declined write stops, `--dry-run` writes nothing
- release-app-setup-live: live — (R2, R14) only the live repo shows a release pushed as the app from the `release` environment, a branch run refused the key, and `ci-ok` required

## Test Plan

Post-merge, operator-driven. The script steps run from the PR branch before the
merge; the rest after it.

1. Before merge, from the PR branch: `scripts/setup-release-app.sh --dry-run`,
   then `scripts/setup-release-app.sh`. It finds the half-done state, checks
   the app, creates `release`, stores the key and strips the bypass. It then adds
   the tag ruleset, and says that `require` waits for an app-pushed release.
2. Rerun it: every step prints `ok`, and nothing is written.
3. Merge the PR. The merge's Release run passes `publish`, and the new `v*`
   tag's commit has a push-event CI run triggered by `derio-fr-automation[bot]`.
4. Push a throwaway branch with a workflow that declares `environment: release`
   and prints whether the secret is empty. The job is refused by the branch
   policy. Delete the branch.
5. Run the script again: the `require` step creates "require ci-ok". Record the
   walk on `release-app-setup-live`, and then on `ci-ok-required-on-main`
   (feature `2026-11-19-local-suite-cost`).
