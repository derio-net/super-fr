# Run pipeline failures at resolve and deliver; double phase claims

**Batch:** `run-pipeline` — super-fr#1090, super-fr#1091, super-fr#1110, delivered as one PR.
**Branch:** `feat/batch-run-pipeline`

## Background

Three defects make an fr run fail, or record the wrong thing, late in its life.

1. **#1090 — ignored acceptance reports.** Some repos gitignore the generated
   acceptance reports (`docs/acceptance/report*.html`, `report*.md`) and let CI
   build them. fr assumes the report set (`REPORT_SET`,
   `packages/fr/src/fr/acceptance/report.py:422`) is committed:
   - a step record that adds acceptance rows renders all three reports into the
     write overlay (`packages/fr/src/fr/record/apply.py:803`), they enter the
     commit set, and `commit_paths`'s `git add` refuses ignored paths
     (`packages/fr/src/fr/artifacts/commit.py:606`) — the whole commit fails,
     record applied, nothing committed;
   - `fr acceptance check`'s report-sync gate
     (`packages/fr/src/fr/acceptance/check.py:276-291`) reports `report drift`
     for every report, which the repo cannot fix without un-ignoring them;
   - the same assumption sits in `fr acceptance report --check`
     (`packages/fr/src/fr/commands/acceptance_cmd.py:170-194`), the archive
     retarget (`packages/fr/src/fr/commands/archive_cmd.py:470-490`, a
     `git add ... check=True`), `fr acceptance init`'s scaffold
     (`packages/fr/src/fr/acceptance/scaffold.py:535-557`) and the matrix-anchor
     repair (`packages/fr/src/fr/artifacts/matrix_anchors.py:90-133`).
     `fr acceptance add` / `set-status` reach the record engine
     (`acceptance_cmd.py:433`), so they share the first failure.

2. **#1091 — an unrunnable `candidate` walk owed at deliver.** A spec whose
   `## Verification` has per-row lines but no `strategy:` line falls back to
   the shape's default (`candidate` for `fr-goal`) in `walk_owed`
   (`packages/fr/src/fr/verification/walk.py:119-122`) and in
   `effective_strategy` (`packages/fr/src/fr/verification/effective.py:16-39`).
   `candidate` installs through `.fr/candidate-install`
   (`packages/fr/src/fr/verifications/candidate.yaml:10`); a repo without that
   executable cannot walk, and nothing says so before `deliver` refuses
   `walk: none`. `fr plan self-review`'s `_verification_issues`
   (`packages/fr/src/fr/plan_ops.py:1647`) checks per-row reasons and scenarios
   only — never whether an owed strategy can run. Separately, `strategy: none —
   <reason>` fails with `malformed \`strategy:\` line` and no hint of the
   accepted form (`packages/fr/src/fr/verification/spec_section.py:98-101`).

3. **#1110 — a re-claim silently rewrites an open attempt.** The two claim
   commits the issue cites (`fe737e5c`, `be1f78b7`, run
   `2026-10-08-feat-batch-sweep-status-lanes`) name the SAME agent id; the
   second only rewrote the open attempt's `model`. `_claimed_identity`
   (`packages/fr/src/fr/commands/run_cmd.py:3985`) treats a same-agent re-claim
   as idempotent but overwrites `harness`/`model` with whatever the re-claim
   passes, and `_claim_identity` (`run_cmd.py:6814`) also replaces
   `agent_type`. A replayed or resumed orchestrator therefore writes a second
   claim commit and erases what the first one recorded. A different agent is
   already refused, and an exact replay already commits nothing (`commit_paths`
   reports `unchanged`), so the defect is the overwrite.

## Requirements

R1. A report in `REPORT_SET` that the repo gitignores (matched by
`git check-ignore`, and not tracked) is CI-built: no fr commit path puts it in a
commit set, and a commit is never refused because of one.

R2. `fr acceptance check` and `fr acceptance report --check` skip the
report-sync comparison for CI-built reports; drift in a tracked report is still
an error. `report --check --out <path>` names one file explicitly and is still
compared, CI-built or not.

R3. `fr acceptance report --deterministic` still writes every report in
`REPORT_SET`, ignored or not, so CI can build the set with the same command.

R4. The workflow shape's default verification strategy does not apply when the
repo cannot run that strategy's install program (an install program that is a
repo-relative path which is missing or not executable). A run whose rows all
carry per-row lines then owes no walk from the default.

