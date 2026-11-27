<!-- fr:journal-schema=4 -->
# Journal: 2026-11-27-triage-leaves-split

<!-- fr:journal kind=decision scope=plan id=p1-src-consumers-import-new-homes created=2026-11-27T20:59:41+00:00 phase=1 -->
### p1-src-consumers-import-new-homes · decision · src consumers import the moved names from their new homes; batch_drive still re-exports them (phase 1)

mypy strict (no implicit re-export) refused nine src modules that imported moved names
from `fr.triage.batch_drive` through the plain `# noqa: F401` re-export (30 errors). The
`X as X` spelling made ruff's isort split every alias into its own statement (+74 lines,
over the new budget). So `triage_batch_cmd`, `settle/managed`, `batch_merge`, `kanban`,
`operator_entries`, `queue_reports`, `readiness`, `views` and `wave_queue` now import those
names from `batch_drive_types`, `batch_drive_export` and `handback_rules` (import lines only,
R7). `batch_drive` keeps the plain re-export the spec names, so R6 holds and the tests (not
type-checked) keep importing from it (R9). The new import statements are one line each
where they fit, so `triage_batch_cmd.py` (held, budget 8320) shrinks to 8315 lines.
`docs/reference/cli.md` (covers `triage_batch_cmd.py`) got the same
`still true, module split only` stamp.

<!-- fr:journal kind=discovery scope=plan id=p1-unused-model-imports-dropped created=2026-11-27T20:59:41+00:00 phase=1 -->
### p1-unused-model-imports-dropped · discovery · four model imports batch_drive no longer used were dropped (phase 1)

After the hand-back move `batch_drive.py` no longer used `typing.Literal`,
`ArchiveConflictEvent`, `CloseoutHandbackEvent` or `ConflictEvent`; ruff removed them. No
module imports any of them from `batch_drive` (all import them from `fr.triage.model`).
An AST comparison against origin/main showed all 30 moved definitions byte-identical.

<!-- fr:journal kind=discovery scope=plan id=p1-docs-stamp-prepended created=2026-11-27T20:59:41+00:00 phase=1 -->
### p1-docs-stamp-prepended · discovery · reviewed stamps were prepended, keeping the history (phase 1)

Each page's `reviewed:` got `2026-11-27 still true, module split only; ` prepended to its
existing note, the convention every earlier stamp on these pages follows.

<!-- fr:journal kind=discovery scope=plan id=p1-fast-tier-not-completed created=2026-11-27T20:59:41+00:00 phase=1 -->
### p1-fast-tier-not-completed · discovery · the brief's fast tier selects 11421 tests and could not finish on the loaded host (phase 1)

`pytest --fr-scope origin/main -n 2` selects 11421 tests (the doc stamps pull in every
own_artifacts test, `triage_batch_cmd.py` fans out widely). At host load ~25-35 it ran about
25 tests a minute, and three attempts were killed from outside (SIGTERM, exit 144) within
minutes; the last was stopped by hand at about 300 tests, none failed. In its place, after the final
code commit: every triage batch/drive/kanban/views/readiness/wave_queue/operator/queue/handback
unit file, settle, import direction, the module budget, the explainers tripwire and
test_triage_batch_drive_cmd.py, 1985 passed. CI (`tests: ci`) is the suite evidence.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-27T20:59:41+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

guard widening, a budget number, doc stamps and a fragment; no code was written that could be cleaned.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-27T21:04:06+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · spec Background/Design/R11 no longer match: nine src callers import moved names from their new homes and docs/reference/cli.md was stamped (phase 1)

Strict mypy (no_implicit_reexport) forced the caller repointing; the spec still said callers import through the re-export.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-27T21:04:06+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · batch_drive.py TYPE_CHECKING comment says wave_queue imports batch_drive, false since wave_queue now imports batch_drive_types (phase 1)

