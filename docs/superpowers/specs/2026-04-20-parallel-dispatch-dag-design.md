# Parallel Dispatch via Explicit Phase DAG

**Status:** Draft
**Date:** 2026-04-20
**Repos affected:** `derio-net/superpowers-for-vk`, `derio-net/agent-images` (bridge audit)

## Goal

Replace the implicit "Phase N depends on Phase N-1" chain in `vk dispatch` with an explicit, author-declared dependency DAG per plan. Unlock safe parallel execution of independent phases (fan-out, fan-in, diamond shapes) while preserving the fail-loud guarantees that post-dated the Frank hextra incident.

## Problem Statement

The current `vk` toolchain encodes a single, implicit dependency model:

- `src/vk/commands/dispatch_cmd.py:290` computes `prev_num = phase_to_issue.get(phase.number - 1)` and emits exactly one `- Blocked by #<prev>` line per dispatched Issue.
- `src/vk/commands/dispatch_body_validator.py:32-41` requires that line for any phase with `number > 0`.
- `src/vk/commands/execute_cmd.py:88-97` refuses execution of Phase N until every phase with a lower number has all steps checked.
- The VK Issue Bridge (`kali/scripts/vk-issue-bridge.py`) consumes the resulting format via its `parse_dependencies` / `check_blockers` gate.

A plan with independent phases — e.g., five microservice scaffolds, or a documented fan-out like the parent spec's "P3 and P4 can run in parallel after P2" — must be serialised by hand, because the plan file cannot express "Phase 5 depends on Phase 2 only."

The implicit-N-1 model was never an affirmative design choice. It is the simplest thing that passed the post-hextra fail-loud tests: after the bridge silently treated every phase as unblocked due to a whitespace-sensitive regex mismatch (`Blocked by #N` vs `- Blocked by #N`), the repair (`2026-04-14-archive-and-unified-descriptions-design.md` §4-§8) hardened the *format* but left the *semantics* at one-previous-phase.

## Non-goals

- Task-level parallelism within a single phase. One phase still corresponds to one Issue and one PR.
- Cross-plan or cross-repo dependency refs. `**Depends on:**` references are plan-local.
- A dependency format richer than "these phases must be CLOSED before I start" (e.g., `any-of`, `optional`, time-boxed). Pure AND-of-closed-blockers is the v1 contract.
- Rewriting the VK Issue Bridge. The bridge audit in Section 5 is verification, not replacement.
- Migrating closed Issues. The `vk dispatch migrate` update in Section 3 refuses to infer deps silently; operators migrate the plan file with `vk plan convert --add-deps` first.

## Cross-cutting principle: fail loud, fail actionable

Inherited from the unified-descriptions spec and reinforced here. Every new validation gate names the offending phase, the rule it broke, and the command to fix it. No silent defaults, no `except Exception: pass`, no inference where declaration is absent.

## Design Decisions

| # | Decision | Alternatives considered |
|---|---|---|
| D1 | Explicit `**Depends on:**` line per phase. Absence on a non-root phase is a validation error. | Header-suffix `(depends on: 1, 2)`; hybrid with N-1 fallback. |
| D2 | Value grammar: `Phase <int>` refs, comma-separated; `—` (em-dash, canonical) or `None` for roots. | Bare integers; Issue-number refs. |
| D3 | Backward-only deps (`depends_on[i] < i`). Forward refs are rejected. | Full any-order DAG with topological sort. |
| D4 | Archived plans in `archived-plans/**` are exempt from the requirement. | Retro-migrate everything; require the line even for history. |
| D5 | Body validator accepts either `None —` or ≥1 `- Blocked by #N` lines. | Keep requiring the dash-prefixed line on every non-root phase (already implied by D1). |
| D6 | `vk plan convert --add-deps` migrates linear plans in one command. Idempotent; refuses mixed plans. | Manual migration; auto-inference inside `dispatch migrate`. |
| D7 | `vk dispatch migrate` refuses legacy dispatched plans with no `**Depends on:**` lines. Points at `convert --add-deps`. | Auto-run `convert --add-deps` under the hood during migrate. |
| D8 | `vk execute check-deps` reads the declared DAG, not N-1. Non-declared earlier phases do not block pickup. | Keep N-1 gate as a defensive fallback; add a separate `check-deps --strict` mode. |
| D9 | Scope (b): this repo + bridge audit. Phase C PR in `agent-images` is an integration test plus any needed fix. | Scope (a) — assume bridge handles multi-blocker; scope (c) — add per-plan slot budget. |
| D10 | Minor version bump `1.0.12 → 1.1.0`. User-visible grammar and new subcommand mode. | Patch (too small for a workflow addition); major (no breaking API change — old plans work after migration). |

