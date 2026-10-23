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

<!-- fr:journal kind=root-cause scope=debug id=0802292723ea created=2026-10-23T05:09:31+00:00 -->
### 0802292723ea · root-cause · #1222: the usage reader iterated assistant rows only, so compaction rows' tokens were invisible

`fr/usage/readers/opencode.py` builds `UsageRecord.messages` from `type == "assistant"` rows only. OpenCode 2 writes a compaction summary as its own `session_message` of `type: "compaction"`, carrying `data.tokens` and `data.model` (and `data.cost: 0`).

Measured in the operator's live 2.1.3 store (copy read read-only, 2026-10-23): 29 compaction rows; 14 carry `tokens` + `model` + `cost: 0`, 15 (migrated older sessions) carry none. So the defect both under-counts (tokens present, unread) and would mis-report if fixed by assuming zero (the 15 with no tokens).

<!-- fr:journal kind=finding scope=debug id=c4fa5d9437de created=2026-10-23T05:09:37+00:00 state=fixed -->
### c4fa5d9437de · finding [fixed] · #1222 fixed: a compaction row carrying tokens is one message; one without adds nothing

Failing test first: `test_opencode_compaction_turn_tokens_are_counted_not_zero` (a `compaction` row inserted into the `ses_paid` fixture with `tokens`, `model`, `cost: 0`) saw 1 message where 2 belong. Companion: `test_opencode_compaction_row_without_tokens_adds_no_zero_turn` pins the 15-row case — unknown tokens are not a zero-token turn.

Fix: `_read` accepts `compaction` rows that carry a `tokens` mapping alongside `assistant` rows (`data.model` names the model, `data.agent` is absent so the row reads as the session's own thread). `cost` stays assistant-only: OpenCode records none for a compaction, and the harness dollar total is unaffected. Module docstring records the live measurement. `tests/unit/test_usage_readers.py` + the store-agreement/rollup/report suites: 116 passed, 4 skipped.

<!-- fr:journal kind=root-cause scope=debug id=f6a51a6e38d4 created=2026-10-23T05:32:05+00:00 -->
### f6a51a6e38d4 · root-cause · #1223: eight sandbox installs each rsyncing the whole tree, concurrent with the suite, is what crosses 60s

Each sandboxed install runs `scripts/install.sh` against a fake HOME; the script rsyncs the repo root into the marketplace (`rsync -a --delete --exclude .git/__pycache__/.venv/.coverage*`) and then syncs each plugin cache with `--checksum`. Measured here: 166 MB / 3300 tracked files per install. Eight of those at once, sharing the disk with the rest of `pytest -n auto`, is the load that tips the last two `TestInstallLock` tests past their hard `communicate(timeout=60)`.

Measured: the file alone is 8 passed in ~28 s (17.6 s of it *system* time — rsync/forks, i.e. syscalls); `-n 8` on the file alone also passes. The full suite ran 13051 passed in 905 s on this host without reproducing the flake, so the 60 s crossing is load-dependent, not deterministic — which is exactly why the issue's "local reproduction: full suite, 12-core host" note matters.

Ruled out: a busy-wait in the install path. `install.sh` waits only in `sleep 1` lock polls and the staged-`fr` retry sleeps; the ~85%-of-a-core system time the issue saw is the copy itself (reproduced here: 17.6 s system for 8 installs, no spin). The real amplifier is concurrency.

<!-- fr:journal kind=finding scope=debug id=41905671acae created=2026-10-23T05:32:12+00:00 state=fixed -->
### 41905671acae · finding [fixed] · #1223 fixed: one install at a time across xdist workers, and a 180s hang bound

The file holds a machine-local `fcntl.flock` across every test (`_one_install_at_a_time`, autouse), so its eight sandboxed installs are the only ones on the disk at once — the issue's "bound the concurrent install load", without changing the CI invocation (`xdist_group` needs `--dist loadgroup`, which the suite does not use and which would rebalance every other file). The three hard `communicate(timeout=60)` bounds become `INSTALL_BOUND_S = 180` (the issue's "it is a sandbox, not a latency assertion"), so a genuine hang is still caught on a quieter disk. FUSE mounts that silently ignore flock fall back to the raised bound (documented in the module docstring).

Verified: file serial 8 passed in ~28 s; `-n 8` 8 passed with setup waits up to 43 s, proving the gate serialises across workers and releases (no deadlock, `test_overlapping_installs_serialise` still asserts the two in-test installs never overlap).
