<!-- fr:journal-schema=3 -->
# Journal: opencode-v2-readiness

<!-- fr:journal kind=repro scope=debug id=v2-readiness-repro created=2026-10-24T20:04:36+00:00 -->
### v2-readiness-repro · repro · OpenCode 2.1.4 blank prompt is rejected by RC9

On 2026-10-24, the live disposable fixture C OpenCode 2.1.4 screen showed a focused blank prompt, Build auto and V2 footer controls, but no 1.18.35 footer. Published RC9 returned unknown-layout. The sanitized lossless capture is tests/fixtures/herdr/opencode/v2-2.1.4-idle.json; the regression failed before the fix. Existing 1.18.35 capture remains accepted.

<!-- fr:journal kind=root-cause scope=debug id=v2-readiness-root-cause created=2026-10-24T20:04:48+00:00 -->
### v2-readiness-root-cause · root-cause · Observer hard-codes the legacy footer instead of validating V2 prompt structure

fr_herdr.opencode.input_reason recognized the final focused bounded textarea only when the footer ended with literal 1.18.35 and contained ctrl+p commands. OpenCode 2.1.4 changes that footer to a current-session row containing shift+tab agents, ctrl+p commands, and workspace/branch state; the actual screen retains the focused border and bounded prompt region. Herdr idle status and selected model are not sufficient evidence. The safe correction retains the legacy signature and accepts only the captured V2 footer plus focused textarea/model selector, while refusing drafts, busy screens, unknown footer layouts, and permission/search/plugin overlays.

<!-- fr:journal kind=finding scope=debug id=v2-readiness-fix created=2026-10-24T20:06:53+00:00 state=fixed -->
### v2-readiness-fix · finding [fixed] · Add a fail-closed V2.1.4 focused-prompt fingerprint

Added the live 2.1.4 screen as a hash-verified sanitized fixture. input_reason now retains the strict 1.18.35 footer route and recognizes only the observed V2 footer in addition to the existing focused closing border, Build auto/Plan model selector, and bounded empty prompt region. Added refusals for permission, search-provider setup, plugin errors, busy indicators, malformed footer, and an eligibility integration case proving Herdr idle status alone does not authorize input. Existing 1.18.35 capture tests continue to pass. Overlay-dismissal attribution remains unknown and lifecycle hooks from the failed plugin are not claimed.
