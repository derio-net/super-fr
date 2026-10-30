<!-- fr:journal-schema=3 -->
# Journal: 2026-10-30-opencode-startup-metadata-ready

<!-- fr:journal kind=hypothesis scope=debug id=6e13d45851f3 created=2026-10-30T13:23:21+00:00 -->
### 6e13d45851f3 · hypothesis · Current main aborts unresolved startup metadata before bounded readiness can wait

Fresh origin/main bf59f77a946c retains RC11 behavior: wait_ready retries unknown-layout only and propagates dialog-or-unfocused immediately. Private paired captures of one unchanged no-focus, --auto diagnostic client show blank metadata/grey border then complete Build/model metadata and strict-parser acceptance. This establishes the premature classification mechanism, not the original service failure cause. Investigate a full-shape startup-only predicate, never accepting grey as ready; reject any draft, overlay or identity/status change. Existing 30-second budget remains finite; 360 seconds was the observation interval, not measured latency. No live allocation or dispatch is authorized. Independent review is pending.

<!-- fr:journal kind=repro scope=debug id=a23b8b67a8d9 created=2026-10-30T13:37:45+00:00 -->
### a23b8b67a8d9 · repro · RED: captured startup is refused before transition or second-observation guards

Focused test_opencode_rendered_readiness.py run before production edits: 12 failed, 15 passed. The captured incomplete-metadata to ready sequence fails at the first dialog-or-unfocused refusal; permanent pending cannot reach its timeout and later unsafe states are never reobserved. Both sanitized lossless viewport fixture hashes verified; the unmodified input parser rejects the initial viewport and accepts the later viewport. Negative tests compose explicit drafts/known captured overlay/unknown overlay with the real startup screen; compositions are labeled synthetic. No live API, terminal control or model call in reproduction.
