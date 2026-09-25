---
name: fr-execute
description: >
  Execute an agentic phase from a plan. Use when implementing
  assigned work from a plan file. Agent-facing skill.
---

# fr-execute

Implements a single phase from a plan. **Announce at start:** "I'm using
fr-execute to implement this phase."

## Mode selection

| Input | Mode |
|---|---|
| Issue URL/number (dispatch repo) | Dispatched: read assignment from Issue body — it embeds the spec link, plan `_prose.md`, and phase `NN.yaml` inline (repo checkout stays the source of truth) |
| (plan_dir, phase number) | Local: direct arguments |

## PR format (unified) — for an agentic phase's PR

- **Title:** `[{owner}/{repo}] {slug} · Phase {n}/{total} · {phase_title}` —
  matches the Issue title shape so VK / GH / PR surfaces align; the
  `fr pickup` output below is the canonical template.
- **Body:** first content block is the tracking block copied verbatim from
  the Issue body (the `📦 Repo:` / `📋 Plan:` / … lines plus the
  `**Goal (from plan):**` paragraph). Then proceed with your PR summary.

## Label lifecycle (no manual transition verbs in v2)

The Issue moves `fr:ready → fr:in-progress → fr:pr-ready → closed`; every flip
is derived from what the renderer observes on the Issue plus its linked PRs:

- **`fr:ready`:** a `tracking_issue`, no assignee, no open draft or non-draft PR.
- **`fr:in-progress`:** the Issue has an assignee OR a draft linked PR.
- **`fr:pr-ready`:** an open non-draft, non-merged linked PR exists.
- **closed:** `state.completion.at` set AND a merged PR observed AND no open
  linked PR remains (per `_phase_complete` in `render.py`).

`fr apply` at the end of the phase pushes whichever transitions the renderer
projects from current GitHub state. Assign yourself to the Issue (or open a
draft PR) for `fr:in-progress`; take the PR out of draft for `fr:pr-ready`.

## Procedure

1. **Get phase scope:**
   ```bash
   fr pickup <plan-dir> --phase N
   ```
   Markdown: title, `Depends on:` (not yet `Complete` → stop, report), tasks + steps, `_prose.md`. In
   an fr-goal run it ends with a `## Step record`: keep THAT (ticks, `refactor:`, journal) instead of
   steps 3–4's verbs — the orchestrator's `fr run resolve --record` applies it in one commit.

2. **Implement** (`superpowers:executing-plans`, parallel phases: `subagent-driven-development`):
   end every task red → green → refactor or record `no-refactor-because: P<n>.T<m>` in the journal — `fr journal add --scope plan` requires `--phase N` or `--global`, so tag it explicitly; `--complete-phase` refuses a phase with a task that has neither. **Context discipline:** don't re-derive from the code what the handoff already states, read the narrowest thing that answers the question, and never paste verbatim tool output into your return — cache reads accumulate as context size summed over turns, so your own re-reads dominate the cost (super-fr#464).

3. **Tick steps as you complete them:**
   ```bash
   fr plan edit <plan-dir> --tick P<n>.T<n>.S<n> --state x
   # or, to record a deliberate skip:
   fr plan edit <plan-dir> --tick P<n>.T<n>.S<n> --state - --note "<reason>"
   ```

   **Harness — dispatch:** the executor is a leaf everywhere — Claude Code
   grants it **no `Agent` tool**, OpenCode's agent sets `task: deny`, and on
   Hermes only this contract stops a further `delegate_task`. A tick claims
   performance, so a step telling you to dispatch, delegate to, spawn or hand
   off to a subagent is a **BLOCKER**, not a deviation and not a `--state -`
   skip: report it, leave the step **unticked**, and do not complete the
   phase. Never do that work inline instead: the dispatch existed to put it in
   a context blind to this one, so doing it here destroys that (#428).

4. **Mark the phase complete (after every step is ticked):**
   ```bash
   fr plan edit <plan-dir> --complete-phase N
   # manual phases require --note describing what was done
   fr plan edit <plan-dir> --complete-phase N --note "<runbook ref>"
   ```
   A phase carrying `acceptance: [row-ids]` — flip those matrix rows now
   (`not-implemented` → `skipped`/`ci`), citing the test refs; the CLI warns
   on unflipped rows (see `fr-acceptance`). Discovered edges may ADD rows
   (`fr acceptance add`) — defended at PR time, never silent scope drift.

5. **Open the PR** via `superpowers:finishing-a-development-branch`, with the
   `fr pickup` title and the body shape above. **Caveat — under fr-goal LOCAL
   mode, do NOT open a per-phase PR:** push the branch only; the single PR is
   fr-goal's step 8, opened as a draft by the orchestrator *after* its review
   pass — opening here reorders deliver ahead of review and reintroduces the
   #320 merge-race. Per-phase PRs are the standalone **dispatched** (Issue/VK)
   flow only.

6. **Reconcile GitHub state:**
   ```bash
   fr apply <plan-dir>           # preview the projected mutations
   fr apply <plan-dir> --yes     # push label / state changes
   ```
   `fr apply` is idempotent and **safe before your PR merges** — the renderer
   needs BOTH `completion.at` AND a merged PR observed before projecting
   CLOSED, so this only sets `pr-ready`. Re-run after merge (or let the
   runner) to close.

## Constraints

- Don't touch other phases. One phase = one PR, except fr-goal LOCAL mode
  (step 5's caveat) — never open a per-phase PR there.
- Stop if blocked — report what's missing.
- A dispatch instruction is a BLOCKER, never a tick or a skip (step 3).
- Step IDs: `P<n>.T<n>.S<n>`.

## v1 plan migration

A `.md` plan file (not a folder) is a v1 plan; migrate before executing:

```bash
fr migrate v1-to-v2           # preview (default)
fr migrate v1-to-v2 --yes     # apply: creates <slug>/ folders, moves .md to .md.v1-archive
```

Migration is repo-wide (converts every v1 plan, rewrites spec tables); commit
as its own PR. "Legacy layout detected" → `fr migrate dirs --yes`.
