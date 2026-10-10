# Pocock workflows — Matt Pocock's skills as fr-tracked workflow shapes

**Date:** 2026-10-10
**Status:** Draft (brainstorm output, awaiting spec review)
**Target repo:** derio-net/super-fr (packages: `fr`; plugin: `super-fr`)
**Upstream:** [mattpocock/skills](https://github.com/mattpocock/skills) (MIT),
Claude Code plugin `mattpocock-skills`, read at commit `49dd158` (v1.3.1).

## Background

super-fr already wraps a third-party skill pack: **superpowers**. That pack is
a declared prerequisite (README "Requirements"). The operator installs it from
its own marketplace and it updates itself. `scripts/install.sh` never installs
it, and super-fr keeps no copy of its text. fr's skills and shipped manifests
name superpowers skills directly (`superpowers:requesting-code-review` in
`fr-goal.yaml`'s `review-phase`).

Matt Pocock's pack follows a different process. Its **main flow** is
`grill-with-docs` → `to-spec` → `to-tickets` → `implement` per ticket (each
driving `tdd` and closing with `code-review`) → `pr` → `retro`. Its bug
**on-ramp** is `diagnosing-bugs` → fix with a regression test → `retro`. The
skill `ask-matt` defines both flows.

The goal is to run those flows as **new fr workflows**. They keep Matt's
process and Matt's operator checkpoints, but run on fr's cursor, isolation,
artifacts and gates. They are not fr-goal shapes: fr-goal's contract (one
question round, unattended to PR, `fr-spec-reviewer`, `fr-phase-executor`)
would override Matt's gates.

Three facts about the upstream pack shape the design:

1. **Matt's orchestrating skills cannot be invoked by an agent.** They carry
   `disable-model-invocation: true`: `grill-with-docs`, `to-spec`,
   `to-tickets`, `implement`, `implement-spec`, `retro`, `triage`,
   `wayfinder` and `setup-matt-pocock-skills`. A manifest step that names one
   cannot be loaded through the harness's skill tool. The agent must read the
   installed `SKILL.md`. The building-block skills (`tdd`, `code-review`,
   `pr`, `diagnosing-bugs`, `codebase-design`, `domain-modeling`, `grilling`)
   are model-invocable.
2. **Matt's artifacts live on an issue tracker.** `to-spec` publishes the spec
   as an issue. `to-tickets` writes tickets to `.scratch/<feature>/issues/` or
   to tracker issues with native blocking links. fr's gates read
   `docs/superpowers/specs/*.md` and a plan folder.
3. **Tickets already have the shape of fr phases.** A ticket is a vertical
   slice with **blocking edges**. An fr phase has `depends_on`
   (`fr/types.py` `PhaseHeader`). The cursor already iterates phases
   (`for_each: phase`).

`fr run start <shape>` / `advance` / `resolve` already drive any manifest. No
**skill** exists today that drives an arbitrary shape without fr-goal's
contract: `/fr-goal <shape>` takes a shape name, but its prose belongs to
fr-goal.

## Requirements

R1. super-fr ships two new workflow shapes. `pocock` follows Matt's main flow
and `pocock-bugs` follows his diagnosing-bugs flow. Both pass
`fr workflow check`.

R2. Matt's skills are a prerequisite, installed and updated by the operator,
like superpowers. super-fr vendors none of his text. `scripts/install.sh` does
not install his plugin. The README lists him as a requirement for these two
workflows only.

R3. `fr` can resolve an installed skill named `<plugin>:<skill>` to its
`SKILL.md` path on the current harness, and say whether an agent may invoke
it. When the plugin or skill is absent, the resolution fails and names the
install command.

R4. Every step whose skill cannot be invoked by an agent tells the agent, in
its brief, to read that skill's resolved `SKILL.md` and follow it. Every
invocable skill is invoked by name as it is today.

R5. Both shapes start with a preflight that refuses to begin when any skill
the shape names cannot be resolved, or when the repo lacks
`setup-matt-pocock-skills`' outputs (`docs/agents/issue-tracker.md`,
`docs/agents/domain.md`). The refusal names the remedy.