## What stays unchanged

- Dispatch gate semantics (opt-in via `plan-config.yaml::dispatch`).
- Issue body sections: `## Instruction`, `## Workspace`, `## Dependencies`. Only the content inside `## Dependencies` gains the possibility of multiple lines.
- Issue title format, tracking block, labels (`plan:<slug>`, `phase:<n>`).
- Bridge contract: dash-prefixed `- Blocked by #N` lines, CLOSED-only gate.
- Agent-side "BEFORE YOU BEGIN" preamble (defence-in-depth).
- Plan filename convention and spec-index integration.

---

## 1. Plan grammar, parser, and validation

### 1.1 Grammar

Every phase declares its blockers on a dedicated line directly under the phase header (after any `<!-- Tracking: ... -->` comment so the line stays stable across dispatch):

```markdown
## Phase 1: Scaffold [agentic]
**Depends on:** —

## Phase 2: Core modules [agentic]
**Depends on:** Phase 1

## Phase 3: Dispatch [agentic]
**Depends on:** Phase 2

## Phase 4: Progress [agentic]
**Depends on:** Phase 3

## Phase 5: Plan + execute helpers [agentic]
**Depends on:** Phase 3

## Phase 6: Skill rewrites [agentic]
**Depends on:** Phase 4, Phase 5
```

Format rules:

- Line grammar: `**Depends on:** ( — | None | Phase <int> ( , Phase <int> )* )`.
- Root phases use `**Depends on:** —` (em-dash, U+2014) as canonical; `None` is accepted as an alias.
- Values are phase numbers, not GitHub Issue numbers. The plan is authored before Issues exist.
- Multiple roots are permitted: Phase 1 and Phase 2 may both declare `—`, enabling diamond and parallel-init shapes.
- The line lives directly under the `## Phase N:` header or its `<!-- Tracking: ... -->` comment; any other location is a parse error.

### 1.2 Parser model change

`src/vk/plan/models.py::Phase` gains one field:

```python
@dataclass(frozen=True)
class Phase:
    number: int
    title: str
    tag: Literal["manual", "agentic"]
    depends_on: tuple[int, ...]    # NEW. Empty tuple = root phase.
    tasks: tuple[Task, ...]
    tracking_url: str | None
```

`src/vk/plan/parser.py` extracts the `**Depends on:**` line per phase. Parse errors raise `ValueError` naming the offending phase number and the unparseable text. The parser does not fabricate a default value when the line is absent — the missing-line case is surfaced by the validation layer (Section 1.3), not silently filled in.

### 1.3 Validation

Runs at two gates: `vk plan self-review <plan>` and `vk dispatch <plan> --dry-run`. Both must pass before any mutation.

| Check | Message |
|---|---|
| Non-root phase missing `**Depends on:**` line (live plan) | `Phase N has no **Depends on:** line. Run 'vk plan convert <plan> --add-deps' to migrate, or declare it manually.` |
| Unknown phase ref | `Phase N depends on Phase X, which does not exist in this plan.` |
| Forward reference (depends on Phase ≥ self) | `Phase N depends on Phase M — forward reference; only backward deps are permitted.` |
| Self-reference | `Phase N depends on itself.` |
| Grammar violation | `Phase N: could not parse dependency list '<text>'.` |

**Why backward-only (D3).** A true DAG admits any acyclic ordering, but restricting to `depends_on[i] < i` buys: trivial cycle detection (the `<` check *is* the cycle check), deterministic dispatch-create order (phase-number order equals topological order), and plans that read top-to-bottom are already sorted. Plan authors keep the "lowest phase number = earliest work" mental model.

### 1.4 Archived-plans exemption

Plans in `docs/superpowers/archived-plans/**` are parsed but not validated against the `**Depends on:**` requirement. Historical record stays as written. Migration only touches live plans.

### 1.5 Relationship to existing plans

