# Journal: 2026-09-23-archive-merge-evidence

<!-- fr:journal kind=discovery scope=plan id=1976193fd0f3 created=2026-09-23T16:58:49 phase=1 -->
### 1976193fd0f3 · discovery · no-refactor-because P1.T1 (phase 1)

P1.T1 is the red half of red-green-refactor: it only writes failing tests. The refactor step lives at the end of the green task P1.T2, where there is production code to refactor.

<!-- fr:journal kind=discovery scope=plan id=804d6bd5cdb4 created=2026-09-23T16:58:50 phase=2 -->
### 804d6bd5cdb4 · discovery · no-refactor-because P2.T1 (phase 2)

P2.T1 is the red half of red-green-refactor: it only writes failing tests. The refactor step lives at the end of the green task P2.T2, where there is production code to refactor.

<!-- fr:journal kind=discovery scope=plan id=196f121f6fa2 created=2026-09-23T16:58:50 phase=3 -->
### 196f121f6fa2 · discovery · no-refactor-because P3.T1 (phase 3)

P3.T1 is the red half of red-green-refactor: it only writes failing tests. The refactor step lives at the end of the green task P3.T2, where there is production code to refactor.

<!-- fr:journal kind=discovery scope=plan id=80e0b0080222 created=2026-09-23T17:09:36 phase=1 -->
### 80e0b0080222 · discovery · agentic_landed is judged from the ref's copy of the plan (phase 1)

MergeEvidence.agentic_landed is computed from the plan as it exists on the default ref (spec 3.A). A phase that exists only in the working tree (added after an earlier merge) is not in the ref's plan, so it cannot block agentic_landed. Phase 2's sweep (archivable = agentic_landed AND locally complete) could therefore list such a plan as archivable; phase 3's archive_gate still blocks it per phase via landed_phases, which is the safe direction. If phase 2 wants 'archivable only narrows' to hold strictly, it should also require every LOCAL agentic phase number to be in landed_phases[name]. Also: fr.git now owns GitRefusal, GitUnavailableError, git_answer, ref_exists, WELL_KNOWN_DEFAULTS, remote_name, remote_default_ref (returns '<remote>/<branch>'); fr.artifacts.commit re-exports the first two via __all__, so existing imports keep working.

<!-- fr:journal kind=finding scope=plan id=f-p2-local-phases created=2026-09-23T17:18:52 phase=2 state=open -->
### f-p2-local-phases · finding [open] · Sweep's merged buckets must check every LOCAL agentic phase against landed_phases (phase 2)

From phase 1 discovery 80e0b0080222: agentic_landed is judged from the ref's copy of the plan, so a phase that exists only in the working tree (added after an earlier merge) does not block it. The sweep must classify a plan as merged (archivable / merged_manual_open) only when every agentic phase in the WORKING-TREE plan is in landed_phases[name]; otherwise it is complete_unmerged or in_progress. Test: plan on ref with phase 1 landed, phase 2 added + ticked locally -> complete_unmerged, not archivable.

<!-- fr:journal kind=review scope=plan id=rev-p1 created=2026-09-23T17:21:42 phase=1 -->
### rev-p1 · review · Phase 1 review (dispatched feature-dev:code-reviewer): no findings (phase 1)

Reviewer verified default-ref fidelity with the old _default_branch (commit-gate tests unchanged), the fetch seam (timeout, GIT_TERMINAL_PROMPT=0, failure degrades, real destroyed-remote test), git archive materialisation, per-phase landed_phases, agentic_landed excluding manual phases (closed PhaseTag literal), unparsed_on_ref, the tripwire's explicit skip, and test quality (real repos, no network). No findings at >=80 confidence. The known working-tree-only-phase gap is filed against phase 2 as f-p2-local-phases.
