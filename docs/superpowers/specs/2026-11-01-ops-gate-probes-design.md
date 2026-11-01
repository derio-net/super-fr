# A devops gate that runs things, not prose — design

**Issue:** derio-net/super-fr#1273. **Builds on:** `docs/superpowers/implemented/specs/2026-10-22-fr-ops-design.md`
(runnable ops, `fr ops gate`'s eight stages, #1220) and #1260 (Test Plan cost lines,
"walked on first real use").

## Background

`fr ops gate` runs a delivered run's DevOps stage. For **ops** it runs things: stages 1
and 4 run each op's `check:`, and then its `apply:` once the operator confirms. A
devops-gated run whose plan declares **no** ops gets none of that. Every Test Plan step
turns into a stage-5 prose prompt (`fr/ops/gate.py` `stage_5`) that only asks for `ran`,
`na` or `owed`.

This was seen on a private infrastructure repo (identity redacted per
`.claude/rules/third-party-privacy.md`; shape only). The spec declared `gate: devops` and
a 7-step Test Plan, and the plan declared 0 ops. Four of the steps were fully scriptable
(an IaC converge, a configuration playbook, a verify playbook, a pinned-ref check). Each
had an obvious probe that would have caught, as OPEN with its own error, problems the
operator had to find by hand: an IaC backend login missing from the ops profile, SSH with
no key for some groups, a base image archived upstream. Nothing in the pipeline flagged
"devops gate, zero ops, Test Plan full of commands". fr-plan, spec review and the gate
all accepted it.

A second, smaller bug: stage 5's `_ANSWER = ^\s*(ran|na|n/a|owed)\s+(\S.*)$` rejects the
natural `ran: label printed`, and it fails the stage with "has no outcome; walk it and
re-run". That reads as if the step was never walked.

## Requirements

R1. One function, `fr.ops.gap.ops_gap`, decides whether a run has an **ops gap**. A run has one when all of the following hold:
    - its effective gates include `devops`;
    - its plan declares no op in either plan carrier (`ops.yaml`, `# manual-operation` step blocks; the runbook is excluded);
    - its `ops.yaml` carries no `none:` acknowledgement;
    - at least one Test Plan step **whose effective gate is devops** (`fr.ops.testplan.steps_gated`) contains a command.
    It returns those command steps, each with the commands it found. A `[tester]`-tagged step never counts.
R2. A step "contains a command" when it carries no op pointer (R6) and yields at least one command:
    - **Fenced lines:** every non-blank line inside a code fence that belongs to the step is one command, with the fence's info string dropped.
    - **Inline spans:** a backtick span counts when it has at least two words and its first word is one of these: on a shipped list of operations tools (`ansible`, `ansible-playbook`, `pulumi`, `terraform`, `tofu`, `kubectl`, `helm`, `talosctl`, `docker`, `podman`, `ssh`, `scp`, `rsync`, `systemctl`, `make`, `curl`); a relative or absolute path (`./x`, `scripts/x`, `/usr/x`); or followed by a flag (`-x`/`--x`) or a path argument containing `/`.
    To do this, `Step` keeps the item's raw lines. The heuristic is documented as one: its false positives are prose spans that look like commands (for example `git diff --stat`, quoted as an example), and its false negatives are commands outside the shipped list written with no flag or path. The `none:` acknowledgement (R4) is the escape for both.
