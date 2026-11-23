# Draft PRs that settle — wait for mergeability and CI before delivery ends

## Background

When super-fr delivers a draft PR outside the wave driver (fr-goal's `deliver`, the end
of fr-debugging, an archive or close-out opened by hand), the session stops as soon as
the PR exists. Nothing checks whether the PR merges cleanly into its base or whether its
CI ends green. The operator finds out later, and by then the session that could fix it
has ended.

What exists today:

- `fr pr create` (`packages/fr/src/fr/commands/pr_cmd.py`) is the one place fr's skills
  open a PR. It always opens a draft and records the PR on the run cursor (`RunState.pr`).
- Under `tests: ci` (`.fr/ci.yaml`), `deliver` calls `fr.run.ci_evidence.verify_ci`.
  That call proves the gate checks are green on the code tree (exit 75, `CiPending`, while
  they run). It is test evidence only: it does not look at mergeability, and nothing checks
  again after the last body edit or `chore(fr):` push.
- `GhClient.pr_view` returns `mergeable` and `merge_state`, and
  `fr.triage.mergeability.conflicting` is the one predicate for "this PR conflicts"
  (`CONFLICTING` or `DIRTY`; `BLOCKED` is branch protection, not a conflict).
  `pr_required_checks` and `pr_checks` read checks.
- The wave merge queue (spec `2026-11-19-wave-merge-queue`) owns every PR the driver
  manages: batch PRs (`feat/batch-*`, `fix/batch-*`), the collected close-out
  (`chore/closeout-<date>-<n>`), legacy per-batch archive PRs (`chore/closeout-<batch
  branch>`), the per-wave export PR and DevOps housekeeping PRs. It hands conflicts and red
  combinations back to the PR's session (R6, R13). The driver's early hand-backs do the same
  before approval, and only to an idle session. Under `land: push` it leases the landing on
  the head it built (R10). It pins approval to the PR's patch-id: a clean merge of the base
  keeps the approval, a hand-resolved merge voids it (R12). A collected close-out is queued
  only at the head its verb recorded. A PR outside those kinds never enters the queue.

So a second fix loop on a driver-managed PR would compete with the driver's hand-backs.
It would also void the lease or the recorded close-out head. The new behaviour applies only
to PRs outside the driver's concerns.

## Requirements

R1. A repo setting `git.settle` has two keys, `conflicts` and `ci`, each `off`, `report` or `fix`, both defaulting to `fix`. It is read from the default branch like every key of `.fr/settings.yaml`, shown by `fr settings show`, and documented by `fr settings init` from the schema.
R2. `fr pr settle` reads this branch's open PR through the repo's forge adapter and reports two states. The conflict state is `clean`, `conflicting` (by `fr.triage.mergeability.conflicting`) or `unknown` (the forge has not computed it yet). The CI state is `green`, `red` with the failing check names, `pending` or `none`. The checks read are `.fr/ci.yaml`'s `gate_checks` when declared, else the base's required checks, else every check on the head. A repo whose services report `ci none` has CI state `none`.
R3. `fr pr settle --wait <seconds>` polls until no state it reports is `unknown` or `pending`, or until the wait ends. The wait has a default and a ceiling, both below 600 seconds, so one call fits in an agent's shell tool. It never pushes, edits a PR, marks a PR ready or merges.
R4. Under the effective modes, `fr pr settle` exits 0 when every concern is settled and not failing under `fix` (a concern under `report` or `off` never fails). It exits 4 when a concern under `fix` is `conflicting` or `red`, and prints what to do. It exits 75 when a state is still `unknown` or `pending` when the wait ends. It exits 2 on a refusal (no open PR, unreadable settings or override). Under `report` a bad state is printed and never changes the exit code.
R5. A PR on a branch the wave driver owns (`feat/batch-*`, `fix/batch-*`, `chore/closeout-*`) is driver-managed. For it, `fr pr settle` reads nothing from the forge, prints that the wave driver's queue and hand-backs own the PR, and exits 0, whatever the modes. The batch and close-out dispatch briefs say the same.
R6. One feature or one bug can override either key for its own PR, and the override is recorded. For a run with a spec, it is a `settle.conflicts: <mode> — <reason>` or `settle.ci: <mode> — <reason>` line in the spec's `## Verification` section. For an fr-debugging session, it is a debug-journal decision with id `settle-conflicts` or `settle-ci` whose title is the mode and whose body is the reason. The reason is required. The override takes precedence over the repo setting. A malformed override is an error that names the line, never ignored.
R7. The PR body fr renders at `deliver` lists every override in force, with its reason, under the run's settle state. A run with no override says the repo setting applies.
R8. fr-goal's `deliver` derives a `settle` witness itself; it is never passed in. Under `fix`, resolve refuses while the PR is `conflicting` or `red`, and holds the unit with exit 75 while a state is `unknown` or `pending`, so fixes land before `deliver` is done and the run's `tests` evidence covers the fixed tree. Under `report`, the witness records the state and refuses nothing. Under `off` it records `off`. For a driver-managed PR it records `managed`.
R9. A fix keeps the PR's history and its approval as the queue reads them. A conflict is fixed by merging `origin/<base>` into the branch, never by rebase or force-push. A red check is fixed by an ordinary commit. fr-goal and fr-debugging allow at most three fix rounds. After that the session stops and reports, and the PR stays as it is. The only ways forward are an override with its reason (R6) or a finding filed through the journal.
R10. fr-debugging runs `fr pr settle` as its last step, after `fr pr create`, under the same modes and the same fix rules.
R11. A forge whose client cannot read a PR's mergeability or checks (glab and tea today) gives the state `unsupported`. That state is printed and recorded, never read as `clean` or `green`, and never a refusal.

