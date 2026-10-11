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
an error.

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

R7. A claim on an open attempt by the agent that already holds it never
overwrites a recorded `harness`, `model` or `agent_type`: an empty field is
filled, an identical value is a no-op, and a different value is kept as
recorded with a warning on stderr, exit 0. A re-claim that changes nothing
writes nothing and makes no commit. A different agent stays refused (exit 2).

R8. The claim path is covered by tests for an interruption after the claim and
before the resolve, followed by a re-claim: identical re-claim, re-claim with a
different model, re-claim by a different agent, and `advance` refusing to
re-brief the held unit.

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
  the CI-built ones it skipped in its success line.
- **archive retarget** (`archive_cmd.py:470`): writes and `git add`s matrix +
  tracked reports only.
- **`fr acceptance init`** (`scaffold.py:548`): creates tracked reports only;
  a CI-built one is reported as skipped.
- **matrix-anchor repair** (`matrix_anchors.py:90`): `_report_paths` (its
  commit `companions`) and `_fn` cover tracked reports only.
- **`report --deterministic`** is unchanged (R3).

### B. Verification strategies the repo cannot run (R4–R6)

One predicate in `fr/verification/effective.py`:

```python
def runnable(strategy: str | None, repo_root: Path | None) -> bool:
    """False iff the strategy's manifest has an `install` whose program is a
    repo-relative path that is missing or not executable under repo_root."""
```

`None`, `none`, a strategy with no `install`, and a program that is not a
repo-relative path (an absolute path or a bare command) are runnable — fr only
judges what it can see in the repo. A strategy that does not resolve raises
`StrategyError`, as `is_post_merge` does.

- **R4:** the shape default is filtered once, where it is bound:
  `fr.verification.rows.shape_default` (`rows.py:78`) and
  `_verification_issues`' `workflow_for_plan(plan).verification`
  (`plan_ops.py:1679`) pass the default through `runnable` and use `None` when
  it fails. `walk_owed` and `effective_strategy` then need no change: both read
  `SpecVerification.shape_default`.
- **R5:** `_verification_issues` adds an error per explicitly named strategy
  (section `strategy:`, a row's per-row line, a row's `verify:`) that is not
  `runnable`, once per strategy. The `brainstorm` resolve, after applying a
  record that emits a spec, runs the same check and prints each issue as a
  `warning:` line — a warning, not a refusal, because self-review (a `cli`
  gate) refuses it before any implementation starts.
- **R6:** `parse_section`'s error for a line starting `strategy:` that does not
  match becomes: `line N: malformed \`strategy:\` line: '<raw>' — it holds only
  the name (\`strategy: <name>\`); put reasons on the per-row lines
  (\`- <row-id>: <strategy|none> — <reason>\`)`.

### C. First claim wins (R7–R8)

`_claimed_identity` changes its merge rule: for each of `harness` and `model`,
a recorded value is kept; only an empty one takes the re-claim's value. A
differing value prints `warning: <key>: already claimed by <agent> with
<field>=<old>; keeping it (re-claim said <new>). A model change mid-attempt is
\`fr run claim ... --abandoned\` then a fresh dispatch.` on stderr.
`_claim_identity` applies the same rule to `agent_type`: the manifest id
recorded by `advance` is refined to a tier variant on the FIRST claim (the
attempt has no `agent` yet); once claimed, a different `agent_type` is kept as
recorded, with the same warning. When the merged attempt equals the open one,
`_claim_identity` returns without `_save_run_state` and prints
`<key>: already claimed by <agent> (no change)`, so no commit is made.
`resolve`'s late-identity path shares `_claimed_identity` and inherits the rule;
the transcript-observed model (`_observed_model`) is unchanged.

No run-cursor schema change: the attempt's fields and vocabulary are untouched.

## Verification

strategy: none

- acceptance-ci-built-reports: none — internal commit/check paths; CI runs the targeted unit and integration tests.
- verification-unrunnable-strategy: none — parser and self-review logic; CI runs the targeted unit tests.
- run-claim-first-wins: none — cursor write rules; CI runs the targeted unit tests.

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