Today's implicit N-1 chain becomes the explicit literal declaration. `Phase N` (N ≥ 2) currently means "depends on N-1"; that becomes `**Depends on:** Phase {N-1}`. `vk plan convert --add-deps` performs exactly this rewrite (Section 2.4).

---

## 2. Dispatch, execute, and migration behavior

### 2.1 Dispatch: emit one `- Blocked by #N` per declared dep

`_build_issue_body` in `src/vk/commands/dispatch_cmd.py` takes `blocker_nums: tuple[int, ...]` instead of `prev_num: int | None`:

```python
def _build_issue_body(phase, plan_path, target_repo, blocker_nums,
                     total_phases, spec, goal):
    if not blocker_nums:
        deps_block = "None — no blocking phases."
    else:
        deps_block = "\n".join(f"- Blocked by #{n}" for n in blocker_nums)
    ...
```

The create-loop computes the tuple from the phase's declared deps:

```python
blocker_nums = tuple(phase_to_issue[dep] for dep in phase.depends_on)
```

Because deps are backward-only (D3) and phases are iterated in number order, every `dep` is present in `phase_to_issue` by the time its dependent is dispatched. If a dep is missing — e.g., because its `gh issue create` failed mid-run — the loop fails loud with the missing-dep phase number. The dependent is not dispatched with a partial body.

Emitted Issue body for Phase 6 (deps on 4 and 5):

```markdown
## Dependencies

- Blocked by #144
- Blocked by #145
```

### 2.2 Body validator relaxation

`src/vk/commands/dispatch_body_validator.py::validate_issue_body` changes from "phase > 0 must contain `- Blocked by #`" to:

> The `## Dependencies` section must contain EITHER the literal line `None — no blocking phases.` OR one or more `- Blocked by #<int>` lines.

Both shapes are accepted. The validator still fails loud on malformed output. Root phases emit the `None —` form; non-root phases emit ≥ 1 blocker lines.

### 2.3 `vk execute check-deps` rewrite

`src/vk/commands/execute_cmd.py::check_deps` stops walking every phase `< target` and reads the target phase's declared deps:

```python
plan = parse_plan(plan_path)
phases_by_num = {p.number: p for p in plan.phases}
target_phase = phases_by_num.get(target)
if target_phase is None:
    die(f"Phase {target} not found")

for dep_num in target_phase.depends_on:
    dep_phase = phases_by_num[dep_num]
    unchecked = sum(1 for t in dep_phase.tasks for s in t.steps if s.state == " ")
    if unchecked > 0:
        die(f"Phase {target} depends on Phase {dep_num}, "
            f"which has {unchecked} unchecked step(s).", code=1)

dep_list = ", ".join(f"Phase {n}" for n in target_phase.depends_on) or "none (root phase)"
console.print(f"Dependencies satisfied for Phase {target} (checked: {dep_list}).")
```

Two behavioural changes from today:

- Phases not declared as deps do not block pickup. A late-added parallel phase can start as soon as its own declared deps are done.
- Output lists the phases that were actually checked, letting the operator confirm at a glance.

This change benefits local-mode execution too: plans dispatched nowhere still get correct parallel-friendly gating via this path.

### 2.4 `vk plan convert --add-deps`

A new mode of the existing `vk plan convert` command, defined in `src/vk/plan/convert.py`:

- **Input:** a phased plan with no `**Depends on:**` lines on any phase.
- **Output:** the same plan with `**Depends on:** —` on Phase 1 (the lowest-numbered phase) and `**Depends on:** Phase {N-1}` on every subsequent phase.
- **Idempotent:** if a phase already has a `**Depends on:**` line, it is left alone.
- **Mixed plans refused:** if some phases have the line and some do not, the command exits with `Phase N has **Depends on:** but Phase M does not. Declare both or neither — auto-inference is disabled.`
- **Honours** the `--dry-run` / `--yes` contract shared by every mutating `vk` subcommand.
- **Commits** with `chore(plan): add **Depends on:** lines (migration)`.

### 2.5 `vk dispatch migrate` interaction

For already-dispatched legacy plans — tracking comments exist, no `**Depends on:**` lines — `vk dispatch migrate` refuses:

```
Error: Plan has dispatched Issues but no **Depends on:** declarations.
Migrate the plan file first, then re-run migrate:
  vk plan convert <plan> --add-deps --yes
  vk dispatch migrate <plan> --yes
```