packages/fr/src/fr/triage/batch_drive.py:109.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-27T21:04:06+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · batch_merge.py:25-27 single-name import left on three lines (phase 1)

Leftover trailing comma from the repointing.

<!-- fr:journal kind=review scope=plan id=review-p1 created=2026-11-27T21:04:06+00:00 phase=1 -->
### review-p1 · review · phase 1 review: 3 findings, all in scope and fixed (phase 1)

Independent reviewer verified: all 30 moved definitions byte-identical (ast source segments vs origin/main); moved set exactly R1/R2/R3; each new module imports cleanly in a fresh interpreter with no batch_drive* load (R5); every origin/main name of batch_drive still an attribute except four plain non-re-exported imports nothing used (R6); mypy clean over 470 files; triage_batch_cmd.py 8315 <= 8320; purity guards flag a planted impurity per file and require >= 4 files; budget 1900 vs 1879; fr docs check clean; fragment present; 268 targeted tests passed. Findings p1-r1..p1-r3.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-27T21:04:06+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: spec Background/Design/R11 no longer match: nine src callers import moved names from their new homes and docs/reference/cli.md was stamped (phase 1)

Spec amended: Background states mypy's no_implicit_reexport; new R9a requires src callers to import from the new homes; R11 adds docs/reference/cli.md; the Design shape lists the nine files.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-27T21:04:06+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: batch_drive.py TYPE_CHECKING comment says wave_queue imports batch_drive, false since wave_queue now imports batch_drive_types (phase 1)

Comment now says fr.triage.readiness imports this module (readiness.py:59 still does), so both TYPE_CHECKING modules are read lazily.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-27T21:04:06+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: batch_merge.py:25-27 single-name import left on three lines (phase 1)

Collapsed to `from fr.triage.batch_drive import checks_verdict`.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1 created=2026-11-27T21:06:05+00:00 state=open review_scope=in -->
### l-docs-accuracy-r1 · finding [open] (reviewer: in scope) · fr-wave-driver.md covers: adds the two new leaves but not triage/handback_rules.py, where the hand-back decisions moved

A later edit to the moved close-out and archive-conflict hand-back rules would no longer bring the page that describes them up for review.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r2 created=2026-11-27T21:06:05+00:00 state=open review_scope=out -->
### l-docs-accuracy-r2 · finding [open] (reviewer: out of scope) · fr-wave-driver.md:113-114 'at most twice per dispatch' rests on HANDBACKS_PER_DISPATCH, which no covers: entry reached even before this change

Pre-existing gap from the wave-queue-gaps §E move; not caused by this split.

<!-- fr:journal kind=review scope=plan id=lens-review created=2026-11-27T21:06:05+00:00 -->
### lens-review · review · lens review: docs-accuracy, 2 findings

docs-accuracy reviewer: no false or stale claim on the five touched pages; the shape file matches the diff; fr docs check reports 33 pages current. One coverage finding in scope (fixed), one out of scope.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1-resolved created=2026-11-27T21:06:05+00:00 state=fixed resolves=l-docs-accuracy-r1 -->
### l-docs-accuracy-r1-resolved · finding [fixed] · resolves l-docs-accuracy-r1: fr-wave-driver.md covers: adds the two new leaves but not triage/handback_rules.py, where the hand-back decisions moved

fr-wave-driver.md covers: now lists packages/fr/src/fr/triage/handback_rules.py.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r2-resolved created=2026-11-27T21:06:05+00:00 state=open resolves=l-docs-accuracy-r2 out_of_scope=true -->
### l-docs-accuracy-r2-resolved · finding [out-of-scope] · resolves l-docs-accuracy-r2: fr-wave-driver.md:113-114 'at most twice per dispatch' rests on HANDBACKS_PER_DISPATCH, which no covers: entry reached even before this change

Not caused by this change (the gap predates the split); r1's covers line, added for the moved decisions, incidentally reaches HANDBACKS_PER_DISPATCH too, so nothing is left to track.
