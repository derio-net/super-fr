---
name: fr-plan
description: >
  Write phase-structured plans with operator collaboration. Use when:
  "write a plan", "fr plan", "create a plan". Invoked by brainstorming handoff.
---

# fr-plan

Produce implementation plans through collaborative dialogue; conversational
parts stay here, mechanical parts delegate to the `fr plan` CLI. **Announce at
start:** "I'm using fr-plan to create the implementation plan."

## Format (v2 plan-as-folder)

A plan is a directory under `docs/superpowers/plans/<slug>/` containing:

- `_meta.yaml` — schema_version, plan slug, spec ref, target_repo, vk_version,
  created date, optional rework metadata (`parent_plan`, `prior_rework`,
  `origin_items`).
  - **`spec` ref notation:** a same-repo spec is the bare filename (`<file>.md`;
    `fr plan create --spec` shortens a full path, as `fr repair` does); a spec
    in **another repo** MUST use the cross-repo form `<owner>/<repo>:<path-in-that-repo>` (e.g.
    `derio-net/frank:docs/superpowers/specs/<file>.md`). Without the
    `owner/repo:` prefix, `fr apply`'s reachability gate reads it as a missing
    same-repo file and refuses to dispatch. `fr plan self-review` warns when a
    same-repo-form spec doesn't resolve locally (#248).
- `_prose.md` — the human-readable narrative. Tooling never parses this; it's
  for humans (and the implementing agent).
- `NN.yaml` (one per phase, two-digit zero-padded: `01.yaml` … `99.yaml`) —
  phase header, tasks, steps, per-step state. Per-phase files prevent merge
  conflicts when parallel branches tick different phases. Phases number **from
  1**; `00.yaml` fails parse — `fr plan create` rejects it pre-flight.

Every step id follows `P<n>.T<n>.S<n>` (phase number, task number, step
number). The renderer / observer / diff / apply chain depends on this shape.

## Procedure

1. Read context (recent commits, existing plans, spec file).
2. Confirm scope. Decompose if too large.
3. Propose 2-3 approaches with tradeoffs. Recommend one.
4. Present plan structure section by section, get approval.
5. Scaffold the plan folder:
   ```bash
   fr plan create --slug <YYYY-MM-DD-slug> --target-repo <owner/repo> \
       --spec docs/superpowers/specs/<spec-file>.md \
       --phases-file "$TMPDIR/<slug>-phases.yaml" \
       --prose-file "$TMPDIR/<slug>-prose.md"
   ```
   Both inputs are scratch: write them to `$TMPDIR`, **never inside the repository** — drafts in the plan folder get committed and hold up `fr archive`, and every file under `docs/superpowers/runs/<run>.records/` is read as a step record, so a phase list there makes every `fr` command refuse.
   `fr plan create` ALSO appends a row to the spec's `## Implementation Plans`
   table — there is no separate spec-index step.
6. Iterate on the prose / per-phase yaml via the Edit tool.
7. Run self-review: `fr plan self-review <plan-dir>`.
8. Hand off for execution:
   - `fr apply <plan-dir>` — render → observe → diff → preview (default
     dry-run). Add `--yes` to actually create / update GitHub Issues.
   - The implementing agent uses `fr pickup <plan-dir> --phase N` to receive
     the phase scope as markdown.

## Rules

- TDD (`superpowers:test-driven-development`): red → green → refactor — or a refactor reason, a
  **step-record field** (`refactor: {P<n>.T<m>: "<why>"}`; a `no-refactor-because:` journal entry counts too).