Rationale (D7): `vk dispatch migrate` rewrites Issue titles and bodies against the current dispatch contract. Silently inferring deps would smuggle an implicit N-1 assumption back in at the exact point where the whole design is moving it out. The two-command migration is one extra keystroke that keeps the DAG visible on disk first.

### 2.6 Operational rollout

Because scope (b) spans two repos, rollout sequences in three phases:

1. **Phase A — superpowers-for-vk grammar + dispatch.** Parser changes, validation, dispatch emission, body-validator relaxation. Tests. PR 1 in this repo.
2. **Phase B — superpowers-for-vk tooling + execute.** `check-deps` rewrite, `convert --add-deps`, `dispatch migrate` guard, skill docs, version bump. Tests. PR 2 in this repo.
3. **Phase C — agent-images bridge audit.** Read-through of `vk-issue-bridge.py::parse_dependencies` and `check_blockers`. Add the fan-in integration test from Section 5. If the read-through finds a gap, the same PR fixes it. PR 3 in `derio-net/agent-images`.
4. **Operational migration.** Run `vk plan convert --add-deps` on every active plan in `derio-net/*` repos. Run `vk dispatch migrate` afterwards for already-dispatched plans.

Phase A and B are independently safe to ship without Phase C: emitting multiple `- Blocked by #N` lines is a superset of today's single-line format; the bridge's existing regex parses each line individually regardless. Phase C is verification, not an unblocker.

---

## 3. Bridge audit (agent-images)

### 3.1 Read-through scope

Verify in `kali/scripts/vk-issue-bridge.py`:

- `parse_dependencies` returns a `list[int]` (or tuple), iterating every `- Blocked by #N` line inside the `## Dependencies` section.
- `check_blockers` iterates that list, calls `gh issue view <n> --json state`, and defers the Issue if any blocker is not `CLOSED`.
- Deferral happens before workspace/slot allocation. No slot is consumed for a deferred Issue.
- `check_blockers` fails loud on `gh` errors (per §7 of the unified-descriptions spec).

### 3.2 Regression test

Whether the code already handles multi-blocker or not, add a regression test pinning the contract:

```
Scenario: fan-in DAG

  Given Issue #1 (OPEN), Issue #2 (OPEN),
        Issue #3 with body containing "- Blocked by #1\n- Blocked by #2"

  When  the bridge processes #3's webhook
  Then  #3 is deferred (no workspace spawned, no slot consumed)

  When  Issue #1 transitions to CLOSED
  Then  #3 is still deferred

  When  Issue #2 transitions to CLOSED
  Then  #3's workspace is spawned on the next bridge tick
```

The test doubles as executable documentation of the CLOSED-only, AND-of-all-blockers semantics.

### 3.3 Expected outcome

If §8's plural-preamble language in the unified-descriptions spec reflects the code accurately, Phase C is a test-only PR. If it does not, the same PR adds the missing iteration. Either way, the bridge emerges with an explicit regression test against the DAG contract.

---

## 4. Testing strategy (this repo)

### 4.1 Unit tests

| File | New cases |
|---|---|
| `tests/unit/test_plan_parser.py` | Parses `**Depends on:** —` as empty tuple. Parses `Phase 1, Phase 2` as `(1, 2)`. Malformed lines raise with the phase number. Accepts `None` as alias for `—`. |
| `tests/unit/test_plan_writer.py` | Round-trip: parse → write → parse preserves `depends_on` exactly. |
| `tests/unit/test_plan_convert.py` | `--add-deps` on linear plan produces `—`+N-1 chain. Idempotent re-run is a no-op. Mixed plans refused with the specific error. |
| `tests/unit/test_dispatch_body.py` | Body with empty `depends_on` emits `None — no blocking phases.`. With `(4, 5)` emits two dash-prefixed lines in order. |
| `tests/unit/test_dispatch_body_validator.py` | Validator accepts both shapes. Rejects malformed (e.g. `Blocked by #5` missing dash). |
| `tests/unit/test_cli.py` | `self-review` and dispatch `--dry-run` each surface cycle / forward-ref / missing-line / unknown-ref errors with the specific message. |

### 4.2 Integration tests

