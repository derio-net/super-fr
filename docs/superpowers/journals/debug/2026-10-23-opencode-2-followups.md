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

<!-- fr:journal kind=root-cause scope=debug id=3b9f0d4c1a77 created=2026-10-23T05:42:56+00:00 -->
### 3b9f0d4c1a77 · root-cause · #1221: the edit gate spawned bare, unbounded processes on the hot path — the opposite of what the bash guard does

`src/marker.ts` resolved the file's repo with `execFileSync("git", ["-C", dir, "rev-parse", "--show-toplevel"])`, with no `timeout`, and asked three more questions the same way: `execFileSync("pwd", {cwd})` for realpath, `execFileSync("bash", ["-c", "for cfg in …/.devcontainer/*/devcontainer.json …"])` for the fr-enabled check, and two more git calls for the common-dir/git-dir pair. Every one of them ran inside the plugin's `execute.before` hook — awaited by the OpenCode server before the tool call it judges — on EVERY file-writing call, in every session.

Two separate defects in one shape:

- **Unbounded.** `execFileSync` has no timeout, and its default stdio inherits the server's pipes. A git that blocks (a wrapper or shim on a network mount, a credential helper, a hung FUSE path) stalls the hook, and with it every edit in the server, indefinitely. The bash guard's equivalent probe is `_fr_toplevel_of`, which is a single `"$FR_GIT_BIN" … 2>/dev/null` with no shell loop per call.
- **Unresolved.** The spawn used the bare name `git`, i.e. whatever `PATH` the OpenCode server inherited. Hooks and this plugin spawn with no shell, so that PATH is not the operator's login PATH (the gh#746 defect, fixed for `fr` by pinning `FR_HARNESS_FR`). The bash guard already answers this correctly and has for months: `lib/fr-isolation-decision.sh` resolves ONE absolute binary through `FR_GIT_CANDIDATES` (`git /usr/bin/git /usr/local/bin/git /bin/git /opt/homebrew/bin/git`) precisely because a PATH that lost `/usr/bin` still has git.

<!-- fr:journal kind=finding scope=debug id=8ac1e5f702b3 created=2026-10-23T05:43:05+00:00 state=fixed -->
### 8ac1e5f702b3 · finding [fixed] · #1221 fixed: one resolved git, bounded; syscalls where the shell was only asking about directories; fail-open announced at load

New `src/git.ts`: `resolveGit()` picks the first executable candidate from `FR_GIT_CANDIDATES` (word-split like the bash guard) or the bash guard's default list, cached per `(FR_GIT_CANDIDATES, PATH)` pair so a repaired PATH needs no reset hook; `git(dir, …)` runs `-C` through `runSync` (`GIT_TIMEOUT_MS = 5_000`, SIGKILL on expiry) and returns `undefined` for unresolvable/timed-out/non-zero — it never throws, like every other handler here. `marker.ts` now uses it, plus `realpathSync` and `readdirSync` in place of the `pwd` and `bash -c` subprocesses (`guard.ts` and `sentinel.ts` use the same module; `sentinel.ts` had its own copy of the bare, unbounded call).

The posture is fail-OPEN and now stated: no toplevel means no verdict, which is what the bash guard's `_fr_toplevel_of` failure already produced. `setup` resolves git eagerly and warns ONCE per process (`console.error`) when nothing is executable, naming `FR_GIT_CANDIDATES` — because an allow nobody announced reads as a verified decision. Documented in `marker.ts`'s header, `README.md` and `plugins/super-fr/rules/fr-isolation-required.md` (mirrors regenerated).

Evidence:
- `test/git.test.ts` (10 cases): candidate order pinned against the bash list; null with nothing executable; an absolute candidate survives a stripped PATH; cache-per-env; `undefined` for non-repo, unresolvable and empty answers.
- `test/guard-verdicts.test.ts` + `tests/fixtures/hooks/guard-verdicts.yaml`: new captured row `git-unresolvable` (`PATH` = `{bin}/bin-no-git`, `FR_GIT_CANDIDATES` = nothing) — both engines DENY the base-repo command rather than allowing it; `guard-world.sh` builds the shim from the caller's PATH minus `git*`, so the row removes git and nothing else; `capture_guard_verdicts.py` now expands placeholders inside a row's `env` and runs bash by absolute path.
- `tests/unit/test_hooks_guard.py` 139 passed; `bun test` 232 passed; `bunx tsc --noEmit` clean.

<!-- fr:journal kind=finding scope=debug id=5d21c8be0a4e created=2026-10-23T05:43:13+00:00 state=fixed -->
### 5d21c8be0a4e · finding [fixed] · Found while fixing #1221: the edit gate read `write` CONTENT as an absolute path when it began with `//`

