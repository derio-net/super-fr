<!-- fr:journal-schema=2 -->
# Journal: 2026-10-23-opencode-2-followups

<!-- fr:journal kind=repro scope=debug id=77c388113584 created=2026-10-23T05:07:57+00:00 -->
### 77c388113584 · repro · Six follow-ups from the OpenCode 2 port: four code defects, one operator parity decision, one live-proof gap

Batch requested: #1231, #1227, #1224, #1223, #1222, #1221.

Failing behaviour, one per issue:

- **#1231** — OpenCode 2.1.3 never delivers `session.idle`; it delivers `session.execution.succeeded`. `src/idle.ts` matches only `session.idle`, so the idle nudge never fires. Repro: synthetic advanceable run in a disposable clone (`fr run check --idle --format json` → exit 3), then a real 2.1.3 session: model replies, no nudge.
- **#1227** — no phase-2 handler has run inside a real model-driven 2.x session: the execute.before throw reaching the model, execute.after firing for `skill`, `context`'s system part reaching the request, `session.deleted` on the subscription.
- **#1224** — `parity.yaml`'s `deliver-tests-provenance` OpenCode cell says `enforced` on 1.x evidence, while every sibling row that reads the same 2.x store is `partial` pending `opencode-observe-take10-rerun`.
- **#1223** — `tests/integration/test_install_atomic.py` times out at its 60 s bound under full-suite `-n auto` load (8 sandbox installs), serially fine.
- **#1222** — OpenCode 2 `compaction` rows carry `data.tokens`; `fr/usage/readers/opencode.py` reads assistant rows only, so a compaction turn counts as zero tokens.
- **#1221** — `src/marker.ts` runs git/pwd/bash through unbounded `execFileSync` on every edit, and spawns bare `git` from PATH rather than resolving it as the bash guard does (`FR_GIT_CANDIDATES`).

Operator decisions (recorded before code): #1224 keeps `enforced` and is re-observed live on 2.x; live walks run in this session for #1227 and #1231; one batch PR on `fix/opencode-2-followups`.
