# Audit — transactional `plan create`, lossless v1→v2 migration, archived-plan reopen guard

**Date:** 2026-05-25 (single session)
**Audience:** future agents/operators touching `vk.plan_ops`, `vk.migrate`,
`vk.render`, or `vk apply`
**Outcome:** three independent transactional-integrity bugs (GH #133, #245,
#246) root-caused and fixed in PR #247, shipped as `vk 2.2.12`. Each fix is
covered by a failing-first test; full suite 462+ green, `ruff`/`mypy` clean.

---

## Why this document exists

GH issues #133, #245, #246 were filed against the `vk` toolchain over the
preceding days. They look unrelated on the surface, but a systematic
investigation showed they share one shape — **the code mutated or decided
before it validated, or validated against the wrong source** — and two of
them are causally linked: the archived plans #246 reopens got their lossy
completion markers *from* the #245 migration (#252 bulk run). This document
records the root causes and the fixes so the next person doesn't re-derive
them, and seeds the follow-up cross-repo scan.

---

## The three bugs

### #133 — `vk plan create` was not transactional

**Root cause:** `src/vk/plan_ops.py::create()` did `folder.mkdir()` and wrote
`_meta.yaml`/`_prose.md`/`NN.yaml` **before** calling `_append_spec_row()`,
which raises `no '## Implementation Plans' section found` when the target spec
lacks that section. The folder was left half-built, so the operator's
corrected re-run hit the `folder.exists()` guard (`plan folder already
exists`) and the spec row was never appended. No pre-flight, no rollback.

**Fix:**
1. **Pre-flight** `_validate_spec_section()` (read-only) runs before any
   `mkdir`, so a missing section fails loud with zero side effects — mirroring
   how `vk apply` validates reachability before `--yes` touches GitHub.
2. **Idempotent repair:** if the folder already exists and its on-disk content
   matches what `create()` would write (`_folder_matches`, comparing meta
   minus the `created:` date, prose, and the **exact set** of phase files), the
   missing spec row is appended and the parsed plan returned. A slug reused for
   *different* content — including a *dropped phase* (stale `NN.yaml` orphan) —
   is a real collision and still raises.

### #245 — v1→v2 migrator was silently lossy (3 + 1)

Discovered finalizing one plan in `derio-net/frank` (frank#384); measured
systematic across that repo's 71 migrated plans.

- **Bug 1 — `target_repo` fell back to the plugin's own repo.**
  `migrate.py` hardcoded `derio-net/superpowers-for-vk` when no phase declared
  `**Target repo:**` (45/71 plans), filing Issues against the wrong repo.
  **Fix:** resolution is `single per-phase declaration → explicit
  --target-repo → fail loud (MigrationError)`. Never the plugin repo.
  `--target-repo` also resolves multi-repo conflicts. New CLI flag added.
- **Bug 2 — `depends_on` only parsed `**Depends on:**`.** The `##
  Dependencies` / "Blocked by Phase N" prose convention flattened to `[]`
  (5/~267 phases had any dependency). **Fix:** `_extract_prose_depends_on`
  recovers it, with a per-plan warning on `MigrationOutcome.warnings`. The
  capture is anchored to a numeric-list grammar so trailing prose
  ("…took 5 days (v2.1 rollout)") can't leak phantom deps.
- **Bug 3 — task intro + `# manual-operation` blocks dropped.** The body
  fallback only fired when a task had **zero** parsed steps, so a task *with*
  steps silently lost the intro paragraph and the fenced `# manual-operation`
  block before its first step (load-bearing: `/sync-runbook` scans for those
  blocks). **Fix:** `_find_task_intro` preserves that content as a synthetic
  leading step `P{p}.T{t}.S0`.
- **Minor — `vk_version`** aligned `>=1.0.0,<3.0.0` → `>=2.0.0,<3.0.0` to
  match `vk plan create`.

> `--force` re-migration is **not** a remedy for already-migrated plans: it
> re-applies these bugs and clobbers hand-fixes. Code fixes first; a `--force`
> sweep is a separate, manually-curated operation that must exclude hand-fixed
> plans (e.g. frank#384).

### #246 — `vk apply` reopened closed Issues for done/archived plans

**Root cause:** `render._phase_complete` judged **agentic** completion by
`obs.linked_prs` — a *live* GitHub query (`observe.py` →
`real_ghclient.list_linked_prs` → GraphQL `closedByPullRequestsReferences`),
**not** the stored `completion.observed_prs`. A plan executed *inline* (direct
commits, or a PR without a closing keyword) has no observable merged PR, so
`_phase_complete` could never return `True` → desired state recomputed `OPEN`
(`render.py`) → `diff.py` emitted `set state … to OPEN` → on `--yes` the closed
Issue was reopened. `--all` was already safe (walks only `plans/`); the hazard
was an explicit `vk apply archived-plans/<plan>`.

**Fix (both halves the issue offered):**
1. **render:** a phase is complete when the Issue is *already CLOSED*,
   `completion.at` is set, and no open linked PR remains. This **only ratifies
   a close that already happened** — for an OPEN issue the merged-PR
   requirement still holds, so it cannot reintroduce the 2026-05-18
   premature-close incident.
2. **apply:** refuses an explicit `vk apply` on a path under
   `superpowers/archived-plans/`.

---

## Method (what worked)

`systematic-debugging` Phase 1 first: three parallel read-only `Explore`
agents mapped each bug's exact code path (file:line, execution order, data
flow) **before** any fix. That converted "the migrator is lossy" into "line
194 hardcodes the repo; line 474's `if not steps_out` skips the intro; line
123 reads the live query not the stored field" — precise enough to TDD.
Every fix was a failing test first, then the minimal change.

A post-implementation code review (fresh subagent, crafted context) caught a
**data-correctness gap the happy-path tests missed**: `_folder_matches` checked
"all expected files present and equal" but not "no *extra* files", so a re-run
that dropped a phase would repair-and-orphan the removed `NN.yaml`. Fixed with
set-equality on the phase-file names + a regression test. Lesson: test the
*fewer-than-before* case, not just match/mismatch.

---

## Next steps

- [ ] **Post-merge cross-repo scan.** Once `vk 2.2.12` lands, scan every repo
  under `~/Docs/projects/DERIO_NET` for the failure modes these bugs leave
  behind: `_meta.yaml` files with `target_repo: derio-net/superpowers-for-vk`
  that shouldn't have it (#245 Bug 1), phases with empty `depends_on` whose
  prose says "Blocked by Phase" (#245 Bug 2), tasks referencing a
  "manual-operation block above" with no block present (#245 Bug 3), and
  archived plans whose closed Issues a prior `vk apply` may have reopened
  (#246). Repos with v1→v2 migrated plans (notably `derio-net/frank`, 71
  plans) are the priority. The repair is **not** blanket `--force`
  re-migration — it is per-finding, hand-verified, excluding plans already
  hand-fixed.
- [ ] Decide whether a curated `--force` re-migration of frank's plans is
  worth it now that the migrator is fixed (exclude frank#384 and any other
  hand-edited plans).
