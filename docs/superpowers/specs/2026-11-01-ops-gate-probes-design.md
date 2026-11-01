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

R1. One function, `fr.ops.gap`, decides whether a run has an **ops gap**: its effective gates include `devops`, its plan declares no op (in either plan carrier, the runbook excluded), its `ops.yaml` carries no `none:` acknowledgement, and at least one of its Test Plan steps contains a command. It returns the command steps, each with the commands it found.
R2. A Test Plan step "contains a command" when it carries no op pointer and holds an inline code span or a fenced code block whose first word looks like an executable (a bare name such as `ansible-playbook` or a relative path such as `./scripts/x`) followed by at least one argument. This heuristic is documented as one, and the acknowledgement (R4) is its escape.
R3. `fr plan self-review` reports an ops gap as a **warning** naming each command step and its commands, plus the two fixes (`fr ops stub`, or `none:` in `ops.yaml`). Resolving `spec-review` done prints the same warning when the spec's run is devops-gated and has command steps: there is no plan yet, so it says that these steps will need ops. Neither one refuses.
R4. `ops.yaml` gains an optional `none: <reason>` key (non-empty string). It is valid only when `ops:` is empty or absent, and it means "no ops on purpose". A file with both is refused by name. The `ops` artifact kind moves from version 1 to 2 with a registered stamp migration and an updated structure validator (`.claude/rules/artifact-versioning.md`). A `none:` file never counts as ops for the R13 gate promotion (`plan_has_ops` stays false).
R5. `fr ops gate` **stage 1 refuses** (exit 2, nothing brought up, nothing recorded) when the run has an ops gap. The refusal names each command step with its commands and both fixes, which are added on the PR branch, so the PR head the stage cuts from carries them.
R6. A Test Plan step may **point at an op** with `(op: <id>)` leading its text, after the optional gate tag: `- [devops] (op: guest-verify) Run the verify playbook`. `fr.spec.Step` gains an `op` field, and the step's `text` no longer contains the pointer. An inline `check:` on a step is not supported.
R7. `fr plan self-review` reports an **error** when a step's pointer names an op the plan does not declare.
R8. Stage 5 runs a pointed step's probe instead of asking. It runs `fr ops status <id> --plan <plan> --json` in the ops workspace, under the same trust grant as the op set, and shows the state and output. **DONE** records `fr closeout outcome --ran` whose evidence is the probe's masked, clipped output (or `check passed (exit 0)` when it printed nothing), with no question. **OPEN, UNVERIFIABLE or CANNOT-VERIFY** shows the reason, then asks `retry`, `na <reason>` or `owed <why>`. `retry` re-runs the probe, and `ran` is refused for a failing probe. Steps with no pointer keep today's prompt.
R9. `fr ops status --json` rows gain `output`: for a DONE check, the probe's stdout masked as reasons are (`sanitise_reason`'s masking) and clipped to a bound; otherwise `null`.
R10. Stage 5's answer grammar accepts an optional `:` or `-` after the keyword (`ran: x`, `na - y`), while still requiring a separator (`rancid` is not `ran`). A non-matching answer is **re-prompted**, echoing what was received and the expected grammar. The stage fails, with that same echo, only after three consecutive non-matches or an empty answer from a closed terminal.
R11. A new `fr ops stub [--plan <dir>] [--yes]` reads the plan's spec and, for each command step without a pointer, proposes an `ops.yaml` op stub: id `step-<n>`, `summary` = the step text clipped, `phase: post-merge`, `apply:` = the step's first command, no `check:` (so `fr ops status` reports it UNVERIFIABLE until one is written). It also proposes the step's `(op: step-<n>)` pointer. Without `--yes` it prints the stubs and the spec edits and writes nothing. With `--yes` it writes both, and it refuses (writing nothing) on an id that is already declared or on a `none:` acknowledgement.
R12. The `fr-plan` skill tells the planner, for a devops-gated spec, to split the Test Plan into runnable steps (→ ops, via `fr ops stub`, then a real `check:`) and physical/judgement steps (→ prose). The `fr-devops-gate` skill and `docs/ops.md` describe R4–R11. Both skills stay within the 120-line cap, and their OpenCode and Hermes mirrors are regenerated.

## Design

### A. The gap (R1–R3)

`packages/fr/src/fr/ops/gap.py` (new):

```
@dataclass(frozen=True)
class CommandStep: n: int; text: str; commands: tuple[str, ...]
def step_commands(step: Step) -> tuple[str, ...]          # R2, pure
def command_steps(steps: Sequence[Step]) -> list[CommandStep]
def ops_gap(repo_root: Path, spec: Path, plan_dir: Path | None, exit_gates: Set[str]) -> list[CommandStep]
def gap_message(steps: list[CommandStep], *, has_plan: bool) -> str
```