R5. A verification strategy the spec names explicitly (a `strategy:` line, a
per-row line, or a row's `verify:`) whose install program the repo cannot run
is an error in `fr plan self-review`, and a warning printed by the
`brainstorm` resolve that emits the spec — naming the strategy, the missing
program and the two fixes (`strategy: none` / per-row `none`, or add the
executable).

R6. A malformed `strategy:` line's error shows the accepted form:
`strategy: <name>` alone, with reasons on the per-row lines.

R7. Once an open attempt is claimed (it carries an `agent`), a later claim by
that same agent — through `fr run claim`, `--open-unit`, or `fr run resolve`'s
`--agent`/`--harness`/`--model` — never overwrites its recorded `harness`,
`model` or `agent_type`: an empty field is filled, an identical value (or, for
`model`, one in the same `fr.models.model_family`) is a no-op, and a different
value is kept as recorded with a warning on stderr, exit 0. A re-claim that
changes nothing writes nothing and makes no commit. A different agent stays
refused (exit 2). The FIRST claim (no `agent` yet) still sets these fields as
today, replacing what `advance` pre-filled.

R8. The claim path is covered by tests for an interruption after the claim and
before the resolve, followed by a re-claim: identical re-claim (no commit),
same-family model, different-family model (warning, value kept), the
OpenCode sequence (plugin `--open-unit` claim, then the orchestrator's claim
with the tier-bound `--model`), `resolve --model` without `--agent` on a
claimed attempt, a first claim overriding `advance`'s pre-filled harness/model,
a different agent (refused), and `advance` refusing to re-brief the held unit.

## Design

### A. CI-built reports (R1–R3)

One helper in `fr/acceptance/report.py`:

```python
def ci_built_reports(root: Path) -> frozenset[str]:
    """The REPORT_SET paths the repo gitignores and does not track."""
```

It runs `git check-ignore --stdin` once over `REPORT_SET`'s paths (a tracked
file is never reported ignored by `check-ignore`, so tracked wins). Outside a
git repo, or when git fails, it returns the empty set — the old behaviour.
A sibling `tracked_reports(root)` returns `REPORT_SET` minus that set; every
caller below uses one of the two, and none calls `git check-ignore` itself.

Callers:

- **record apply** (`apply.py:803`): renders and writes only tracked reports
  into the overlay, so the commit set never holds an ignored one. A CI-built
  report is not written by the record engine at all (CI renders it).
- **`fr acceptance check`** (`check.py:276`): the existence trigger and the
  comparison both iterate tracked reports only. When every report is CI-built
  the gate is skipped.
- **`fr acceptance report --check`**: compares tracked reports only and names
  the CI-built ones it skipped in its success line; an explicit `--out` is
  compared regardless (R2).
- **archive retarget** (`archive_cmd.py:470`): writes and `git add`s matrix +
  tracked reports only.
- **`fr acceptance init`** (`scaffold.py:548`): creates tracked reports only;
  a CI-built one is reported as skipped.
- **matrix-anchor repair** (`matrix_anchors.py:90`): `_report_paths` (its
  commit `companions`) and `_fn` cover tracked reports only.
- **`report --deterministic`** is unchanged (R3).

### B. Verification strategies the repo cannot run (R4–R6)

**One install rule.** `walk.py`'s `_contract` (`walk.py:354-370`) already
decides whether an install program can run: an `install[0]` that is a bare
command or an absolute path is accepted; a repo-relative one must be a file
and executable. That check moves into one function in
`fr/verification/effective.py`:

```python
def install_problem(manifest: StrategyManifest, repo_root: Path) -> str | None:
    """Why the repo cannot run the manifest's install program, or None."""
```

A manifest with no `install` returns `None` — nothing to install is not a
reason a strategy cannot be owed (e.g. `live`). `_contract` keeps its own
walk-specific refusal ("has no install — there is nothing to walk") and calls
`install_problem` for the program check, so self-review, the brainstorm
resolve and `fr verification walk` share one rule and one message.

**R4 — one filter for the shape default.**

```python
def effective_shape_default(name: str | None, repo_root: Path | None) -> str | None:
```

returns `name`, unless it resolves and `install_problem` reports a problem —
then `None`. A default that does not resolve (`StrategyError`) is returned
UNFILTERED, so the existing gates keep refusing it by name (the deliver gate,
`run_cmd.py:2574`) and no new exception reaches callers that catch only
`WorkflowError`/`OSError`/`SectionError` (`rows.py:84-87`,
`record/pr_body.py:473-477, 537-541`). All three places that bind a shape
default call it: `fr.verification.rows.shape_default` (`rows.py:78`),
`_verification_issues` (`plan_ops.py:1679`) and `fr/run/visual.py:344`.
`walk_owed`, `effective_strategy` and the PR-body renderers read
`SpecVerification.shape_default` and need no change.

**R5 — a plan-free check.**

```python
def unrunnable_strategies(
    repo_root: Path, section: Section, rows: Sequence[Row]
) -> list[str]:
```

