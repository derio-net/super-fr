# fr-goal subagent execution — journal-fed, tier-selected phase dispatch

Status: design
Origin: operator brainstorm (2026-07-22). Started as "add a `/compact`/`/clear`
handoff after each code review to keep context fresh and cut cost"; harness
verification redirected the mechanism to subagents (the one context-isolation
primitive available unattended across all target harnesses).

## Problem

`fr-goal` implements every phase **inline in one long conversation** and
explicitly forbids subagents: *"Implement inline, not via subagents (the
context needs the Q&A + spec history)"* (`fr-goal/SKILL.md:86`). Two costs:

1. **Context bloat / cost.** A run accumulates brainstorm + Q&A + spec + plan +
   every phase's file reads, test output, and failed attempts + every review
   finding in a single window. Long runs approach the context limit; the
   operator's original ask was to reset context at phase boundaries.
2. **Run-state is remembered, not durable.** The Q&A answers, review outcomes,
   per-phase discoveries, and review findings/fixes/refutations live *only* in
   the conversation. Grep confirms no persistence: a plan folder is
   `_meta.yaml` / `_prose.md` / `NN.yaml`, the sole note surface a per-step
   `note: str | None` (`types.py:105,111`). fr-goal step 8 requires the
   findings list *verbatim* in the PR body — today that is memory, and it thins
   silently if context is compacted.

### Why not `/compact` or `/clear` (the original idea)

Harness verification (Claude Code docs, 2026-07-22): `/compact` and `/clear`
have **no** tool, flag, hook, or MCP trigger — user-typed only, so an
unattended run cannot invoke them. A `PreCompact` hook cannot *flush* state (a
shell script has no access to model context); it can only refuse a compaction.
And on compaction, re-injected skill bodies are capped 25K oldest-first — an
fr-goal run's own orchestrating body is first to be evicted. The mechanism does
not survive the unattended constraint.

### Why subagents (the redirect)

The one capability confirmed across **all three target harnesses** is
subagents with isolated context (Claude Code Task / `model`-per-dispatch;
OpenCode Task/`@agent`; Hermes `delegate_task`). A per-phase subagent:

- keeps the phase's file reads / test runs / dead ends **out of the parent
  context** — only its result returns, so the parent stays lean and rarely
  needs compaction at all (the problem is *subsumed*, not guarded against);
- inherits **no** parent history — so it needs the Q&A + spec history from
  somewhere durable. That "somewhere" is the journal. **The journal is the
  handoff channel that makes the forbidden subagents possible;** the two are
  one feature.

## Design

Three components, all **harness-agnostic** (no hooks, no harness-specific
lifecycle events). A (journal primitive) and B (fr-goal subagent execution)
are the core and ship together; C wires fr-debugging onto the same journal
(A, no B). The journal is a **shared, scope-keyed primitive**, so A serves both
fr-goal (spec + plan scopes) and fr-debugging (debug scope).

**Why no compaction-safety hooks.** An earlier draft carried a Claude-only
`PreCompact` guard + `SessionStart` rehydrate as a backstop for the parent's
residual context. Dropped deliberately: with B in place the parent stays lean
and rarely compacts, so the backstop guards a case that mostly no longer
occurs — questionable benefit for definite complexity (a `trigger:manual|auto`
deadlock split, an experimental-API OpenCode analog, and nothing at all on
Hermes). Continuous flush through the CLI already makes run-state durable on
**every** harness; that is the whole guarantee, and it needs no hook. Staying
hook-free keeps all three components portable by construction.

### A. `journals/` — durable run-state, parallel to `specs/` and `plans/`

A new tree `docs/superpowers/journals/`, mirroring the existing
`specs/`+`plans/` layout and its `implemented/` archive. The `fr journal`
primitive is **scope-keyed and pipeline-agnostic** (`--scope spec|plan|debug`),
not fr-goal-specific — so fr-debugging can adopt it (component C) without a
schema change. **Scopes** (fr-goal uses spec + plan; the `debug` scope is
defined here so nothing is fr-goal-shaped, wired by C):