- **Refactor step shape:** trailing `P<n>.T<n>.S3` after red→green for small cleanups, a separate
  `REFACTOR + quality gate` **task** for larger ones. Omit only with a reason; the phase's `fr run
  resolve` enforces it (single-step tasks, manual phases exempt), not self-review — at plan time it's a guess.
- **Size phases to the asks:** one agentic phase per independently reviewable ask — usually one per group of the spec's requirements, never one per acceptance row. Every phase costs a fixed round trip (an executor, a reviewer, the orchestrator's resolve turns) that does not shrink with its size (#745; `fr run cost` shows it per step), so a one-agentic-phase plan is first-class and usually right. Every phase after the first records a `phase-split-<plan>-p<N>` spec-journal decision (`fr journal add --scope spec --slug <spec-journal-slug> --kind decision --id phase-split-<plan>-p<N> --title "<reason>: …"`, the slug being the spec file's stem without `-design`, as `fr journal` uses it; a later decision for the same phase supersedes it as `phase-split-<plan>-p<N>-<k>`, highest `k` wins): `ask:` when it serves an ask of its own, otherwise `tier:` (needs another tier), `risk-first:` (a risky piece lands before the rest) or `review-size:` (the diff is too large for one review). With a Requirements list in the spec, `fr plan self-review` errors on an agentic phase whose rows cite no requirement of its own and on a later phase with no recorded reason. With two or more agentic phases, the skeleton is the first ask's phase, marked `skeleton: true`, with the smoke (CI green on a trivial test, fixtures captured never constructed) as its first task — never a phase of its own; self-review errors without the marker (override: `skeleton-override-*`).
- **Pure agentic phases:** an agentic phase must be fully agent-completable end-to-end. Collect ALL manual work (secrets, UI operations, deploy actions, cluster-dependent config) into a dedicated `[manual]` phase — never author a manual step into an agentic phase planning to defer it. `fr plan self-review` enforces this with error severity (#252). An operator *verification* step (a screenshot, a live check, a post-merge run) is a Test Plan line or a `verify: live` acceptance row, not a `[manual]` phase; keep `[manual]` phases for a prerequisite agentic work depends on or a real dispatch/deploy. Self-review warns on a single-step trailing manual phase.
- **Steps name outcomes, not mechanisms:** "gather file:line-cited evidence following
  `<protocol>`", never "dispatch `<agent>`". A step naming the actor or the tool rots *silently*
  the moment either changes — the phase executor is a leaf, not an orchestrator, so it does the
  nearest thing it can and ticks. Self-review errors on a dispatch verb in an agentic step
  (#428); real dispatch belongs in the TRAILING `[manual]` phase, never a mid-plan one (#496).
- **Acceptance linkage:** a phase that advances a matrix row carries `acceptance: [row-ids]` in its
  header. `fr plan self-review` errors when the spec has a Test Plan but zero linked rows (matrix
  present) and on unknown ids. Planning may ADD rows (`fr acceptance add`, origin = spec) when
  decomposition exposes a missed business acceptance — flagged as an addition, defended at PR time,
  never ironed over. The phase that builds the UI links the row carrying `visual` too, so fr-execute's browser check knows what to capture.
- **Tier:** every agentic phase declares `tier: mechanical | standard | hard` (`fr.types.PHASE_TIERS`;
  manual phases don't — never dispatched). fr-goal resolves it via `fr models resolve`; omit it and
  dispatch is untiered, inheriting the session model — self-review warns when missing.
  **`standard` is the default**; choose by the phase's hardest step, not its size — `mechanical`: rote, fully specified edits (renames, a message, a table row, a mirror sync); `standard`: ordinary feature or fix work against a clear spec, however many files; `hard`: a design judgement the spec leaves open, or a change to a gate, migration or concurrency path every caller relies on. `hard` sends the whole phase to the costliest model, so it needs a reason — `fr journal add --scope spec --slug <spec-journal-slug> --kind decision --id tier-<plan>-p<N> --title "<why>"` (a `tier:` phase-split decision for that phase counts); self-review errors without one.
  The phase also declares `files:` (repo-relative globs it will touch; `*` spans `/`) and `estimate_lines:` (added + deleted) — `fr plan proportionality` reports touches outside them and size above 2× at deliver; self-review warns on no `files`.
- No placeholders: every step has actual code, commands, expected output.
- Bite-sized steps: 2-5 minutes each, sized within the phase — a one-phase plan still keeps one or
  more steps per spec design section, never one step for a whole section.
- Use BEGIN/END markers for full-file embeds, not nested fences.
- **Cross-repo completeness:** If the spec lists multiple plans across repos, write ALL of them
  before offering the execution handoff. For each target repo: scaffold the plan in that repo's
  `docs/superpowers/plans/` directory. `fr plan create` updates the spec table automatically.

## Dependency declarations

Each per-phase yaml declares its blockers via `phase.depends_on: [N, ...]`
(integers): `[]` for a root phase, `[1, 2]` for fan-in. Deps are
backward-only — phase N may only reference phases < N — and cycles are caught
by `fr plan self-review`.

## Rework plans

After a parent plan ships, defer surfaced-but-unrealised items into a separate
rework plan — do not reopen the parent.

- `fr plan rework <parent-plan-dir>` scaffolds a sibling
  `<parent-slug>-rework-N/` folder, adds `parent_plan` (and `prior_rework` if
  N>1) to its `_meta.yaml`, and appends a row to the spec table.
- `fr plan rework-add <rework-dir> --item ... --source ... --track ...`
  appends an entry to `_meta.origin_items`. `--track` is free-form (canonical
  tokens `development`, `operations`, `decision`; compounds like
  `decision → development` accepted).
- `fr plan rework-list [--include-archived]` surfaces open reworks.

## Integration

Upstream: brainstorming hands off via fr-plan-override. Downstream:
`fr apply` for GitHub-side work; `executing-plans` for the agent loop.
