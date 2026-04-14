# Archive-on-Complete and Unified Work-Item Descriptions

**Status:** Draft
**Date:** 2026-04-14
**Repos affected:** `derio-net/superpowers-for-vk`, `derio-net/secure-agent-kali`, all `derio-net/*` consumer repos (operational migration)

## Goal

Two related improvements to the VK work lifecycle:

**A. Archive-on-Complete.** Extend `vk progress sync` so that when a plan transitions to `Complete`, it interactively offers to move the plan file from `docs/superpowers/plans/` to `docs/superpowers/archived-plans/`. Stops completed plans from piling up alongside active ones.

**B. Unified work-item descriptions.** Today, a single piece of work is represented with different text on at least five surfaces (plan file, GitHub Issue title/body, VK workspace prompt, GitHub PR). Operators and agents lose track of which Issue goes with which plan in which repo. This design introduces one canonical tracking block that appears on every surface, a human-readable title format, and structured labels.

## Non-goals

- Changing the plan file format or phase syntax.
- Migrating **closed** Issues — they are frozen history.
- Replacing the VK Issue Bridge or its contract (bodies continue to expose `## Instruction` / `## Workspace` / `## Dependencies`).
- Building a repo-walking bulk migration command. Per-plan `vk dispatch migrate` plus a shell loop is enough for v1.

## Cross-cutting principle: fail loud, fail actionable

Silent degradation caused the Frank hextra dispatch incident (phases 3–5 consumed workspace slots while phases 1–2 remained queued, because the dispatch body's `Blocked by #N` was unparseable by the bridge's regex, which expects `- Blocked by #N`). The bridge silently treated every phase as unblocked.

Going forward, every parse/validate/execute step fails hard with an actionable message. No `except Exception: pass`, no fail-open fallbacks that mask bugs.

## Design

### 1. Canonical tracking block

Rendered identically in Issue body, VK workspace starting prompt, and PR body.

```
📦 Repo:   {owner}/{repo}
📋 Plan:   {plan_path_relative_to_repo_root}
📐 Spec:   {spec_path_from_plan_header}
🎯 Phase:  {n}/{total} — {phase_title} [{tag}]
🔗 Issue:  {issue_url}

**Goal (from plan):** {plan.goal_paragraph_verbatim}
```

`{total}` = `len(plan.phases)`. Goal is taken verbatim from the plan's `**Goal:**` header paragraph.

### 2. Title format

Issue title and PR title:

```
[{owner}/{repo}] {slug} · Phase {n}/{total} · {phase_title}
```

Example: `[derio-net/frank] blog-hextra-migration · Phase 2/5 · Content Migration`.

Slug is derived by the existing `derive_slug()` from the plan filename.

### 3. Structured labels

Added on Issue create (and on migrate) so parsers have a stable surface despite human-readable titles:

- `plan:{slug}` — e.g. `plan:blog-hextra-migration`
- `phase:{n}` — e.g. `phase:2`
- Existing `vk-ready` / `manual` labels preserved.

Label lifecycle on an Issue over time:

| Event | Labels added | Labels removed |
|---|---|---|
| `vk dispatch` creates Issue | `vk-ready` / `manual`, `plan:<slug>`, `phase:<n>` | — |
| Agent starts work (`vk-execute`) | `in-progress` | `vk-ready` |
| Agent pushes first PR | `pr-ready` | `in-progress` |
| PR merged / Issue closed | (GitHub sets state) | `pr-ready` |

Label strings are configurable under `dispatch.labels` in `plan-config.yaml`.

### 4. Dependency format

Dispatch emits dash-prefixed list items that match the bridge's existing regex:

```
## Dependencies

- Blocked by #{prev_num}
```

This single change activates the bridge's dependency-aware deferral that is already implemented at `secure-agent-kali/scripts/vk-issue-bridge.py::parse_dependencies` and `::check_blockers`.

Phase 0 phases (no dependencies) emit:

```
## Dependencies

None — no blocking phases.
```

### 5. Archive-on-Complete

Location: `src/vk/commands/progress_cmd.py::sync`, after `_rewrite_status` writes `Status = Complete`.

