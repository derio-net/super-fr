# Auto-archive merged fr plans (#334)

**Spec:** `docs/superpowers/specs/2026-07-03-auto-archive-merged-plans-design.md`

## Why

Merged fr plans keep getting stranded in `docs/superpowers/plans/` instead of
moving to `implemented/plans/`. The move machinery (`fr archive --all`) and
per-plan detection (`fr status <dir>` → "plan complete") already exist — what's
missing is *unprompted, repo-wide detection* and an *automatic backstop*. This
plan closes that gap in the repo's own idiom: a code-enforced, tested guard
(#328 principle), not prose.

## Shape

One pure, gh-free predicate is the spine:

```python
# fr.archive
def completed_unarchived_plans(repo_root: Path) -> list[str]:
    # plan-dir names under docs/superpowers/plans/ where EVERY phase is
    # render.plan_locally_complete(...) — offline, deterministic, conservative.
```

Both new surfaces consume it, so "merged-but-unarchived" has exactly one
definition:

- **Phase 1** — the predicate + its tests.
- **Phase 2** — `fr status` with no `PLAN_DIR` becomes a read-only repo-wide
  sweep (text + json), nudging toward `fr archive --all`. Status stays
  allowlist-safe / never mutates.
- **Phase 3** — a hard-fail pytest tripwire (`test_tripwire_unarchived_plans.py`)
  that fails CI when a complete plan lingers in `plans/`. This makes the archive
  non-skippable.
- **Phase 4** — archive the live offender `2026-07-02-cncd-phase1-integration`
  (13/13 complete, never dispatched) so the tripwire ships **green** — the
  feature's own end-to-end proof.
- **Phase 5** — patch version bump (user-observable CLI change) + ruff + full
  suite.

## Not doing

Issue #334 option 1 (auto-open a housekeeping PR when the final phase merges):
no reliable local merge trigger exists in this flow, so it's out of scope. The
auto-archive path is the existing `fr archive --all`, surfaced by the new
detection.

## TDD

Every code phase is red → green → optional-refactor. Phase 3's tripwire is
deliberately red at author time (the repo-level assertion) and goes green only
once phase 4 archives cncd — the plan sequences the offender-archive to prove
the guard works, not to paper over it.

## Known quirk

`fr archive` leaves the spec-ref repair unstaged (RM state). Phase 4 runs
`git add -A` after archiving so the committed tree carries the normalized
bare-slug spec ref.
