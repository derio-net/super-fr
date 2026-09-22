# Journal: 2026-09-23-lifecycle-container-vs-worktree

<!-- fr:journal kind=discovery scope=plan id=0ff1a43ad622 created=2026-09-23T01:05:39 phase=4 -->
### 0ff1a43ad622 · discovery · no-refactor-because P4.T1 (phase 4)

Red-only task: it writes failing tests; production code does not exist yet, the refactor pass is P4.T3.S3.

<!-- fr:journal kind=discovery scope=plan id=b2698d7d0da0 created=2026-09-23T01:05:40 phase=4 -->
### b2698d7d0da0 · discovery · no-refactor-because P4.T2 (phase 4)

Red-only task: failing tests only; the refactor pass for the preserve module is P4.T3.S3.

<!-- fr:journal kind=discovery scope=plan id=94d22e0fbf2e created=2026-09-23T01:05:40 phase=5 -->
### 94d22e0fbf2e · discovery · no-refactor-because P5.T1 (phase 5)

Red-only task: failing tests only; refactor lives in P5.T2.S2.

<!-- fr:journal kind=discovery scope=plan id=63c9d00fb633 created=2026-09-23T01:05:40 phase=6 -->
### 63c9d00fb633 · discovery · no-refactor-because P6.T1 (phase 6)

Prose, generated mirrors and a version bump: no code structure to refactor; mirrors are generator-owned.

<!-- fr:journal kind=discovery scope=plan id=41a03e1da877 created=2026-09-23T01:05:41 phase=6 -->
### 41a03e1da877 · discovery · no-refactor-because P6.T2 (phase 6)

Live verification and matrix status moves: no code is written.

<!-- fr:journal kind=discovery scope=plan id=8f763b55b51e created=2026-09-23T01:05:48 phase=1 -->
### 8f763b55b51e · discovery · no-refactor-because P1.T1 (phase 1)

Red-only task: failing tests only; the phase's green task carries the refactor step.

<!-- fr:journal kind=discovery scope=plan id=e1e4eeb0c509 created=2026-09-23T01:05:49 phase=2 -->
### e1e4eeb0c509 · discovery · no-refactor-because P2.T1 (phase 2)

Red-only task: failing tests only; the phase's green task carries the refactor step.

<!-- fr:journal kind=discovery scope=plan id=b653780d4c09 created=2026-09-23T01:05:49 phase=3 -->
### b653780d4c09 · discovery · no-refactor-because P3.T1 (phase 3)

Red-only task: failing tests only; the phase's green task carries the refactor step.

<!-- fr:journal kind=discovery scope=plan id=9dfaeed2a006 created=2026-09-23T01:17:00 phase=1 -->
### 9dfaeed2a006 · discovery · P1.T2 refactor: strict container lookup shared by restart and stop (phase 1)

Refactored rather than no-refactor: `LocalWorktreeDevcontainerTarget._ps_parts_strict` (docker ps --all; a non-zero rc or missing docker binary raises IsolationError 'docker is unreachable', never reads as absence — #354) and `_require_container(state, nothing)` (raises with the `fr isolation up` hint). `restart` now uses `_require_container` too. Behaviour change for restart: a FAILED docker ps used to surface as 'no container — nothing to restart'; it now says docker is unreachable. Phase 2's `_ensure_running` can build on `_ps_parts_strict`.

<!-- fr:journal kind=discovery scope=plan id=1e6486082107 created=2026-09-23T01:17:01 phase=1 -->
### 1e6486082107 · discovery · stop treats exited/created/dead as already stopped; status maps only exited (phase 1)

`_NOT_RUNNING = {exited, created, dead}`: stop on any of these is a no-op success ('already stopped (<id>, docker state <s>)'). A container absent after a successful `docker stop` (e.g. --rm) is accepted as stopped. status maps only `exited` -> `stopped` per spec §3.B (helper `_shown_container_state`); `created`/`dead` pass through. The FakeRunner in tests/unit/test_isolation.py gained a stateful `stopped` set + `stop_sticks` flag (still-running-after-stop case).