| File | New cases |
|---|---|
| `tests/integration/test_dispatch.py` | Fan-out plan (Phase 3 depends on Phase 1 and Phase 2) creates three Issues. Phase 3's body contains both `- Blocked by` lines in declared order. |
| `tests/integration/test_plan_execute.py` | `check-deps` on Phase 5 (depends on Phase 3 only) succeeds when Phase 3 is complete even if Phase 4 still has unchecked steps. Today's behaviour would wrongly refuse. |
| `tests/integration/test_convert.py` | End-to-end `--add-deps` on a real fixture plan. Asserts file content after conversion, re-runs the command to confirm idempotency. |

### 4.3 Contract tests

No new `gh` subprocess shapes are introduced. The existing mocked `gh` tests in `tests/unit/test_gh.py` continue to cover create/edit/labels/project.

### 4.4 Fixtures

Two new plan fixtures in `tests/fixtures/plans/`:

- `phased-dag.md` — six phases, fan-in/fan-out shape, for parser and dispatch tests.
- `phased-no-deps.md` — four phases, no `**Depends on:**` lines, for the `--add-deps` migration test.

### 4.5 Coverage

The coverage gate stays at 85 %. The new code is pure parsing + validation + string formatting, which reaches full coverage cheaply.

---

## 5. Release mechanics

Per `CLAUDE.md`, any PR that changes `src/**` or `skills/**` bumps the version across three files in lockstep:

| File | Field |
|---|---|
| `pyproject.toml` | `[project].version` |
| `.claude-plugin/plugin.json` | `.version` |
| `.claude-plugin/marketplace.json` | `.plugins[0].version` |

After editing, run `uv sync` and confirm `uv run vk --version`.

**Version target:** `1.0.12 → 1.1.0` (minor bump — new user-visible plan grammar and new subcommand mode, no breaking API change for plans that have been migrated).

Skill docs updated in the same PR that changes behaviour:

- `skills/vk-plan/SKILL.md` — sample phase block with `**Depends on:**`; link to `vk plan convert --add-deps`.
- `skills/vk-dispatch/SKILL.md` — note that `dispatch migrate` refuses until `convert --add-deps` has run; example error message.
- `skills/vk-execute/SKILL.md` — `check-deps` description updated to mention the declared DAG.

## 6. Rollback story

Each PR is independently revertible. The change is additive in the grammar (new line) and permissive in the validator (accepts either shape). Post-rollback:

- Plans with `**Depends on:**` lines stay parseable by the old parser — the line sits between `## Phase N:` and the first `###` task header and is not consumed by today's regex.
- `check-deps` returns to the N-1 behaviour; plans that relied on parallelism lose it until the code is re-deployed but do not break.
- `convert --add-deps` edits on plan files are cosmetic on rollback — they do not alter semantics under either the old or new code.

No irreversible schema change is introduced.

## 7. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Author declares `Phase 3 depends on Phase 5` (forward ref); validator catches it late. | Validate at `self-review` AND `dispatch --dry-run` (D3). Two gates before any mutation. |
| Plan author migrates with `--add-deps` then hand-edits to a real DAG, introducing a typo like `Phase 1, Phas 2`. | Grammar is strict; parser raises with the unparseable text and the phase number. |
| Bridge silently accepts a second `- Blocked by #N` line but only gates on the first. | Phase C regression test pins multi-blocker AND semantics. |
| Operator forgets to run `convert --add-deps` before `dispatch migrate`; migrate rewrites Issue bodies against a stale single-dep assumption. | `dispatch migrate` refuses and points at the correct command (D7). |
| Workspace-slot starvation under wide fan-out exceeds capacity. | Acknowledged explicitly as scope (b) limitation; operator has the option to raise the slot ceiling. No per-plan budget introduced in this spec. |

## 8. Open questions

None at spec time. Phase A's unit tests will surface any grammar edge cases missed here (e.g., Unicode whitespace around refs, trailing commas).

## Implementation Plans

| Plan | Repo | File | Status | Depends on |
|------|------|------|--------|------------|
| Parallel Dispatch DAG Implementation Plan | `derio-net/superpowers-for-vk` | `docs/superpowers/plans/2026-04-20-parallel-dispatch-dag.md` | Not Started | — |
| Bridge Audit Implementation Plan | `derio-net/agent-images` | `docs/superpowers/plans/2026-04-20-parallel-dispatch-dag-bridge-audit.md` | Not Started | Phase 2 of the superpowers-for-vk plan |