R3. `fr plan self-review` reports an ops gap as a **`warn`** issue naming each command step and its commands, plus the two fixes (`fr ops stub`, or `none:` in `ops.yaml`). Resolving the run's spec-reviewing step (`spec-review` or `spec-plan-review`) done prints the same warning to stderr, computed against the run's plan when one exists and otherwise worded as "these steps will need ops". Neither one refuses, and neither changes an exit code. A Verification section or matrix that cannot be read makes both skip the warning silently.
R4. `ops.yaml` gains an optional `none: <reason>` key, a non-empty string meaning "no ops on purpose". Two cases are refused by name: a file whose `none:` sits beside a non-empty `ops:`, and a plan whose phase files carry `# manual-operation` blocks while its `ops.yaml` says `none:`. The `ops` artifact kind moves from version 1 to 2, with a registered stamp-only migration and an updated structure validator (`.claude/rules/artifact-versioning.md`). The validator refuses `none:` in a file stamped below 2. A `none:` file never counts as ops for the R13 gate promotion: `plan_has_ops` stays false.
R5. `fr ops gate` **stage 1 refuses** (exit 2, nothing brought up, nothing recorded) when the PR head has an ops gap. It decides this on a scratch tree materialised from the PR head before any workspace exists. The refusal names each command step with its commands and both fixes, which go on the PR branch.
R6. A Test Plan step may **point at an op** with `(op: <id>)` leading its text, after the optional gate tag, e.g. `- [devops] (op: guest-verify) Run the verify playbook`. `fr.spec.Step` gains an `op` field, and the pointer is removed from `text`. An inline `check:` on a step is not supported.
R7. `fr plan self-review` reports an **error** when a step's pointer names an op the plan does not declare. It also reports an error for an op whose `check:` is still the stub sentinel `TODO` (R11).
R8. Stage 5 runs a pointed step's probe instead of asking. First it calls `gate.trust(tree)`, as `apply_phase` does. Then it runs `fr ops status <id> --plan <plan> --json` in the ops workspace, takes exit 0, 1 and 3 as reports and exit 2 as a refusal that fails the stage with its output, and shows the row's state and output or reason. Then:
    - **DONE (how=checked)** records `fr closeout outcome --ran` with the evidence `<op id>: check passed — <evidence lines>` (R9), with no question.
    - **OPEN, UNVERIFIABLE, CANNOT-VERIFY or ESCALATE** shows the reason, then asks `retry`, `na <reason>` or `owed <why>`. `retry` re-runs the probe, and `ran` is refused.
    - **N/A, or a DONE that ran no check** (attested, proof or legacy) shows the state and asks the usual `ran | na | owed` question. No probe ran, so fr records no `ran` on its own.
    Steps with no pointer keep today's prompt.
R9. Probe output reaches the row. The runner returns the probe's **full** stdout, and the engine derives the last non-blank line itself wherever it used the line before, so its reasons are unchanged. `fr ops status --json` rows gain two fields:
    - `output`: for a DONE (checked) row, the last ≤ 40 lines with secret values masked, each line ≤ 200 chars, shown on screen;
    - `evidence`: the last ≤ 3 non-blank of those lines, ≤ 300 chars in all, masked the same way.
    Both are `null` otherwise. Only `evidence` is ever recorded. Committed evidence stays a few lines, because masking hides secret values, not hostnames, and `docs/ops.md` says so: a probe should end with a one-line summary.
R10. Stage 5's answer grammar takes the keyword with an optional `:` or `-` separator (`ran: x`, `na - y`, `owed x`). A bare keyword with no argument is accepted only for `retry`. A word that merely starts with a keyword is not one (`rancid`, `na-ive` with no separator after `na`). A non-matching answer, an empty one included, is **re-prompted**, echoing what was received and the expected grammar. After three consecutive non-matches the stage fails with that same echo.
R11. A new `fr ops stub [--plan <dir>] [--yes]` reads the plan's spec. For each devops command step (R1) without a pointer, it proposes an `ops.yaml` op:
    - id `step-<n>`;
    - `summary`: the step text, clipped;
    - `phase: post-merge`;
    - `apply:` the step's commands joined with ` && `;
    - `mutating: true`, so stage 4 asks for the mutating confirmation;
    - `check: TODO`, a reserved sentinel that `fr ops status` reports as UNVERIFIABLE "write a real probe" and that `fr plan self-review` reports as an error (R7).
    It also proposes the step's `(op: step-<n>)` pointer. A step reaches `ran` once the planner replaces `TODO` with a real probe and that probe passes. Without `--yes` the command prints the stubs and the spec edits and writes nothing. With `--yes` it writes both. It refuses, writing nothing, an id that is already declared, a `none:` acknowledgement, or a plan with no spec.