Flow:

1. Compute new status from checkboxes (unchanged).
2. If new status is `Complete` AND the plan file lives in `profile.plan.save_to`:
   - **Interactive (default):** prompt `"Plan is Complete. Archive to docs/superpowers/archived-plans/? [y/N]"`. Default No.
   - **`--yes`:** archive automatically without prompt.
   - **`--dry-run`:** print `"Would archive: <src> -> <dest>"`.
3. Archive action:
   - Destination: `<repo_root>/<profile.plan.archive_to>/<basename>` (default `docs/superpowers/archived-plans/`).
   - If destination exists → refuse (do not overwrite).
   - `git mv` the file to preserve history. On non-git or failure, fall back to `shutil.move` + `git add`.
   - Commit: `chore(plan): archive <slug> on completion`.
4. Update the spec index row's `file:` column to the archived path.
5. On any failure: leave `Status = Complete` written, emit the git error verbatim. User re-runs or archives manually.

Config key added to `plan-config.yaml` (optional):

```yaml
plan:
  archive_to: docs/superpowers/archived-plans/
```

### 6. Retroactive migration

New command: `vk dispatch migrate <plan-path> [--dry-run | --yes]`.

Behavior:

1. Parse the plan; collect `<!-- Tracking: URL -->` comments per phase.
2. **Fail if any phase lacks a tracking comment** (run `vk dispatch <plan>` first).
3. For each tracked Issue: `gh issue view`. Failure → abort with repo/number.
4. Closed Issues: skip with a log line (not an error).
5. Compute new title, body, labels.
6. Run the body validator; abort if it fails.
7. Dry-run prints a full diff per Issue. `--yes` applies via `gh issue edit --title ... --body ... --add-label ...`.
8. Any `gh` failure mid-run → abort immediately. Partial state is worse than stopping.
9. Emit summary and non-zero exit on any failure.

### 7. Fail-loud audit: existing quiet fallbacks to remove

| Location | Current | New |
|---|---|---|
| `vk-issue-bridge.py::check_blockers` L216–218 | `gh issue view` failure → treat blocker as resolved | Raise; log `"Blocker #{n} unreachable — cannot gate safely. Fix: check gh auth or network."` Bridge exits non-zero for that Issue. |
| `vk-issue-bridge.py::parse_dependencies` silent `[]` | No `## Dependencies` → no gating | If `phase_number > 0` and no parseable deps → fail ingest: `"Issue #{n} is phase {p} but has no parseable '- Blocked by #N' line. Fix: run 'vk dispatch migrate <plan>' or re-dispatch."` |
| `vk dispatch::_build_issue_body` | — (new) | Validate generated body before `gh create`. Must contain `## Instruction`, `## Workspace`, `## Dependencies`, and (if phase>0) `- Blocked by #N`. On failure, abort with the specific missing section. |
| `dispatch_cmd.py::L282–296` | Bare `except Exception: pass` around git commit | Remove; propagate with git error verbatim. |

### 8. Agent-side blocker guardrail

Defense-in-depth for the case where the bridge misfires or a human manually labels a blocked Issue `vk-ready`. The bridge, not the Issue body, carries this instruction — it's imperative to the agent at spawn time, and the Issue body stays clean as the durable record.

Change to `secure-agent-kali/scripts/vk-issue-bridge.py::build_prompt`: when `parse_dependencies` returns any entries, prepend a preamble:

```
BEFORE YOU BEGIN: This Issue declares dependencies: {dep_refs}.
Verify each is CLOSED via `gh issue view <n> --repo <owner/repo> --json state`.
If any is OPEN:
  - STOP. Do not start work.
  - Do not duplicate the upstream work.
  - Do not start 'parts that don't depend on it'.
  - Exit with message: 'Blocked on {open_blocker}, not starting.'
The bridge should have deferred this workspace if the blocker were open —
if you see this and blockers are open, report it to the operator.
```

### 9. Multi-repo scope

#### `derio-net/superpowers-for-vk` (this repo)