in `fr/verification/rows.py` returns one message per distinct strategy named
explicitly — the section's `strategy:`, a per-row line, or a `verify:` of a
row in `rows` — that resolves and has an `install_problem`. Each message names
the strategy, the problem and both fixes (`strategy: none` or a per-row `none`
line with a reason; or add the executable). It never consults the shape
default (R4 handles that) and needs no plan. Callers:

- `_verification_issues` passes the rows citing the spec and turns each
  message into a self-review **error**.
- the `brainstorm` resolve, after applying a record whose `emitted` names a
  spec, reads that spec's section and the matrix rows citing it (the record's
  `acceptance:` rows are in the matrix by then) and prints each message as a
  `warning:` line. A missing or malformed section, or an unreadable matrix,
  prints nothing there — self-review reports those.

**R6.** `parse_section`'s error for a line starting `strategy:` that does not
match becomes: `line N: malformed \`strategy:\` line: '<raw>' — it holds only
the name (\`strategy: <name>\`); put reasons on the per-row lines
(\`- <row-id>: <strategy|none> — <reason>\`)`.

### C. First claim wins (R7–R8)

One merge function in `run_cmd.py` decides what a claim does to an open
attempt; `_claimed_identity` (`run_cmd.py:3985`), `_claim_identity`
(`run_cmd.py:6814`, for `agent_type`) and `_close_on_resolve`'s no-agent branch
(`run_cmd.py:4049-4057`) all go through it:

- attempt not yet claimed (`agent is None`): fields are set from the claim,
  exactly as today — this is how a claim refines what `advance` pre-filled
  (`harness` from `detect_harness`, `model` for orchestrator-run work,
  `agent_type` as the manifest id).
- attempt claimed: for `harness`, `model` and `agent_type`, an empty field
  takes the claim's value; a value equal to the recorded one, or (for `model`)
  in the same `model_family`, is kept silently; any other value is kept as
  recorded, with `warning: <key>: <agent> is recorded with <field>=<old>;
  keeping it (this claim said <new>). The first claim's identity stands;
  resolve records the model the transcript observed. If the executor was
  really replaced, close it with \`fr run claim ... --abandoned\` and
  re-dispatch.`

When the merged attempt equals the open one, `_claim_identity` returns without
`_save_run_state` and prints `<key>: already claimed by <agent> (no change)`,
so no commit is made. The transcript-observed model (`_observed_model`,
`run_cmd.py:4080`) still replaces `model` at resolve — observation, not a
claim, and unchanged by this spec.

No run-cursor schema change: the attempt's fields and vocabulary are untouched.

## Verification

strategy: none

- acceptance-ci-built-reports: none — internal commit/check paths; CI runs the targeted unit and integration tests.
- verification-unrunnable-strategy: none — parser and self-review logic; CI runs the targeted unit tests.
- run-claim-first-wins: none — cursor write rules; CI runs the targeted unit tests.

## Tests

One test module per member, all targeted, all in CI:

- **R1–R3** (`acceptance-ci-built-reports`): an integration test on a git repo
  whose `.gitignore` ignores the report set — record apply with `acceptance:`
  rows commits (cursor, matrix, journal) with no report path; `fr acceptance
  add` / `set-status` commit; archive retarget stages without the reports; the
  matrix-anchor repair's companions exclude them; `fr acceptance init` skips
  them. Unit tests: `ci_built_reports` (ignored, tracked-but-ignored, no repo);
  `fr acceptance check` and `report --check` pass with ignored reports absent
  or stale and still fail on a stale TRACKED report; `report --check --out
  <ignored>` still compares; `report --deterministic` writes all three.
- **R4–R6** (`verification-unrunnable-strategy`): `install_problem` cases
  (missing, not executable, bare command, absolute, no install);
  `effective_shape_default` filters an unrunnable `candidate` and returns an
  unresolvable name unchanged; `walk_owed` owes nothing for an all-`none`
  per-row section in a repo without `.fr/candidate-install`, and still owes
  `candidate` in one with it; `visual.py`'s binding agrees; self-review errors
  on an explicit unrunnable strategy (section, per-row, `verify:`); the
  brainstorm resolve prints the warning and still resolves; `_contract`'s
  message is unchanged; the R6 message.
- **R7–R8** (`run-claim-first-wins`): the R8 sequences, each asserting the
  cursor's attempt fields and the commit count.

## Decisions

The five design choices (gitignore detection, writer-side filtering, default
filter + early flag, first-claim-wins, `strategy: none`) were taken as the
spec author's recommended options by the derio-net triage session under the
operator's overnight brief — not ruled by the operator. They are recorded in
the spec journal and open to revision at PR review.

## Out of scope

- A config knob declaring reports CI-built (detection by `.gitignore` only).
- Filtering ignored paths generically inside `commit_paths`.
- An audited attempt-replacement transition in the run cursor (a schema change).
