<!-- fr:journal-schema=3 -->
# Journal: 2026-10-30-opencode-startup-metadata-ready

<!-- fr:journal kind=hypothesis scope=debug id=6e13d45851f3 created=2026-10-30T13:23:21+00:00 -->
### 6e13d45851f3 · hypothesis · Current main aborts unresolved startup metadata before bounded readiness can wait

Fresh origin/main bf59f77a946c retains RC11 behavior: wait_ready retries unknown-layout only and propagates dialog-or-unfocused immediately. Private paired captures of one unchanged no-focus, --auto diagnostic client show blank metadata/grey border then complete Build/model metadata and strict-parser acceptance. This establishes the premature classification mechanism, not the original service failure cause. Investigate a full-shape startup-only predicate, never accepting grey as ready; reject any draft, overlay or identity/status change. Existing 30-second budget remains finite; 360 seconds was the observation interval, not measured latency. No live allocation or dispatch is authorized. Independent review is pending.

<!-- fr:journal kind=repro scope=debug id=a23b8b67a8d9 created=2026-10-30T13:37:45+00:00 -->
### a23b8b67a8d9 · repro · RED: captured startup is refused before transition or second-observation guards

Focused test_opencode_rendered_readiness.py run before production edits: 12 failed, 15 passed. The captured incomplete-metadata to ready sequence fails at the first dialog-or-unfocused refusal; permanent pending cannot reach its timeout and later unsafe states are never reobserved. Both sanitized lossless viewport fixture hashes verified; the unmodified input parser rejects the initial viewport and accepts the later viewport. Negative tests compose explicit drafts/known captured overlay/unknown overlay with the real startup screen; compositions are labeled synthetic. No live API, terminal control or model call in reproduction.

<!-- fr:journal kind=root-cause scope=debug id=5a8209ef0930 created=2026-10-30T14:12:49+00:00 -->
### 5a8209ef0930 · root-cause · Confirmed classification gap: known incomplete metadata frame aborted startup wait

Current main propagated dialog-or-unfocused immediately after generic title readiness; only unknown-layout entered its bounded wait. The paired diagnostic captures and RED replay establish that a narrow empty grey metadata frame can later become strict-parser-ready without controller input or focus. This identifies a premature startup classification, not the historical service/root-cause or a measured initialization duration. The fix recognizes only the full captured empty-layout fingerprint as pending, preserves the strict parser, keeps the existing 30-second deadline and revalidates identity/session/auto/cwd/status and foreground PID each observation.

<!-- fr:journal kind=finding scope=debug id=5da3a0439361 created=2026-10-30T14:12:56+00:00 state=fixed -->
### 5da3a0439361 · finding [fixed] · Bounded metadata wait passes focused regressions; live walk and independent review remain owed

RED before production edits: 12 failed/15 passed. Added PID continuity RED: 1 failed/7 passed, then GREEN. Latest same-source verification: readiness 30, restart 57, runner 90, replacement 35, replacement observer 15 and directly relevant recovery autonomy/eligible cases 3 all pass (230 total). Ruff and scoped mypy pass. Full six-module run timed out; later full recovery module also hit its 90-second cap during unrelated cursor cases, without printed failure. Earlier replacement attempt timed out in unchanged conftest CLI import; separating that import from pytest allowed its full current-code module to pass with all fixtures/guards enabled. No historical timeout is relabeled PASS. Full suite and installed/live verification were not run. Public fixtures retain sanitized lossless viewports; synthetic draft/overlay negatives are labeled. Independent code review has NOT occurred; no review PASS, runtime install, model turn, live launch, batch recovery or issue closeout is claimed.

<!-- fr:journal kind=review scope=debug id=9e32a9a9e5a2 created=2026-10-30T16:09:10+00:00 -->
### 9e32a9a9e5a2 · review · Independent review REQUEST CHANGES at PR 1254 head 2a3af0105c834f2f15baa647a5d003f0d59d6c76

Independent report dated 2026-10-30T16:04:43Z requests changes for blocking R1 P2. Shared poll checks expiry after unsuccessful checks and accepts late success; native observations individually retain a 60-second timeout. Reviewer reproduced pending completion at 29.5s and late readiness at 31.5s being admitted under a 30-second startup budget. Other reviewed guard/parser/privacy/matrix invariants were supported; this is not review approval. Re-review remains required after resolution.