- `src/vk/commands/progress_cmd.py` — archive-on-Complete.
- `src/vk/commands/dispatch_cmd.py` — new title builder, tracking block, labels, dash-prefixed deps, body validator, remove quiet git-commit swallow, add `migrate` subcommand.
- `src/vk/plan/parser.py` — verify Goal extraction captures full paragraph.
- `src/vk/config.py` — add optional `plan.archive_to`, `dispatch.labels.in_progress/pr_ready`.
- `skills/vk-execute/SKILL.md` — PR title format, paste tracking block into PR body, `pr-ready` label swap after PR push.
- `skills/vk-dispatch/SKILL.md` — document `migrate` and new title shape.
- `skills/vk-progress/SKILL.md` — document archive-on-Complete.
- `tests/` — unit + integration tests (Section 11).

#### `derio-net/secure-agent-kali`

- `scripts/vk-issue-bridge.py` — `check_blockers` fail-loud, `parse_dependencies` fail-loud when phase>0 has no deps, `build_prompt` blocker preamble.
- Tests for above.

#### `derio-net/frank` and other consumer repos

No code change. Operational step: run `vk dispatch migrate <plan>` against each plan with open phases after the CLI ships. First target: Frank's `2026-04-13--repo--blog-hextra-migration.md` (currently stuck).

### 10. Rollout

1. **Phase 0 — Impact audit.** Report committed to `docs/superpowers/`. Checks:
   - Grep all three repos plus `willikins` and `vibe-kanban` for consumers of `{slug}-{phase}-{tag}` title regex, Issue title parsers, `vk-ready`/`vk-synced` label consumers.
   - Enumerate open Issues with old title format across `derio-net/*`.
   - Confirm `vk-issue-bridge.py` is the only bridge instance.
   - Confirm `willikins/scripts/hooks/vk-lifecycle-transition.sh` doesn't parse Issue titles.
   - Verify PR-body format constraints from any review tooling.
2. **Phase 1 — superpowers-for-vk dispatch changes.** Title builder, tracking block, labels, dash-prefixed deps, body validator, unit tests. Gated behind existing `dispatch_enabled`.
3. **Phase 2 — superpowers-for-vk archive + migrate.** Archive-on-Complete, `vk dispatch migrate`, their tests.
4. **Phase 3 — secure-agent-kali bridge hardening.** Fail-loud changes, blocker preamble, tests. Deploy.
5. **Phase 4 — Operational migration.** Run `vk dispatch migrate` for open plans, starting with Frank hextra. Confirm bridge log shows correct `deferred` lines for blocked phases.
6. **Phase 5 — Docs.** Update skill SKILL.md files, runbooks, operator announcement.

**Order rationale:** Phase 1 before Phase 3 is safe because dispatch's new dash-prefixed deps are already parseable by the bridge's *existing* regex. There is no window where the bridge expects a new format that dispatch hasn't produced.

Each phase is independently revertable. If Phase 3 causes starvation or false failures, revert and bridge resumes current behavior while dispatch keeps producing the correct format.

### 11. Testing

**Unit (superpowers-for-vk):**

- `_build_issue_title` — new format with slug/phase/total/title interpolation.
- `_build_issue_body` — tracking block shape, Goal paragraph, dash-prefixed deps conditional on phase>0.
- Body validator — rejects missing sections and wrong dep format.
- Archive — git mv path, destination-collision refusal, dry-run preview, spec-index row update.
- Migrate builder — diff computation, closed-Issue skip, label additions.

**Integration (superpowers-for-vk):**

- End-to-end archive: create plan, sync to Complete, confirm prompt, assert file moved and commit made.
- End-to-end dispatch with mocked `gh`: assert Issue create call has new title, labels, body sections in order.
- End-to-end migrate with mocked `gh issue view`/`edit`: assert correct rewrite.

**Unit (secure-agent-kali):**

- `parse_dependencies` — fail-loud when phase>0 body has no deps.
- `check_blockers` — raises on `gh` errors.
- `build_prompt` — preamble present when deps present, absent when not, references correct blockers.

## Open questions

None at spec time. Phase 0 audit will surface any additional title/label consumers.
