# fr status and fr archive: check the default branch before saying "merged"

- **Date:** 2026-09-23
- **Status:** designed
- **Origin:** gh#526 (canonical for #439), gh#544
- **Goal:** `fr status` calls a plan merged, and `fr archive` archives it, only
  when the plan is complete on `origin/<default>`. A plan that is only complete
  locally is reported as waiting for merge. Nothing suggests archiving it, and
  `fr archive` refuses it.

## 1. Problem

`fr status` with no argument sweeps `docs/superpowers/plans/` and prints:

```
archivable — merged but not archived (1):
  2026-09-20-agentic-dispatch-verb-lint

run `fr archive --all` to move 1 plan(s) to implemented/.
```

The list comes from `fr.archive.completed_unarchived_plans`. That function is
gh-free by design (#334): it counts a plan when every phase is locally complete
(`render.plan_locally_complete`). It never checks merge state. Its docstring
puts "merged-but-unarchived" in quotes because it knows the label is a guess.
`status_cmd._sweep_text` (`status_cmd.py:150`) prints that guess as fact and
then suggests acting on it.

**Every fr-goal run reaches this state before its PR exists.** fr-goal finishes
every phase and only then delivers. So the suggestion fires exactly when
following it would be wrong. #439 recorded a live case on 2026-08-15:
`2026-07-26-fr-goal-isolation-deadlocks` was reported merged while PR #422 was
still open.

#439 argued this was only a wording bug, because `archive_gate` would refuse
the real move. For fr-goal plans it does not refuse (#544). `archive_gate`'s
undispatched arm (`render.py:276`) passes any phase that is locally complete
and has no tracking issue. fr-goal plans never get a tracking issue. So
`fr archive --all` archives the unmerged plan the sweep just called merged.

Archiving is hard to undo. `docs/superpowers/implemented/` is frozen: no
locator reaches it, no migration rewrites it, and `fr validate artifacts` does
not check it (`.claude/rules/artifact-versioning.md`).

The correct version of this signal already exists, in a test.
`tests/unit/test_tripwire_unarchived_plans.py` computes *complete on
`origin/main`* ∩ *still in the working tree*. It materialises `origin/main`'s
`plans/` subtree with `git archive` and runs the same predicate on it. That is
why the tripwire did not fire on the branch that led to #526.

## 2. Goal and non-goals

**Goal.**

1. "Merged" has one definition, shared by `fr status`, `fr archive`, and the CI
   tripwire: the plan is complete as it exists on `origin/<default>`.
2. The sweep shows three buckets: merged but not archived, complete locally but
   waiting for merge, and in progress. It suggests `fr archive <dir>` only for
   the first bucket, one command per plan, and never `--all` (decision
   `d2-suggestion`).
3. `fr archive` refuses a plan whose undispatched phases are not complete on
   `origin/<default>` (#544, decision `d1-scope`). `--force` on a single plan
   still overrides.

**Non-goals.**

- The dispatched arm of `archive_gate` stays as it is. A dispatched phase
  already needs gh to show a merged PR (`_phase_complete`), which is real merge
  evidence.
- No gh or PR lookups in the sweep. The default branch is the evidence, which
  keeps the sweep working across forges.
- `completed_unarchived_plans` keeps its meaning (locally complete). The CI
  tripwire uses it as a building block.

## 3. Design

### A. One merge-evidence helper in `fr.archive`

`fr/archive.py` gains the single definition of "merged":

```python
@dataclass(frozen=True)
class DefaultRef:
    ref: str            # e.g. "origin/main" — a remote-tracking ref, never a local branch
    sha: str            # short SHA read, so a stale ref is visible in output

@dataclass(frozen=True)
class MergeEvidence:
    ref: DefaultRef | None          # None = no remote-tracking default ref resolvable
    fetched: bool                   # a fetch was attempted and succeeded
    fetch_error: str | None         # attempted and failed (offline, auth) — evidence is the stale local ref
    complete_on_ref: frozenset[str] # plan-dir names complete AS THEY EXIST on ref
    landed_phases: Mapping[str, frozenset[int]]  # plan name → phase numbers locally complete on ref

def merge_evidence(repo_root: Path, *, fetch: bool) -> MergeEvidence: ...
```

**How the default ref is found.** Only remote-tracking refs count, because a
local `main` does not show that anything merged:

1. `refs/remotes/origin/HEAD`, if its target exists.
2. `refs/remotes/origin/{main,master,trunk,develop}`, the first one that exists.

The remote name comes from the same lookup `fr.artifacts.commit` uses
(`_remote_name`), with the single-remote fallback. If none of these resolves,
`ref=None` and nothing counts as merged. The answer is "unknown", never
"merged".

**Fetch (decision `d3-evidence`).** With `fetch=True`, the helper first runs
`git fetch --quiet --no-tags <remote>` with `GIT_TERMINAL_PROMPT=0` and a
30-second timeout. A failure is not fatal. `fetch_error` records it, the
evidence falls back to the local remote-tracking ref, and every surface prints
that fact. A fetch changes only remote-tracking refs, never the working tree or
any registered artifact, so `status` can stay in `READ_ONLY_COMMANDS`.

**Materialising the ref's plans.** The helper runs
`git archive <ref> docs/superpowers/plans`, extracts the result into a temp
dir, and runs `completed_unarchived_plans` on that tree. This moves the
tripwire's `_completed_plans_on_origin_main` into shipped code. It also records
which phases are locally complete for each plan on the ref (`landed_phases`),
which the #544 gate needs. If the ref has no `plans/` tree, the sets are empty.

The tripwire imports this helper with `fetch=False`. CI already fetched with
`fetch-depth: 0`, and the test must stay offline. The tripwire keeps its own
failure message and its fixture tests, now aimed at the shared helper. There
is then one definition of "merged".

### B. `fr status` sweep: three buckets

`_sweep_lists` becomes a sweep over `merge_evidence(repo_root, fetch=True)`:

- **merged** = `complete_on_ref` ∩ plans still in the working-tree `plans/`
- **complete_unmerged** = `completed_unarchived_plans(repo_root)` − merged
- **in_progress** = every other plan folder, unchanged

Text output:

```
merged but not archived — complete on origin/main @ f6a2603 (1):
  2026-09-20-foo
    fr archive docs/superpowers/plans/2026-09-20-foo

complete locally, not yet on origin/main — waiting for merge (1):
  2026-09-23-bar

in progress (2):
  ...
```

- One `fr archive <dir>` line per merged plan. Never `--all`.
- The complete-unmerged bucket gets no command.
- A fetch failure adds `(fetch failed: <reason> — using the local origin/main
  ref)`.
- `ref=None` turns the second heading into `complete locally — merge state
  unknown (no origin/<default> ref; try git fetch / git remote set-head origin
  -a)`, and the merged bucket is always empty.
- When nothing is merged: `no merged-but-unarchived plans.` Other buckets
  follow as usual.

JSON (decision `d4-json`):
`{"archivable": [...merged], "complete_unmerged": [...], "in_progress": [...],
"default_ref": {"ref", "sha", "fetched", "fetch_error"} | null}`.
`archivable` narrows: it can only get shorter, never longer.

### C. `archive_gate` requires landed evidence (#544)

`render.archive_gate(plan, observed, *, landed: frozenset[int] | None)`. The
new keyword is **required, with no default**, so no caller can skip the
question. `landed` is the set of phase numbers that are locally complete on
`origin/<default>`. `None` means the merge state is unknown.

- Dispatched arm: unchanged.
- Undispatched arm: a phase passes only if it is locally complete **and** its
  number is in `landed`. Otherwise the blocker reads `Phase N: complete
  locally, not on origin/main — merge the PR first` (or `… merge state unknown
  — no origin/<default> ref`).

The three callers compute `landed` from one `merge_evidence` call:

- `fr archive`: `fetch=True`, one call per invocation (not one per plan under
  `--all`). `--force` on a single plan still overrides every blocker. `--force
  --all` stays refused.
- `fr status <plan>`'s "plan complete — run fr archive" nudge.
- `fr apply`'s matching nudge.

All three share one gate, so they cannot disagree. A plan that is not on the
ref at all gets `landed=frozenset()`.

### D. Prose

`plugins/super-fr/skills/fr-progress/SKILL.md` describes the sweep. Update it
to the three buckets and per-plan commands. Regenerate both mirror sets
(`sync-opencode.py`, `sync-hermes.py`). The fr-goal close-out (`fr archive
<plan-dir>` after verify-merge) already runs after merge and needs no change.
No explainer describes the sweep, and a patch release does not trigger
explainer updates.

### E. Housekeeping

Patch bump (bug fix; the gate gets stricter in the direction #544 asks for).
Acceptance rows `status-sweep-merge-evidence` and
`archive-refuses-unmerged-plan` go in at `ci`. The live walk is the trailing
manual phase.

## 4. Risks

- **A slow or hanging fetch** would stall `fr status`. The 30-second timeout
  and `GIT_TERMINAL_PROMPT=0` bound it, and failure degrades instead of
  aborting.
- **Archive tests build repos with no remote.** About 20 tests in
  `test_archive_cmd.py` must now commit the plan and add a file-path remote,
  like the tripwire fixtures do. A shared test helper keeps this in one place.
- **Squash-merge.** Evidence is the plan's *content* on the ref, not commit
  ancestry, so a squash merge counts as merged.
- **Plan complete on main but edited locally since.** It is still "merged". The
  archive dirty check (`paths_dirty`) still guards uncommitted edits.

## 5. Test Plan

**In this PR:**

1. Unit `merge_evidence`: origin/HEAD resolution; fallback to a remote
   well-known branch; a local-only `main` never counts; `ref=None` when no
   remote; plan complete on the ref versus only in the tree; plan incomplete on
   the ref but complete in the tree is not merged; `landed_phases` per phase;
   fetch success, fetch failure (unreachable remote) degrading with
   `fetch_error` set.
2. Tripwire `test_tripwire_unarchived_plans.py` uses the shared helper; its
   fixture tests still pass.
3. Unit sweep: the three buckets; per-plan `fr archive <dir>` lines; `--all`
   never printed; the complete-unmerged bucket has no command; ref-unknown
   wording; fetch-failed note; JSON keys and `default_ref`.
4. Unit gate: undispatched phase complete locally but not landed → blocked; not
   on the ref → blocked; `landed=None` → blocked with unknown wording; landed →
   passes; dispatched arm unchanged; the keyword is required (a call without
   it is a `TypeError`).
5. `fr archive`: unmerged plan refused (single, exit 2) and skipped (`--all`);
   merged plan archived; `--force` single still overrides; one fetch per
   invocation.
6. `fr status <plan>` and `fr apply` nudges do not fire for an unmerged plan.
7. Skill validation, neutrality, and all three mirror tripwires green; version
   lockstep green; acceptance rows added; `fr acceptance check` green.

**Pre-merge and post-merge, operator-driven (trailing `[manual]` phase):**

8. On this run's own branch, after implement, before merge: `fr status` lists
   this plan under "complete locally, not yet on origin/main". It does not call
   it merged and prints no archive command. `fr archive <this plan>` refuses.
9. After the PR merges, on `main`: `fr status` lists this plan under "merged
   but not archived" with its `fr archive <dir>` line, and the close-out
   archive succeeds.

## 6. Evidence hygiene

All fixtures are built in temp git repos with fictional plan names. Live
evidence comes from `derio-net/super-fr` (public, owned by `derio-net`). No
third-party hosts.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-09-23-archive-merge-evidence | `derio-net/super-fr` | `2026-09-23-archive-merge-evidence` | — |
