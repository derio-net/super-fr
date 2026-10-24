<!-- fr:journal-schema=3 -->
# Journal: opencode-v2-readiness

<!-- fr:journal kind=repro scope=debug id=v2-readiness-repro created=2026-10-24T20:04:36+00:00 -->
### v2-readiness-repro · repro · OpenCode 2.1.4 blank prompt is rejected by RC9

On 2026-10-24, the live disposable fixture C OpenCode 2.1.4 screen showed a focused blank prompt, Build auto and V2 footer controls, but no 1.18.35 footer. Published RC9 returned unknown-layout. The sanitized lossless capture is tests/fixtures/herdr/opencode/v2-2.1.4-idle.json; the regression failed before the fix. Existing 1.18.35 capture remains accepted.