R6. Matt's operator checkpoints become fr operator gates. In `pocock`, the
gated steps are the grilling, the spec (Matt's seam check) and the tickets
(Matt's breakdown quiz). In `pocock-bugs`, the gated step is the diagnosis
(Matt's "no feedback loop, ask the user" stop). `retro` is gated in both,
because Matt has it present its candidates to the operator. No other step
stops for the operator.

R7. The spec `to-spec` produces is an fr spec file under
`docs/superpowers/specs/`. It uses Matt's spec template with a
`## Requirements` section prepended (one `R<n>.` per user story or group of
stories). It is not published to the tracker.

R8. The tickets `to-tickets` produces are an fr plan folder: one phase per
ticket, each phase's body in Matt's local-ticket template, its blocking edges
as `depends_on`. They are not written to `.scratch/` or to the tracker.

R9. In `pocock`, each ticket is implemented as its own unit in a fresh
context, following Matt's `implement` (driving `tdd`, closing with
`code-review`). Its `code-review` result is journaled against that phase. fr
refuses to finish a ticket while a finding against it is open.

R10. Before the PR, fr refuses to continue while any completed ticket lacks a
review entry, or while any review finding is open. This is the same rule
`journal-check` enforces for fr-goal.

R11. In `pocock-bugs`, the fix is reviewed with Matt's `code-review`, and fr
refuses to open the PR while a finding from that review is open in the run's
debug journal.

R12. Both shapes open their PR with a body shaped by Matt's `pr` skill. Before
the PR, the orchestrator runs the full test suite and records its log as
evidence.

R13. A new generic driver skill, `fr-flow`, runs any workflow shape from fr's
briefs. It covers isolation, start, brief, step record, resolve and gates, and
adds no process of its own.

R14. Two named skills, `fr-pocock` and `fr-pocock-bugs`, start `fr-flow` on
their shape. Each carries only the flow-specific redirections that R7 and R8
require (write fr files instead of publishing to the tracker).

R15. Every run executes inside an fr-isolation workspace, as every fr run
does.

## Design

### A. Skill resolution — `fr skills resolve`

`fr skills resolve <plugin>:<skill> [...] [--json]` prints, for each name, the
installed `SKILL.md` path and `invocable: true|false`. `invocable` is the
negation of the frontmatter's `disable-model-invocation`. The verb sits under
the existing `fr skills` group, which is read-only and already in
`READ_ONLY_COMMANDS`.

Resolution order, per harness:

- **Claude Code:** `~/.claude/plugins/installed_plugins.json` →
  `<plugin>@<marketplace>`'s `installPath`. Then that plugin's
  `.claude-plugin/plugin.json` `skills` list (or `skills/*/` when the list is
  absent). The skill directory whose basename is `<skill>` holds `SKILL.md`.
- **OpenCode / Hermes:** the harness's skill directories that `npx skills add`
  installs into, matched by skill name. The plugin prefix is checked against
  the skill's provenance where the installer records it, and ignored
  otherwise.

When a name does not resolve, the command exits 2. Its message names the
install command for the harness it ran on (Claude Code:
`claude plugin install mattpocock-skills@claude-plugins-official`). The
resolver is a pure function over a filesystem root, so tests run it against a
stub install.

### B. Brief carries the resolution

A dispatch brief for an `agent` step already carries the step's `skill` (one
or a list). It gains a `skill_sources` list: `{name, path, invocable}` for
each named skill, resolved per §A when the brief is built. A `skill_sources`
entry with `invocable: false` means: **read `path` and follow it as the
step's discipline**. An unresolvable skill fails the advance with §A's
message. No manifest field is added. Briefs are not an artifact kind, so no
stamp moves.

### C. The `pocock` shape

`plugins/super-fr/workflows/pocock.yaml`, `unit: run`,
`requires: [git, tests, scm]`, `verification: candidate`:

| id | kind | skill | gate | emits / needs | evidence |
|---|---|---|---|---|---|
| `preflight` | cli | — | — | — | — (`run: fr skills resolve … --require-setup`) |
| `grill` | agent | `mattpocock-skills:grill-with-docs` | operator | emits `journal:spec` | — |
| `spec` | agent | `mattpocock-skills:to-spec` | operator | emits `spec`, `journal:spec` | — |
| `tickets` | agent | `mattpocock-skills:to-tickets` | operator | needs `spec`; emits `plan` | — |
| `implement` | agent | — | — | `for_each: phase`; needs `spec`, `plan` | — |
| ↳ `implement-ticket` | agent | `mattpocock-skills:implement` | — | emits `journal:plan`, `plan:ticks` | `review`, `findings` |
| `journal-check` | cli | — | — | needs `plan`, `journal:plan` | — (`fr journal check --scope plan … --require-reviews`) |
| `pr` | agent | `mattpocock-skills:pr` | — | needs `spec`, `plan`; emits `pr` | `tests` |
| `retro` | agent | `mattpocock-skills:retro` | operator | — | — |

- `grill` and `spec` run **inline in the orchestrator**. Matt's context
  hygiene wants grilling, spec and tickets in one unbroken window.
  `implement-ticket` runs in a **fresh subagent** per ticket, Matt's `/clear`
  between tickets. That subagent is a general one given the brief, not
  `fr-phase-executor`, whose discipline is fr-execute's.
- `implement-ticket` has one member, because Matt's `implement` ends in
  `code-review` itself. fr verifies its outcome: `review` (a `kind=review`
  plan-journal entry naming the phase) and the derived `findings` (refused
  while one is open), with the same verifiers `review-phase` uses. `reviewer`
  is not required, since the reviewers are `code-review`'s own subagents, not
  a dispatch the orchestrator makes.
- There is no `plan-review` (`fr plan self-review`). Its checks (TDD-shaped
  steps, acceptance links) are fr-plan's conventions, which Matt's tickets
  don't follow. `fr validate artifacts` still checks the plan's structure.
- The shape emits no `acceptance` rows. Matt's process has no acceptance
  matrix (see Non-goals).

### D. The `pocock-bugs` shape

`plugins/super-fr/workflows/pocock-bugs.yaml`, `unit: run`:

| id | kind | skill | gate | emits | evidence |
|---|---|---|---|---|---|
| `preflight` | cli | — | — | — | — |
| `diagnose` | agent | `mattpocock-skills:diagnosing-bugs` | operator | `journal:debug` | — |
| `review` | agent | `mattpocock-skills:code-review` | — | `journal:debug` | — |
| `journal-check` | cli | — | — | — | — (`fr journal check --scope debug --slug …`) |
| `pr` | agent | `mattpocock-skills:pr` | — | `pr` | `tests` |
| `retro` | agent | `mattpocock-skills:retro` | operator | — | — |

`diagnose` covers Matt's six phases, from feedback loop through cleanup. The
fix and its regression test land in this step. `review`'s findings go to the
debug journal, and `journal-check` refuses the PR while one is open. If the
manifest template has no variable for a run's debug-journal slug, the plan
adds one. The requirement (R11) stands either way.

### E. The driver — `fr-flow`, `fr-pocock`, `fr-pocock-bugs`

`plugins/super-fr/skills/fr-flow/SKILL.md` is the generic driver:

1. `fr run start <shape> --branch <b>`, which enters isolation itself.
2. Loop: read the brief. On a `gate: operator` step, do the step's work with
   the operator and then resolve. For each `skill_sources` entry, invoke it,
   or read its path when `invocable: false`. A step with `for_each` dispatches
   one fresh subagent per unit. Fill the step record and resolve with
   `--record`, which prints the next brief.
3. Stop only at an operator gate, a refusal it cannot fix, or the finished
   run.

It states no process of its own: no question budget, no autonomy contract, no
review discipline. Those come from the shape's skills.

`fr-pocock` and `fr-pocock-bugs` each say "run `fr-flow` with shape `pocock`
(or `pocock-bugs`)" and list the redirections:

- Where Matt's skill says to publish the spec to the tracker, write the fr
  spec file instead (R7).
- Where it says to write tickets to `.scratch/` or the tracker, create the
  plan folder (`fr plan create`, one phase per ticket, `depends_on` from the
  blocking edges) (R8).
- Where it says to commit or close tickets on the tracker, tick the phase
  instead.

All three skills are canonical sources under `plugins/super-fr/skills/`, so
the OpenCode and Hermes mirrors, install wiring and tool-neutrality scan
apply as for every skill.

### F. Prerequisite wiring

The README gains a line under "Requirements": `mattpocock-skills` is needed
only for the `pocock` / `pocock-bugs` workflows, with its install command per
harness. `fr skills` (the overview) lists the three new skills.

## Non-goals

- Matt's other flows: `triage`, `wayfinder`, `implement-spec` (parallel
  frontier), `improve-codebase-architecture`. They are candidates for later
  shapes reusing §A/§B.