## Design

### A. The setting (R1)

`fr.settings.model.Git` gains `settle: Settle`, a closed model with `conflicts` and `ci`,
each a closed-vocabulary field over `SETTLE_MODES = {"off", "report", "fix"}` with the
two-line `description=` every field carries. `fr settings show` lists
`git.settle.conflicts` and `git.settle.ci`. `.fr/settings.yaml` is not an artifact kind,
so no stamp moves. But `Settings` is `extra="forbid"`, so a repo that writes `git.settle`
makes an `fr` older than this change refuse its settings. That is how every new key has
worked since the settings spec, and the change fragment says so.

### B. The engine (R2–R5, R11)

A new package, `fr/settle/`:

- `model.py`: `ConflictState`, `CiState`, `Modes`, `Verdict` (states, failing checks,
  effective modes with their source, exit code, the lines to print).
- `evaluate.py`: `evaluate(view, checks, gate_names, modes, *, ci_none) -> Verdict`. It is
  pure, so every mode × state pair is a table test. `unknown` covers both GitHub's
  `mergeable: UNKNOWN` and a merge state it has not computed.
- `managed.py`: `driver_managed(branch) -> bool`, using the prefixes from
  `fr.triage.batch` (`BRANCH_PREFIX`, `FIX_BRANCH_PREFIX`) and the close-out prefix, so the
  names live in one place.
- `modes.py`: `effective_modes(repo_root, *, spec, debug_journal) -> Modes`, which applies
  the setting, then the override (R6), and records where each mode came from.
- `poll.py`: the bounded poll over an injected clock and sleeper. It re-reads the view and
  checks until nothing is `unknown` or `pending` or the wait ends.

The verb is `fr pr settle [--wait <s>] [--json]` in `pr_cmd.py`. It finds the PR from the
run cursor's `pr` when there is a run, else from the forge's open PR for the branch. It
reads check names the way `ci_evidence` does (`load_gate_checks`, then
`required_check_names`), and asks `fr services` for `ci none`. A client without
`pr_view` or checks gives `unsupported` (R11).

### C. Overrides (R6, R7)

`fr.verification.spec_section` accepts two more grammar lines in `## Verification`:
`settle.conflicts: <mode> — <reason>` and `settle.ci: <mode> — <reason>`. Like every
grammar line, a line that looks like one of them but breaks it is an error naming the
line. A missing reason is an error. The debug-journal form is a `decision` entry with id
`settle-conflicts` or `settle-ci`, read from the branch's one debug journal. The plan
finds out whether either form is a shape change of the `spec` or `journal` kind under
`.claude/rules/artifact-versioning.md`. If it is, the same PR ships the stamp bump, the
migration and the validator.

`fr.record.pr_body` renders a `## PR settle` section: the effective modes with their
source, every override with its reason, and the state the witness recorded.

