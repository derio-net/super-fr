# Draft PRs that settle — wait for mergeability and CI before delivery ends

## Background

When super-fr delivers a draft PR outside the wave driver (fr-goal's `deliver`, the end
of fr-debugging, the housekeeping PR of a close-out run by hand), the session stops as soon as
the PR exists. Nothing checks whether the PR merges cleanly into its base or whether its
CI ends green. The operator finds out later, and by then the session that could fix it
has ended.

What exists today:

- `fr pr create` (`packages/fr/src/fr/commands/pr_cmd.py`) is the one place fr's skills
  open a PR. It always opens a draft and records the PR on the run cursor (`RunState.pr`).
- Under `tests: ci` (`.fr/ci.yaml`), `deliver` calls `fr.run.ci_evidence.verify_ci`.
  That call proves the gate checks are green on the code tree (exit 75, `CiPending`, while
  they run). It is test evidence: it refuses a conflicting PR (CI cannot run on one) and red
  gate checks, but only in a `tests: ci` repo, only as test evidence, and nothing checks
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
R2. `fr pr settle` reads this branch's open PR through the repo's forge adapter and reports two states. The conflict state is `clean`, `conflicting` (by `fr.triage.mergeability.conflicting`) or `unknown` (the forge has not computed it yet). The CI state is `green`, `red` with the failing check names, `pending`, `missing`, `unrunnable` or `none`. The checks read are the declared gate set (`fr.run.ci_evidence.declared_gates`: `.fr/ci.yaml`'s `gate_checks` at the base and at HEAD), else the base's required checks, else every check on the head. With no check reported yet on a repo that has CI, the state is `pending` until `NO_CI_WAIT_SECONDS` after the head was committed, then `missing`. A conflicting PR's CI state is `unrunnable`, because the forge runs no pull-request workflow for it. A repo whose services report `ci none` has CI state `none`.
R3. `fr pr settle --wait <seconds>` polls the concerns whose mode is `report` or `fix` until none of them is `unknown` or `pending`, or until the wait ends. A concern under `off` is neither read nor polled. The wait has a default and a ceiling, both below 600 seconds, so one call fits in an agent's shell tool. The verb never pushes, edits a PR, marks a PR ready or merges.
R4. Only a concern under `fix` decides the exit code. The verb exits 4 when a `fix` concern is `conflicting`, `red`, `missing` or `unrunnable`, and prints what to do. It exits 75 when a `fix` concern is still `unknown` or `pending` at the end of the wait, or when a forge read fails transiently. It exits 2 on a refusal (no open PR, unreadable settings or override). Otherwise it exits 0. A `report` concern's state, settled or not, is printed and never changes the exit code.
R5. A PR whose branch only the wave driver produces is driver-managed: `feat/batch-*`, `fix/batch-*`, a collected close-out `chore/closeout-<YYYY-MM-DD>-<n>`, a legacy per-batch archive `chore/closeout-feat-batch-*` or `chore/closeout-fix-batch-*`, a state export `chore/triage-state-*`, and a DevOps housekeeping PR `chore/ops-*`. For such a PR, `fr pr settle` reads nothing from the forge, prints that the wave driver's queue and hand-backs own the PR, and exits 0 whatever the modes. Every brief the driver gives a session about a driver-managed PR (the batch brief, the red and conflict hand-back briefs, the collected close-out hand-back brief, and the close-out brief when its PR head is the managed `chore/closeout-<batch branch>`) says the session runs no settle loop. A close-out brief that sends the session to `fr pickup --run` carries no such sentence, because that housekeeping PR is unmanaged and its pickup brief settles it. Any other branch is not driver-managed. That includes `chore/archive-<plan>` and `chore/closeout-<run-id>`, which a hand-run close-out also produces.
R6. One feature or one bug can override either key for its own PR, and the override is recorded. For a run with a spec, it is a `settle.conflicts: <mode> — <reason>` or `settle.ci: <mode> — <reason>` line in the spec's `## Verification` section. Adding or changing such a line after spec-review is allowed. For an fr-debugging session, it is a debug-journal decision with id `settle-conflicts` or `settle-ci` whose title is the mode and whose body is the reason. The reason is required. The override takes precedence over the repo setting. Any line of the section that starts with `settle.` and breaks the grammar is an error that names the line, never ignored. A section that holds only settle lines is a grammar section. A hand-run close-out has no override: the repo setting applies.
R7. The PR body fr renders at `deliver` carries a required `## PR settle` section. It names the effective mode of each key and where the mode came from, and it lists every override with its reason. Under `forge.pr_body: minimal`, the section is in the durable rendered file, as every fr section is.
R8. fr-goal's `deliver` derives a `settle` witness itself; it is never passed in. The witness is evaluated without a wait, after every other witness. Under `fix`, a failing state refuses the resolve (exit 2, naming it), and an `unknown` or `pending` state (or a transient forge failure) holds the unit with exit 75 and records nothing. Otherwise the witness records `<conflicts mode>/<ci mode>:<conflict state>/<ci state>@<head sha>`. It records `off` when both keys are `off`, and `managed` for a driver-managed PR. An `unsupported` state is recorded and refuses nothing. Under `tests: ci` the `tests` witness still needs a non-conflicting PR and green gate checks, whatever the settle modes, because CI does not run on a conflicting PR. In such a repo, a `report` or `off` override relaxes only the settle witness. A local full-suite log remains an accepted `tests` evidence.
R9. A fix keeps the PR's history and its approval as the queue reads them. A conflict is fixed by merging `origin/<base>` into the branch, never by rebase or force-push. A red check is fixed by an ordinary commit. fr-goal, fr-debugging and the hand-run close-out allow at most three fix rounds. That limit is skill text, not counted by fr. After the third round, the session stops and reports. For fr-goal, `deliver` stays refused until the PR settles or an override with its reason (R6) relaxes the key, and the override is then visible in the PR body (R7).
R10. Three flows run `fr pr settle --wait` under the same modes and fix rules. fr-debugging runs it as its last step, after `fr pr create`. The hand-run close-out brief (`fr pickup --run`) runs it after the housekeeping PR is opened. fr-goal runs it before resolving `deliver`, and once more after the `deliver` resolve's own push. The check after the resolve is skill text, not a witness, and any fix it leads to is a commit after `deliver`.
R11. A forge read that raises `UnsupportedForgeOperation` (glab and tea today, PR discovery included) gives the state `unsupported`. So does an origin that names no forge at all (a local path or a `file://` URL, as in a fixture or a mirror), which fr never reads. It takes effect before the no-open-PR refusal. It is printed and recorded, never read as `clean` or `green`, never a refusal, and exits 0.

## Design

### A. The setting (R1)

`fr.settings.model.Git` (`packages/fr/src/fr/settings/model.py`) gains `settle: Settle`, a
closed model with `conflicts` and `ci`. Each is a closed-vocabulary field over
`SETTLE_MODES = {"off", "report", "fix"}`, with the two-line `description=` every field
carries. `fr settings show` lists `git.settle.conflicts` and `git.settle.ci`.
`.fr/settings.yaml` is not an artifact kind, so no stamp moves. But `Settings` is
`extra="forbid"`, so a repo that writes `git.settle` makes an `fr` older than this change
refuse its settings. That is how every new key has worked since the settings spec, and the
change fragment says so.

### B. The engine (R2–R5, R11)

A new package, `fr/settle/`:

- `model.py`: `ConflictState`, `CiState`, `Modes` (each mode with its source: setting,
  spec line, journal decision), and `Verdict` (states, failing checks, exit code, lines to
  print, witness value).
- `evaluate.py`: `evaluate(view, checks, gate_names, modes, *, ci_none, head_committed_at,
  now) -> Verdict`. It is pure, so every mode × state cell is a table test. `unknown`
  covers GitHub's `mergeable: UNKNOWN` and an uncomputed merge state. A conflicting PR's
  CI state is `unrunnable`. With no reported check on a CI repo, the state is `pending`
  until `ci_evidence.NO_CI_WAIT_SECONDS` after the head commit, then `missing`.
- `managed.py`: `driver_managed(branch) -> bool`. It takes every prefix from its owner and
  writes no name of its own: `fr.triage.batch.BRANCH_PREFIX` and `FIX_BRANCH_PREFIX`, the
  collected close-out pattern behind `batch_drive.collected_name` (`chore/closeout-<date>-<n>`),
  `chore/closeout-` plus a batch prefix with `/` as `-` (the legacy per-batch archive
  head, `batch_drive.housekeeping_branch` with no run), `batch_drive.EXPORT_PREFIX` and
  `batch_drive.HOUSEKEEPING_PREFIX`. `chore/archive-<plan>` and `chore/closeout-<run-id>`
  stay unmanaged. The driver can tell those apart only by the files a PR touches
  (`batch_drive.attributed`), and a branch name cannot. So a legacy per-batch archive PR on
  one of those names is settled by its session like a hand-run one. The session is busy
  while it settles, and the driver hands work back only to an idle session.
- `modes.py`: `effective_modes(repo_root, *, spec, debug_journal) -> Modes`. It applies the
  setting, then the override (R6). The debug journal is found the way
  `push_cmd.approval_journal` finds it, as the branch's one debug journal.
- `poll.py`: the bounded poll over an injected clock and sleeper.

The verb is `fr pr settle [--wait <s>] [--json]` in `pr_cmd.py`. It finds the PR from the
run cursor's `pr`, else with `open_pr_for_head`. It reads checks with `pr_checks` and the
gate set with `declared_gates`, then `required_check_names`. It departs from
`ci_evidence._gate_names` on the third fallback: with neither declared nor required checks,
it reads every check on the head and does not refuse. `fr services` decides `ci none`. A
read that raises `UnsupportedForgeOperation` gives `unsupported` (R11). A `FORGE_ERRORS`
failure exits 75, as `_ci_tests_witness` maps it (gh#1395).

### C. Overrides and the PR body (R6, R7)

`fr.verification.spec_section`: `_is_grammar` recognises a line that starts with
`settle.`. `Section` gains `settle: dict[str, SettleOverride]` (mode and reason). A
malformed `settle.` line, an unknown key or mode, or a missing reason is an error naming the
line. The debug-journal form is a `decision` entry with id `settle-conflicts` or
`settle-ci`.

`fr.record.pr_body` renders `## PR settle` from the effective modes (known before the
resolve): each key's mode, its source, and each override's reason. The section joins
`REQUIRED_SECTIONS`, so a live body without it is refused like any other required section.
The section is required, unlike `## Review lenses`: a run whose live body an older fr rendered gets one more refuse-and-edit round at `deliver`, whose refusal prints the edit command. That cost is accepted so that an override cannot reach a PR unseen. The settle state is not part of the body. It is the witness's value (`fr run status`),
because the body is rendered before the witness exists.

**No shape change.** A new evidence key is a key in `StepRecord.evidence: dict[str, str]`
(`fr/run/model.py`). The `docs` witness added one in 2026-11 without a stamp move. A
`decision` entry with a fixed id uses an entry kind journal v4 already holds. A section that holds only `settle.` lines counts as no verification section for strategy, walk and gate resolution (`fr.verification.effective`), so adding an override changes no row strategy and owes no walk; only the overrides are read from it. A `settle.`
line is prose to every released spec reader, which ignores lines outside the grammar. None
of the three is a shape change under `.claude/rules/artifact-versioning.md`, so no stamp,
migration or validator ships.

### D. The `deliver` witness (R8)

`settle` joins `deliver`'s `evidence:` in both shipped workflow manifests (`fr-goal.yaml`,
`fr-goal-light.yaml`) and the registries every derived witness is listed in:
`fr.workflow.artifacts.DERIVED_EVIDENCE`, and `run_cmd`'s `_VERIFIABLE_EVIDENCE` and
`_DERIVED_FROM`. It is not evaluated through `derive()`, because that turns every exit into
a refusal (exit 2). It is evaluated after the derived witnesses and after every `deliver` gate (placement, acceptance, leftovers, the PR-body check, the exit guard), and before the label sync, which writes the forge. So a pending CI state holds the unit only once the body is rendered and every hard refusal has printed. It is evaluated in the way `_ci_tests_witness` is: it calls `fr.settle.evaluate` with no wait, refuses with exit 2 on a
failing `fix` state, and holds with exit 75, recording nothing, on a pending one. A refusal
of any other witness is reported first.

### E. Skills and briefs (R5, R9, R10)

- fr-goal: before resolving `deliver`, after the PR body is on the PR, run
  `fr pr settle --wait <s>`. On exit 4, fix under R9 and push with `fr push`. On exit 75,
  call it again. After the `deliver` resolve's push, call it once more and report the
  result. `fr-goal/SKILL.md` is at its line cap, so the text is a compressed clause, and the
  detail lives in the brief that `deliver` prints.
- fr-debugging: the same loop as its last step.
- The hand-run close-out: `fr.run.closeout`'s brief adds the settle step after the
  housekeeping PR is opened.
- Driver briefs: `fr.triage.batch_dispatch` (`render_brief`, `red_brief`, `conflict_brief`,
  `archive_conflict_brief`), `fr.triage.batch_closeout.handback_brief`, and `fr.triage.batch_drive.closeout_brief` when it has no run, each carry one sentence: the wave driver owns
  this PR's mergeability and CI, so run no settle loop.

## Verification

- pr-settle-setting: none — the CI suite proves it with the settings model and `fr settings show` (Test Plan 1).
- pr-settle-verb: none — the CI suite proves every mode × state cell and the exit codes over the fake forge (Test Plan 2, 3, 4, 8).
- pr-settle-managed: none — the CI suite proves the exemption and the brief sentences over the fake forge (Test Plan 5).
- pr-settle-override: none — the CI suite proves the grammar, precedence and the required PR-body section (Test Plan 6).
- pr-settle-deliver: none — the CI suite proves the witness through `fr run resolve`, and its interaction with `tests: ci` (Test Plan 7).
- pr-settle-skills: none — the CI suite pins the settle step and the fix rules in fr-goal, fr-debugging and the close-out brief (Test Plan 9).
- pr-settle-live: live — only a real GitHub PR shows `mergeable: UNKNOWN` timing and real check runs; the CI suite proves the logic over the fake forge.

gate: pr-settle-live=tester

## Test Plan

1. `git.settle.conflicts` and `git.settle.ci` default to `fix`, accept `off`, `report` and `fix`, refuse any other value naming the key, and appear in `fr settings show --json` and in the file `fr settings init` writes. (R1)
2. Over the fake forge: `clean`, `conflicting` and `unknown`. `BLOCKED` is not a conflict. `green`, `red` with names, `pending`, `none` under `ci none`, `unrunnable` on a conflicting PR, and no reported check giving `pending` before `NO_CI_WAIT_SECONDS` and `missing` after. Checks come from `declared_gates`, else required checks, else every check, with no refusal on the third fallback. (R2)
3. With an injected clock, `--wait` polls only `report` and `fix` concerns until they settle or the wait ends. An `off` concern is never read. A wait above the ceiling is refused. The verb makes no write call on the fake forge. (R3)
4. Exit-code table over modes × states: 4 for each failing `fix` state; 75 for a pending `fix` state at the end of the wait and for a transient forge failure; 2 with no open PR; 0 otherwise. A `report` concern, pending or failing, never changes the code. (R4)
5. Each managed name gets the managed line and exit 0 with no forge read under every mode: `feat/batch-x`, `fix/batch-x`, `chore/closeout-2026-11-23-1`, `chore/closeout-feat-batch-x`, `chore/triage-state-s-wave-2` and `chore/ops-p`. `chore/archive-p`, `chore/closeout-<run-id>` and `feat/other` are settled normally. Every driver brief named in §E carries the sentence. (R5)
6. A spec `settle.ci: report — <reason>` line and a debug-journal `settle-conflicts` decision each override the repo setting. A section with only settle lines is read. A `settle.` line with no reason, an unknown key or an unknown mode is an error naming the line. The rendered body's `## PR settle` names modes, sources and reasons, and a live body without the section is refused. (R6, R7)
7. `fr run resolve --step deliver`: under `fix`, a conflicting or red PR is refused (2), and a pending one exits 75 with nothing recorded. `report` records the state. `off` records `off`. A managed branch records `managed`. `unsupported` is recorded and refuses nothing. A passed `settle` value is refused. Under `tests: ci` with `settle.conflicts: off`, a conflicting PR is still refused by the `tests` witness. (R8)
8. On a glab or tea client, PR discovery included, the state is `unsupported`, the exit code is 0 under every mode, and the line says so. (R11)
9. fr-goal's and fr-debugging's skill text and the close-out brief name `fr pr settle`, merge-not-rebase and the three-round limit. fr-goal names the second settle after `deliver`. A tripwire pins the wording. (R9, R10)
10. Post-merge, live: in a sandbox repo of the `derio-net` org, open a draft PR through `fr pr create`, push a conflicting change to its base, and run `fr pr settle --wait 300`. It reports `conflicting` (CI `unrunnable`) and exits 4. Merge the base, push a failing test, and it reports `red` with the check name. Fix the test, and it ends `clean`/`green`, exit 0. Record the walk with `fr acceptance set-status --walk`. (R2, R3, R4, R9; row `pr-settle-live`)

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-11-23-pr-readiness-wait | `derio-net/super-fr` | `2026-11-23-pr-readiness-wait` | — |