R12. The `fr-plan` skill tells the planner, for a devops-gated spec, to split the Test Plan: runnable steps become ops (`fr ops stub`, then a real `check:`), and physical or judgement steps stay prose. The `fr-devops-gate` skill and `docs/ops.md` describe R4–R11. Both skills stay within the 120-line cap, and their OpenCode and Hermes mirrors are regenerated.

## Design

### A. The gap (R1–R3)

`packages/fr/src/fr/ops/gap.py` (new, pure except `ops_gap`'s reads):

```
@dataclass(frozen=True)
class CommandStep: n: int; text: str; commands: tuple[str, ...]
def step_commands(step: Step) -> tuple[str, ...]                    # R2, from step.raw
def command_steps(steps: Sequence[Step], exit_gates: Set[str]) -> list[CommandStep]
def ops_gap(root: Path, spec_rel: str, plan_dir: Path | None, exit_gates: Set[str]) -> list[CommandStep]
def gap_message(steps: list[CommandStep], *, has_plan: bool) -> str
```

`fr.spec.Step` gains `raw: tuple[str, ...] = ()` (the item's lines as written, fences
included) and `op: str | None = None`. Both default, so every existing
`Step(n, text[, gate])` stays valid. `exit_gates` comes from
`fr.verification.exit.exit_for_spec(root, spec_rel)` for self-review and stage 1 (no run is
needed). With 0 ops there is no R13 promotion, so the result is the same. The spec-review
hook uses `run_exit`. `fr/gates.py` is not edited.

Callers:
- `plan_ops.self_review` adds a `warn` ReviewIssue for a gap (R3), plus an `error` per
  dangling pointer and per `check: TODO` (R7). The spec comes from `Plan.spec_path`.
- `run_cmd`: at the existing spec-review `done` hook (`_spec_review_ids`), print
  `gap_message` to stderr, using `run_plan_dir` when the run has a plan. `SectionError`,
  `AcceptanceError` and `OpsLoadError` are swallowed there and in self-review.
- `gate.stage_1` (R5): after the archive/profile checks and before `isolation up`. A new
  `GateHost.materialise(ref, paths) -> Path` writes `git archive <ref> -- <paths>` into a
  fresh temporary directory, using the paths `docs/superpowers/specs`,
  `docs/superpowers/plans/<plan>`, `docs/acceptance/matrix.yaml` and `.fr`. `ops_gap` runs
  over that directory, the directory is removed, and a non-empty gap raises
  `StageFailed(code=2)`. The fake host in the scenarios and unit tests implements
  `materialise` the same way, over its own repo.

### B. The acknowledgement (R4)

The changes:
- `OpsFile` gains `none: StrictStr | None = Field(default=None, min_length=1)`, plus a model
  validator that refuses `none` together with a non-empty `ops`.
- `load._ops_yaml` accepts the `none` key. A new `load.ops_none(plan_dir) -> str | None`
  reads it and raises `OpsLoadError` when step blocks exist too.
- `structure.validate_ops` refuses `none:` under a stamp below 2.
- The registry moves `ops` to `current_version=2`. The migration is a stamp-only
  `SchemaMigration` 1→2 (every v1 file is a valid v2 file), registered through a module
  imported by `fr/artifacts/__init__.py`.
- `fr migrate artifacts --yes` runs in the same PR.

### C. The pointer and the probe (R6–R9)

The pointer: `fr.spec`'s `_POINTER_RE = ^\(op:\s*(?P<id>[A-Za-z0-9][\w.-]*)\)\s+(?P<rest>\S.*)$`
is applied after the tag. Readers of `Step.text` only display or quote it (archive,
closeout, holds, gate), so dropping the pointer from `text` is safe. The spec file's shape
on disk is unchanged, so no spec stamp bump is needed.

Probe output: `ShellRunner.__call__` returns `(rc, stdout)` in full. `engine._check` and
`_evaluate` take `last_line(out)` wherever they used the line. Fakes that return one line
behave as before. On DONE (checked), `_check` keeps the last successful identity run's
output, and the two fields are built by a new `mask.clip_output` and `mask.evidence_lines`.
Both are covered by `as_row`. `check: TODO` (`model.TODO_CHECK`) is caught before the
runner runs: the row is UNVERIFIABLE with "a stub: write a real probe".

Stage 5: `gate.stage_5` (rewritten loop). For each devops step not already closed at head:
- `step.op` set → `_probe_step(gate, tree, step)`, as R8 describes. The first pointed step
  calls `gate.trust(tree)` once.
- no pointer → today's question, with the R10 grammar.

The grammar: `_ask_outcome(gate, text, allowed)` holds the re-prompt loop (R10). A keyword
(`ran|na|n/a|owed|retry`, case-insensitive) is followed by one of: end of input, whitespace,
a `:` (spaces optional), or a `-` followed by whitespace. The rest is the argument. Then the
answer is checked against the allowed set: `retry` takes no argument, and the others need
one. The tests pin `ran: x`, `ran:x`, `na - y`, `na- y`, `owed x`, `retry` (accepted), and
`rancid`, `na-ive`, `ran` with no argument and an empty answer (each re-prompted).

### D. Stubs (R11)

`fr ops stub` in `commands/ops_cmd.py` calls a pure
`fr.ops.stub.propose(spec_text, existing_ops, exit_gates)`, which returns
`(new_ops, spec_edits)`. Writes go through `fr.artifacts.atomic.write_text_atomic`:
`ops.yaml` is stamped 2, and the spec lines are edited in place by step position. The verb
is gated by the artifact trigger like the rest of `fr ops`.

### E. Prose (R12)

The changes:
- `fr-plan` SKILL.md: one compressed line in its ops/manual-work paragraph.
- `fr-devops-gate` SKILL.md: its stage-5 line names probes and the stage-1 refusal.
- `docs/ops.md`: a "Test Plan probes" section (pointer, stub, `none:`, the evidence bound
  and its privacy note).
- Then run `scripts/sync-opencode.py` and `scripts/sync-hermes.py`.

### Out of scope

The parallel runs' files (`fr/artifacts/trigger.py`, `fr/gates.py`, `fr/debt/`) are not
touched. An inline step `check:` is not supported (decision q3).

## Verification

strategy: candidate
gate: none
gate: ops-gate-probes-first-real-use=none
- ops-gap-advisory: none — pure functions and self-review output, verified by CI unit tests
- ops-none-acknowledgement: none — loader, validator and migration, verified by CI unit tests
- ops-stub-cli: none — a pure proposer plus a file write, verified by CI unit and CLI tests
- ops-gate-probes-first-real-use: live — only a real devops-gated run with real probes shows it; walked on first real use

The candidate walk runs a new scenario `tests/scenarios/fr-ops-gate-probes.sh` (same
harness as `fr-ops-gate-stage.sh`: host-worktree mode, fake forge, real candidate `fr`).
It covers the stage-1 refusal, the refusal lifted by `none:`, a pointed step recorded `ran`
with probe output, an OPEN probe answered `owed`, and `ran: x` accepted after one malformed
answer is re-prompted. Rows `ops-gate-gap-refusal` (R5), `ops-gate-step-probe` (R6, R8, R9)
and `ops-gate-answer-grammar` (R10) carry no override line, so they take the run-level
`candidate` strategy and this scenario. R7's errors sit with `ops-gap-advisory`. Every row
also gets CI unit tests.

## Test Plan

1. Walked on first real use: the next devops-gated run's `fr ops gate` shows a pointed step DONE with its probe output recorded as `ran` evidence, and an unpointed step's `ran: …` answer is accepted. **Cost:** none. It is observed on the next real devops-gated run, not rehearsed.