`step_commands` reads the step's raw text. The parser joins continuation lines into one
line, so a fenced block inside an item shows up as inline spans. Candidate spans are
backtick spans. A span counts when its first word matches `^(\./|\.\./|[\w.-]+/)*[A-Za-z][\w.+-]*$`
and the span has a second word. A lone path like `config/x/vault.yml` is not a command.
`ops_gap` returns `[]` unless `devops ∈ exit_gates`, the plan has no op
(`plan_has_ops` is false) and `ops.yaml` has no `none:`. `exit_gates` comes from
`fr.verification.exit` (the same effective-gate computation stage 5's `gated_steps` uses),
read through its public function. `fr/gates.py` is not edited.

Callers:
- `plan_ops.self_review` adds a `warning` ReviewIssue when the plan's spec yields a gap
  (R3), and an `error` per dangling pointer (R7).
- `run_cmd`: at the existing spec-review `done` hook (`_spec_review_ids`), print
  `gap_message(..., has_plan=False)` to stderr. This is advisory and never changes the exit.
- `gate.stage_1` (R5): after the profile checks and before `isolation up`, compute the gap
  against the **PR head's** tree (`tree.show(head, …)` / the host's checkout of the feature
  ref) and raise `StageFailed(code=2)` with `gap_message`.

### B. The acknowledgement (R4)

`OpsFile` gains `none: StrictStr | None = Field(default=None, min_length=1)`, plus a model
validator that refuses `none` together with a non-empty `ops`. `load._ops_yaml` accepts the
`none` key, and a new `load.ops_none(plan_dir) -> str | None` reads it. The registry moves
`ops` to `current_version=2`. The migration is a stamp-only `SchemaMigration` 1→2 (no body
change: every v1 file is a valid v2 file), registered through a module imported by
`fr/artifacts/__init__.py`. `validate_ops` accepts version 2's key, and
`fr migrate artifacts --yes` is run in the same PR.

### C. The pointer and the probe (R6–R9)

`fr.spec`: `_POINTER_RE = ^\(op:\s*(?P<id>[A-Za-z0-9][\w.-]*)\)\s+(?P<rest>\S.*)$` is
applied after the tag, so `Step(n, text, gate, op)`. Every existing caller reads
`text`/`gate`, so the pointer drops out of displayed text. The spec artifact's on-disk
shape is unchanged (it is still prose to an older fr), so no spec stamp bump is needed.

`engine._check` keeps the last successful run's stdout. `StatusRow.output` is filled on
DONE through a new `mask.clip_output(text, secrets, limit=2000)`, which masks like
`sanitise_reason` but keeps lines. `as_row` emits it. The runner protocol already returns
`(rc, out)`.

`gate.stage_5` (rewritten loop): for each devops step not already closed at head,
- `step.op` set → `_probe_step(gate, tree, step)`: run `gate.exec_args("ops", "status",
  step.op, "--plan", plan_rel, "--json")`, parse the one row, and `gate.say` the state and
  output/reason. DONE records `--ran --evidence "<op id>: <output>"` and moves on.
  Otherwise ask with the OPEN grammar (`retry | na <reason> | owed <why>`).
- no pointer → today's question, with the R10 grammar.

`_ask_outcome(gate, text, allowed)` holds the re-prompt loop (R10), shared by both
branches. `_ANSWER = ^\s*(ran|na|n/a|owed|retry)(?:\s*[:\-]\s*|\s+)(\S.*)?$`, plus an
allowed-set check (`retry` takes no argument, and the others need one).

### D. Stubs (R11)

`fr ops stub` in `commands/ops_cmd.py` calls a pure `fr.ops.stub.propose(spec_text, ops)`
that returns `(ops_yaml_additions, spec_edits)`. Writes go through
`fr.artifacts.atomic.write_text_atomic`. The verb is gated by the artifact trigger like the
rest of `fr ops`.

### E. Prose (R12)

`fr-plan` SKILL.md gets one compressed line in its ops/manual-work paragraph. The
`fr-devops-gate` SKILL.md stage-5 line names probes and the stage-1 refusal. `docs/ops.md`
gets a "Test Plan probes" section and the `none:` key. Then `scripts/sync-opencode.py` and
`scripts/sync-hermes.py`.

### Out of scope

The parallel runs' files (`fr/artifacts/trigger.py`, `fr/gates.py`, `fr/debt/`) are not
touched. Inline step `check:` is not supported (decision Q3). Gap detection by tool name
lists is not part of this change.

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
with probe output, an OPEN probe answered `owed`, and `ran: x` accepted.

## Test Plan

1. Walked on first real use: the next devops-gated run's `fr ops gate` shows a pointed step DONE with its probe output recorded as `ran` evidence, and an unpointed step's `ran: …` answer is accepted. **Cost:** none. It is observed on the next real devops-gated run, not rehearsed.