| File | Scope | Repo | Holds | Born |
|---|---|---|---|---|
| `journals/specs/<spec-slug>.md` | whole feature | spec-owning repo | Q&A **decisions**, spec-**review** outcomes, cross-repo location decisions | at spec write (step 2) — no pre-plan window |
| `journals/plans/<plan-slug>.md` | one plan | each plan's repo | per-phase **discoveries** / dead ends, review **findings**/fixes/refutations | at `fr plan create` |
| `journals/debug/<debug-slug>.md` | one investigation | the fix branch's repo | **repro**, **hypothesis**, **ruled-out**, **root-cause**, fix + verification | at fr-debugging start (component C) |

Each scope is its own subdirectory (`specs/`/`plans/`/`debug/`) so a bare
`ls journals/` is self-describing — a debug-slug can otherwise look identical to
a plan-slug. The archive mirror is `implemented/journals/<scope-dir>/`.

Multi-repo: repo-B's agent writes findings that ship in repo-B's PR, so
findings must live in a *plan*-scoped journal in repo B — a single spec-level
journal cannot express this. Single-repo runs carry both files; each has a
distinct lifetime (the spec journal spans reworks; a plan journal archives
**with its plan** to `implemented/journals/`, mirroring `archive.py`).

Entries are append-only, written **only** via the `fr journal` CLI (parseable
+ readable, like `NN.yaml` is machine and `_prose.md` is prose). Kinds:
`decision`, `review`, `discovery`, `finding` (fr-goal; `finding` carries
`fixed`/`refuted`/`open`); plus `repro`, `hypothesis`, `ruled-out`,
`root-cause` (the `debug` scope, wired by C). Each entry: kind, stable id,
timestamp, phase (nullable), title, body. The kind set is a defined enum, not
free-form, so `render` and `check` stay deterministic across pipelines.

**`fr journal` CLI:**
- `fr journal add --scope spec|plan --slug <s> --kind <k> --title <t>
  [--phase N] [--body <b>] [--state ...] [--id <caller-id>]` — append;
  idempotent on `--id` so a re-run does not double-write.
- `fr journal render --scope ... --slug ... [--section findings|decisions|all]`
  — emit the Markdown the PR body embeds. **The payoff that makes the journal
  stand alone:** step 8's findings/decisions sections become *generated*, not
  remembered.
- `fr journal check --scope ... --slug ...` — parse + freshness heuristic:
  non-zero when completed phases have no discovery/finding entries or findings
  remain `open` at PR time. Advisory, fail-closed on parse for `check`,
  fail-open for `render`.

`fr plan create` initializes the plan journal; the spec journal is created on
first `fr journal add --scope spec` (or at spec write).

### B. Subagent-per-phase execution (replaces fr-goal step 6 inline rule)

fr-goal's implementation step changes from "inline, no subagents" to:

For each phase in **dependency order** (serial — `depends_on` respected), the
orchestrator dispatches **one subagent** that:

1. receives a self-contained brief: `fr pickup <plan-dir> --phase N` (phase
   scope) + the spec + the relevant journal slices (decisions, prior
   discoveries, open findings) via `fr journal render`;
2. implements the phase **TDD** (red→green→refactor) inside the **shared**
   fr-isolation workspace (see §B.1);
3. appends its discoveries and any findings back to the plan journal
   (`fr journal add --scope plan`);
4. returns a **structured result** (steps ticked, tests run + output, files
   touched, journal entry ids) to the parent — the only thing that re-enters
   parent context.

The parent orchestrates, reviews (step 7) against the returned results +
journal, and opens the single PR (step 8). **No new operator gate** — the
existing batched Q&A (step 1) remains the only touchpoint; the subagents run in
sequence autonomously.

**The journal completeness bar (testable):** *a fresh subagent, given only the
journal render + spec + its phase yaml, can implement the phase.* This is the
acceptance target for A+B together and a far stronger design constraint than
"survives compaction."

#### B.1 Serial execution in the shared workspace (decided)

All phases build **one branch → one PR**, so phase subagents run **strictly
serially in the plan's single fr-isolation workspace** — never parallel agents
in private worktrees. **Parallelism is explicitly out of scope: `fr apply
--to <runner>` (fr dispatch) is the mechanism for concurrent phase execution**,
and it already isolates each phase in its own Issue/branch/PR. The inline
fr-goal path stays serial by design.