- Publishing the spec or tickets to the tracker as a mirror. fr files are the
  only record.
- Vendoring, pinning or auto-installing Matt's plugin. His updates flow in
  unreviewed, breaking ones included. The preflight catches a missing skill,
  not a changed one.
- Acceptance-matrix rows for runs of these shapes.
- Changing fr-goal, fr-goal-light or their skills.

## Verification

strategy: candidate
- pocock-shapes-valid: candidate
- pocock-skill-resolution: candidate
- pocock-preflight-refusal: candidate
- pocock-brief-skill-sources: candidate
- pocock-run-walk: candidate
- pocock-live-flow: live — only a real session with Matt's plugin installed,
  an operator answering the gates and a real PR shows the whole flow. A stub
  install can prove the wiring, not that Matt's prose and fr's redirections
  compose.

Candidate rows install the branch's build via `.fr/candidate-install` and run
scenarios against a **stub** `mattpocock-skills` install under a temporary
`$HOME`: a minimal `installed_plugins.json` plus `SKILL.md` files with the real
frontmatter flags.

## Test Plan

- post-merge — operator-driven: after release, in a repo with
  `mattpocock-skills` installed and `/setup-matt-pocock-skills` run, start
  `/fr-pocock` on a small feature. Answer the three gates and confirm the
  following, recording the redacted evidence on `pocock-live-flow`:
  - the spec lands as an fr spec file;
  - the tickets land as plan phases with `depends_on`;
  - each ticket runs in a fresh subagent with its `code-review` journaled;
  - `journal-check` gates the PR;
  - the PR body follows Matt's `pr` shape.
