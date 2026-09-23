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