Seriality removes the collision the org `agent-worktree-default` rule guards
against (parallel agents racing in the base tree), so phase subagents do **not**
get a fresh worktree each — they operate on the shared fr-isolation worktree,
which is *already* an isolated linked worktree. The one reconciliation the plan
must make: the enforcement hook (`agent-worktree-required.sh`) blocks
code-writing subagents that lack `isolation: "worktree"` regardless of
seriality, so the serial-phase dispatch needs an **explicit allowlist entry /
exception** recognizing "subagent operating inside an already-isolated fr
workspace" as a permitted shape. That hook change is the concrete B.1 task for
fr-plan; the *policy* (serial, shared workspace, no parallelism here) is
decided.

#### B.2 Per-phase model tiering

`fr-plan` annotates each `NN.yaml` phase header with a `tier` (e.g.
`mechanical` / `standard` / `hard`), judged from phase complexity at planning
time. **`tier` is harness-neutral metadata** — the plan never names a concrete
model. The `tier → model` binding is resolved at dispatch, per harness, from
config with a runtime fallback.

**Config surface (mirrors the existing `~/.config/fr/repos.yaml` pattern).**
The repo's `plan-config.yaml` is being *slimmed* (`plan_config.py` strips dead
keys), so the binding does **not** go there. Instead:

- **User-level `~/.config/fr/models.yaml`** — primary. Shape:
  `harness → tier → model` (e.g. `claude-code: {mechanical: claude-haiku-4-5,
  standard: claude-sonnet-5, hard: claude-opus-4-8}`). Sits beside
  `repos.yaml`/`secrets/` in the established fr user-config dir.
- **Repo-level override (optional)** — a dedicated small file if a repo needs to
  pin models (e.g. `docs/superpowers/models.yaml`); resolution order
  repo > user. Exact file left to fr-plan; *not* folded into the deprecating
  `plan-config.yaml`.

**Runtime fallback + persistence.** When no config resolves the active
harness's tiers, fr-goal's **batched Q&A (step 1) gains one question**: it
surfaces the models the *current harness* actually offers, the operator picks a
model per tier, and fr-goal offers to **persist** the choice (user or repo
scope). This keeps model selection inside the existing single-touchpoint Q&A —
no new gate — and means the operator only chooses once per harness, not once
per run. Per-dispatch override support: **Claude Code** confirmed (Agent
`model`); **OpenCode** likely (confirm before relying); **Hermes** unconfirmed
→ flat tier until its port spec verifies `delegate_task` model override.

`tier` degrades safely: a harness (or config) that can't bind per-phase models
runs every phase at one operator-chosen tier — cost optimization lost,
correctness intact.

### C. fr-debugging adopts the journal (component A, not B)

fr-debugging already writes a durable investigation log
(`fr-debugging/SKILL.md` step 3: symptom/repro, evidence, root cause, fix,
**rejected hypotheses**) and derives its PR body from it (step 4). This
upgrades that hand-written prose to the structured, continuously-flushed
`fr journal` primitive — **no component B** (debugging is one investigative
thread, not phase-decomposed; parallel/dispatched debugging is out of scope,
same as B.1).

Why debugging is a *strong* fit, not an afterthought: the **rejected-hypotheses
trail is the most compaction-vulnerable artifact in the suite** — it
accumulates across a long investigation and is written "at step 3", i.e.
potentially *after* a compaction already dropped it; losing it means
re-exploring ruled-out paths. Appending each hypothesis→verdict *as tested*
(`fr journal add --scope debug --kind hypothesis|ruled-out`) makes it
crash-safe.

- **SKILL.md changes:** step 3 records to `journals/debug/<debug-slug>.md` via
  `fr journal add --scope debug` **as the investigation proceeds** (repro on
  reproduce; each hypothesis + its verdict as tested; root-cause on
  confirmation; fix + verification at the end) — replacing the write-it-all-at-
  step-3 prose. Step 4's PR body uses `fr journal render --scope debug`.
- **Directory:** new debug journals live in `journals/debug/<debug-slug>.md`
  (uniform with spec/plan; archives to `implemented/journals/debug/`). **Existing
  `docs/superpowers/debugging/*.md` prose logs stay in place** as the
  historical archive of pre-journal investigations — no migration, no churn.
  `debugging/` is simply no longer the write target for new runs.
- **Crash-safety comes from continuous flush, not a hook:** because each
  hypothesis→verdict is appended as tested, the trail is durable on every
  harness with no PreCompact machinery — the same reason the dropped
  compaction-safety hooks were unnecessary applies here too.