`index.ts`'s `collectPathValues` treats any unkeyed string that `path.isAbsolute` accepts as a possible target, so that an unknown path-carrying tool still fails closed. `write`'s `content` is an unkeyed string: a file whose first bytes are `//` (a licence header, a commented-out include) was therefore probed as a path, and the refusal named the CONTENT — `fr-isolation: cannot inspect target symlink: // …  …`, with ENAMETOOLONG for a real file. Observed when writing the TypeScript test files for #1221; the running plugin still refuses those calls.

Fix: a string is only a path target when it is ONE LINE and at most `MAX_PATH_BYTES = 4096` (`looksLikePath`) — the `PATH_KEYS` branch (`filePath`, `path`, …) is unchanged and still absolute-or-relative by key, and patch bodies keep their own parser. `test/index.test.ts` pins three cases: a `//`-headed `write` in the base clone is denied naming the FILE and never the content; the same write inside a valid workspace is allowed; a 5000-character single-line absolute string is content, not a probe.

<!-- fr:journal kind=finding scope=debug id=c0b488ce5017 created=2026-10-23T05:55:49+00:00 state=fixed -->
### c0b488ce5017 · finding [fixed] · #1231 fixed: the idle nudge fires on the event 2.1.x actually delivers, and one nudge per position was observed live

`src/idle.ts` now accepts `TURN_END_EVENTS = {"session.idle", "session.execution.succeeded"}` and runs the same once-per-`position` loop for either. `session.idle` stays matched: `strings $(which opencode)` still carries it, so an operator on a 2.1.x build that does emit it is not left behind by a fix for a 2.1.3 server. The header records the lineage (2.0.x emitted `session.idle`; 2.1.3 emits `session.execution.succeeded` and records an `idle` message with `outcome: succeeded` instead) so the next reader does not have to re-derive it from a session export.

Tests: `test/idle.test.ts` gained four cases — `session.execution.succeeded` nudges once and not twice at the same position, an unrelated event does not nudge, and a run that moves position between events nudges again (so the dedupe is per position, not per session). 39 pass.

**Live walk, OpenCode 2.1.3** (isolated HOME/XDG, a logging `fr` shim, `opencode/deepseek-v4.1-flash-free`), synthetic advanceable run `2026-10-23-live-idle` in a disposable clone on branch `live-idle`: the model replied `ready`, then the nudge text appeared in the session export as a plugin-authored message (not the operator's prompt) and the model ran `fr run advance 2026-10-23-live-idle` — the shim log carries it. The event fan-out is visible there too: the server delivered the terminal event to three listeners, so `fr run check --idle` and `fr isolation detach` each appear three times in the shim log for that one event, while exactly ONE nudge was submitted — which is the once-per-position guard doing its job, not three nudges raced by the model.

<!-- fr:journal kind=finding scope=debug id=70cb14eda62b created=2026-10-23T05:56:01+00:00 state=fixed -->
### 70cb14eda62b · finding [fixed] · #1227 proven live: all four phase-2 handlers ran inside real model-driven 2.1.3 sessions

Four separate 2.1.3 sessions, each in the disposable world under `$TMPDIR/fr-live-opencode2` (isolated HOME/XDG, `opencode/deepseek-v4.1-flash-free`, the plugin delivered from this branch, a logging `fr` shim on PATH so every handler-initiated `fr` call is timestamped):

1. **`execute.before`'s refusal reaches the model.** A `write` to a tracked file in an fr-enabled clone came back to the model as a failed tool call carrying the guard's own text ("not inside an fr-isolation workspace"), and the model reported the refusal instead of the write. The file was unchanged. The handler's throw is therefore not swallowed by the server — it is the model-visible tool result.
2. **`execute.after` fires for `skill`, with status completed.** After the model invoked `fr-brainstorming`, `$ROOT/home/.cache/fr/sentinels/ses_e98af6cccffezgh2hxwdqP93OM.json` was written by the handler with `{"skill": "fr-brainstorming"}` — i.e. the skill name reached the sentinel writer, which only the `execute.after` path does.
3. **`context`'s `event.system.push` reaches the request.** A fresh top-level session in a repo with acceptance debt answered the nag probe and QUOTED the debt block verbatim ("Acceptance debt in this repo … p2-row-1 [walk-owed] …"), while the operator prompt did not contain it. A system part, not a prompt rewrite — the row's own acceptance.
4. **`session.deleted` arrives on the subscription.** `opencode session delete` against that session produced `fr isolation detach --session ses_e98af17c2ffebqTXFLmmWLiWdR` in the shim log, which only the `session.deleted` branch issues.

Two observations worth keeping. The server fans one terminal event out to every subscribed listener (proof 4's `detach` and the idle guard's `check --idle` both appear three times per event), so every handler must be idempotent per session/event — `setProcessWarned`, the sentinel writer and the idle dedupe all are. And an `edit`/`write` whose *content* begins with a path-looking string (`//…`) was itself refused by the edit gate as if the content were the path: recorded as its own finding below, fixed in this PR.