### D. The `deliver` witness (R8)

`settle` joins `deliver`'s `evidence:` in both shipped workflow manifests
(`fr-goal.yaml`, `fr-goal-light.yaml`), as a derived witness next to `docs` and
`proportionality` in `run_cmd`. Its value is `<mode-pair>:<state-pair>@<head>`, or `off`
or `managed`. It reuses `fr.settle.evaluate` with no wait. A pending state exits 75 with the
unit held, as `CiPending` does. The plan finds out whether a new evidence name is a
shape change of the `run` kind, and handles it under the artifact-versioning rule if so.

### E. Skills (R5, R9, R10)

- fr-goal: in `deliver`, after the PR body is on the PR, run `fr pr settle --wait <s>`. On
  exit 4, fix under R9 and push with `fr push`. On exit 75, call it again. Then resolve.
  `fr-goal/SKILL.md` is at its line cap, so the text is a compressed clause, and the
  details live in the brief that `deliver` prints.
- fr-debugging: the same loop as its last step (R10).
- The batch and close-out dispatch briefs (`fr.triage.batch_dispatch`) say that the
  driver owns the PR and that the session never runs a settle loop.

## Verification

- pr-settle-setting: none — the CI suite proves it with the settings model and `fr settings show` (Test Plan 1).
- pr-settle-verb: none — the CI suite proves every mode × state pair and the exit codes over the fake forge (Test Plan 2, 3, 4, 8).
- pr-settle-managed: none — the CI suite proves the exemption over the fake forge (Test Plan 5).
- pr-settle-override: none — the CI suite proves the grammar, precedence and PR-body render (Test Plan 6).
- pr-settle-deliver: none — the CI suite proves the derived witness through `fr run resolve` (Test Plan 7).
- pr-settle-live: live — only a real GitHub PR shows `mergeable: UNKNOWN` timing and real check runs; the CI suite proves the logic over the fake forge.

gate: pr-settle-live=tester

## Test Plan

1. `git.settle.conflicts` and `git.settle.ci` default to `fix`, accept `off`, `report` and `fix`, refuse any other value naming the key, and appear in `fr settings show --json` and in the file `fr settings init` writes. (R1)
2. Over the fake forge, `fr pr settle` reports `clean`/`conflicting`/`unknown` and `green`/`red`/`pending`/`none` correctly. `BLOCKED` is not a conflict. Checks come from `gate_checks`, else required checks, else all checks. A `ci none` repo is `none`. (R2)
3. With an injected clock, `--wait` polls until settled or until the wait ends, then exits 75. A wait above the ceiling is refused. The verb makes no write call on the fake forge. (R3)
4. Exit codes over the mode × state table: 0, 4 under `fix` for `conflicting` or `red`, 75 for pending, 2 with no open PR. `report` never changes the exit code. (R4)
5. On `feat/batch-x`, `fix/batch-x` and `chore/closeout-…` the verb reads nothing from the forge, prints the managed line and exits 0 under every mode. The batch and close-out briefs carry the managed sentence. (R5)
6. A spec `settle.ci: report — <reason>` line and a debug-journal `settle-conflicts` decision each override the repo setting. A line with no reason, or with an unknown mode, is an error naming the line. The rendered PR body lists each override with its reason, or says the repo setting applies. (R6, R7)
7. `fr run resolve --step deliver` under `fix` refuses on a conflicting or red PR and exits 75 while pending. Under `report` it records the state. Under `off` it records `off`. On a managed branch it records `managed`. A passed `settle` evidence value is refused. (R8)
8. On a glab or tea client the state is `unsupported`, the exit code is 0 under every mode, and the line says so. (R11)
9. fr-goal's and fr-debugging's skill text names `fr pr settle`, merge-not-rebase, and the three-round limit. A tripwire pins the wording. (R9, R10)
10. Post-merge, live: in a sandbox repo of the `derio-net` org, open a draft PR through `fr pr create`, push a conflicting change to its base, and run `fr pr settle --wait 300`. It reports `conflicting` and exits 4. Merge the base, push a failing test, and it reports `red` with the check name. Fix the test, and it ends `clean`/`green`, exit 0. Record the walk with `fr acceptance set-status --walk`. (R2, R3, R4, R9; row `pr-settle-live`)

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