- **Workspace reuse:** when fr-debugging reuses an active fr-goal workspace (a
  bug found mid-implementation, SKILL.md §0), the debug entries append to a
  `journals/debug/<debug-slug>.md` in that same worktree and ride the feature's PR —
  consistent with "the fix joins that branch/PR, no second PR".

## Non-goals

- **The Hermes Agent port** — its own future spec. This spec designs the core
  to the universal subset (subagents + journal CLI) so that port is mostly
  mechanical, and adds no Hermes-specific code beyond noting the gaps.
- **Parallel phase execution.** Phases are serial (one branch, one PR); any
  parallelism is a separate concern.
- **Triggering compaction programmatically / blocking auto-compaction.** Not
  supported / deadlock-prone; explicitly avoided.
- **Changing fr-goal's autonomy contract.** No new gate, no new mode; the
  batched Q&A stays the sole touchpoint.

## Testing & verification

- **Unit (`fr journal`):** add/render/check round-trip per scope; idempotency
  on `--id`; freshness heuristic true/false; malformed → `check` fails closed,
  `render` fails open; spec-scope vs plan-scope resolution.
- **Unit (`fr plan create`):** initializes the plan journal; a plan without one
  still parses (back-compat). `fr-plan` writes a `tier` per phase; parser
  accepts/defaults it.
- **Unit (archive):** `fr archive` moves `journals/plans/<plan-slug>.md` →
  `implemented/journals/plans/`; spec journal follows a fully-implemented spec
  into `implemented/journals/specs/`.
- **Integration (journal completeness bar):** a subagent-shaped harness given
  only `fr journal render` + spec + phase yaml has every input it needs
  (assert the render contains each decision + open finding); a dropped finding
  is caught by `fr journal check`.
- **Integration (PR body derived):** a scripted create→add→render sequence
  yields a PR-body block containing every finding + resolution; nothing
  finding-related is composed from memory.
- **Tiering:** `tier`→model mapping honored on the Claude path; flat fallback
  asserted for a harness without per-dispatch override. Config resolution order
  (repo > user > runtime prompt) unit-tested; persistence writes valid
  `~/.config/fr/models.yaml`.
- **Component C (fr-debugging):** debug-scope round-trip (repro/hypothesis/
  ruled-out/root-cause add→render→check); the fr-debugging PR body is produced
  by `fr journal render --scope debug`; existing `debugging/*.md` prose is left
  untouched (no migration path invoked).
- **Version bump:** skill + CLI → **minor** (new `fr journal` subcommand, new
  mandatory execution behavior, new phase `tier` field, fr-debugging record
  format change). Confirmed minor by the operator.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-07-22-fr-goal-subagent-execution | `derio-net/super-fr` | `2026-07-22-fr-goal-subagent-execution` | — |

## References

- `plugins/super-fr/skills/fr-goal/SKILL.md` — steps 1/2/4/6/7/8; line 86
  (no-subagents rationale this spec inverts).
- `plugins/super-fr/skills/fr-debugging/SKILL.md` — steps 3/4 (durable log +
  derived PR body) that component C upgrades to the journal.
- `packages/fr/src/fr/plan_config.py`, `packages/fr/src/fr/repos.py` — the
  slimmed repo `plan-config.yaml` (why the model config avoids it) and the
  `~/.config/fr/repos.yaml` user-config pattern the model config mirrors.
- `packages/fr/src/fr/commands/pickup_cmd.py` — the dispatched-flow phase-brief
  primitive the subagent handoff reuses inline.
- `packages/fr/src/fr/plan_ops.py:183-187` — plan-folder member creation
  (journal init mirrors this).
- `packages/fr/src/fr/archive.py` — plan/spec archival the `journals/` mirror
  follows.
- `~/.claude/rules/agent-worktree-default.md` — the parallel-worktree rule
  §B.1 must reconcile for serial shared-workspace phase subagents.
- Harness capability research (2026-07-22): Claude Code / OpenCode / Hermes
  Agent **subagents** (universal — the mechanism this spec builds on) and
  per-dispatch **model** override (Claude confirmed, OpenCode likely, Hermes
  unconfirmed). Compaction-hook findings recorded but **not used** — the design
  is deliberately hook-free (see Design §"Why no compaction-safety hooks").
