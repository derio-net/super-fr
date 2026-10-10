# Journal: 2026-10-10-herdr-opencode-uptake

<!-- fr:journal kind=repro scope=debug id=live-startup-stall created=2026-10-10T01:54:29+00:00 -->
### live-startup-stall · repro · Authorized live walk stalled before first OpenCode prompt uptake

Final candidate b348f8b2 launched real OpenCode with selected model at stable base and Herdr reported ready, but two dispatched initial prompts returned agent_prompt_stalled after five seconds and captured screen remained empty home prompt. Owned fixture processes/workspaces were closed, source transcripts retained; no passing live verdict. Reuse feat/1089 and draft1115, no new PR; investigate startup/render versus submission before fixing.

<!-- fr:journal kind=hypothesis scope=debug id=rendered-readiness-before-first-prompt created=2026-10-10T01:55:40+00:00 -->
### rendered-readiness-before-first-prompt · hypothesis · Herdr title readiness may precede the rendered OpenCode input surface

Single hypothesis to test before any fix: agent start reports interactive-ready on initial title/process detection before OpenCode has rendered its focused empty textarea. Compare timestamped start return, grounded screen/process/name/model readiness, then ONE benign HOLD submission through the unchanged installed-candidate runner submission path. All targets are newly owned disposable panes; no replay on an uncertain existing submission. Prior failed source panes were closed and inspected; the earlier successful grounding waited for a rendered placeholder.

<!-- fr:journal kind=root-cause scope=debug id=ready-title-before-rendered-textarea created=2026-10-10T01:58:43+00:00 -->
### ready-title-before-rendered-textarea · root-cause · Herdr returns title-based OpenCode readiness before the usable input surface

Confirmed with a REAL disposable OpenCode 1.18.35 pane, Herdr 0.9.0, unchanged candidate runner submission transport and no focus/native-key changes. agent start returned at +4.406s; exact live name/pane/model/foreground cwd checks passed but grounded input observation reported unknown-layout from +4.480s through +9.163s. At +9.741s the focused empty rendered prompt became eligible. ONE benign read-only HOLD turn through the original runner._submit --wait working/blocked path then confirmed activity at +11.507s and settled successfully. Earlier immediate submissions stalled at the same pre-render interval. Readiness based on the terminal title is therefore insufficient for prompt submission. Redacted timestamped screen/process evidence is in the approved host 1089-client-live-observed.log; all controls targeted only owned fixture panes.

<!-- fr:journal kind=ruled-out scope=debug id=focus-or-forwarding-not-required created=2026-10-10T01:58:47+00:00 -->
### focus-or-forwarding-not-required · ruled-out · No focus change, payload transport change or extra Enter was needed

The successful controlled trial kept workspace/tab creation --no-focus, used the identical installed candidate runner._submit agent prompt flags and real Herdr forwarding, and sent no native Enter retry. Exact process/name/model/cwd plus grounded rendered textarea readiness was the only precondition added. This rules out required focus switching or an unconditional extra Enter as the remedy for this reproduced startup failure; unknown submissions still must never be replayed.

<!-- fr:journal kind=finding scope=debug id=bounded-rendered-readiness-wait created=2026-10-10T02:09:23+00:00 state=open -->
### bounded-rendered-readiness-wait · finding [open] · Shared startup render readiness fix awaits fresh installed live confirmation

TDD reproduced all three unsafe pre-render prompt paths: initial dispatch stalled, managed restart failed submission, replacement failed target observation. Added one bounded opencode.wait_ready predicate shared by dispatch/restart/replacement; it reuses grounded eligibility under exact foreground/name/model/base cwd, retries only unknown startup layout, rejects drafts/dialogs/identity drift, and never promotes pending descriptors or retries Enter. Eight readiness regressions now pass; affected managed/replacement/runner group is 216 passed, ruff green. Next verify freshly installed candidate real first launch/uptake, then continue six-item client-live walk. No full local suite or delivery cursor mutation.

<!-- fr:journal kind=finding scope=debug id=bounded-rendered-readiness-wait-resolved created=2026-10-10T02:19:29+00:00 state=fixed resolves=bounded-rendered-readiness-wait -->
### bounded-rendered-readiness-wait-resolved · finding [fixed] · resolves bounded-rendered-readiness-wait: Shared startup render readiness fix awaits fresh installed live confirmation

Fresh host candidate 82d755cf installed into its own prefix and real first OpenCode dispatch now passes without focus or native-key changes: agent start at 04:18:06, grounded render gate before prompt at 04:18:15, confirmed prompt activity and active managed descriptor at 04:18:17. Name/pane/model and stable base identity are preserved. Root-cause fix is verified live; the remaining six-item client-live behaviors are still being exercised, not accepted by this resolution.

<!-- fr:journal kind=repro scope=debug id=idle-sidebar-layout-refusal created=2026-10-10T02:27:34+00:00 -->
### idle-sidebar-layout-refusal · repro · Fresh launch now succeeds but idle wide-session replacement preview is refused

After the verified render-readiness fix, the real owned OpenCode session completed the read-only sleep/HOLD turn. Real name/model/base process identity and done/interactive-ready state match. Candidate replacement preview correctly sends no keys but returns unknown-layout. Actual wide-session screen has a focused empty textarea whose closing border shares its row with the right sidebar cwd text; the old closing-border regex requires the entire row to be only border/whitespace. Raw capture and plain nonblank row excerpt are in the redacted host evidence log. Investigate this captured geometry before widening recognition.

<!-- fr:journal kind=root-cause scope=debug id=sidebar-outside-input-boundary created=2026-10-10T02:27:38+00:00 -->
### sidebar-outside-input-boundary · root-cause · Closing-border recognition and draft width incorrectly include the session sidebar

Source-traced against the real captured wide idle screen: input_reason uses the full-row ^whitespace+closing-border+whitespace$ predicate, so actual cwd text outside the closing border prevents locating the focused input at all. The process/name/model and focused blue border are correct. The fix must derive the input width from the captured border span, not the full sidebar-bearing row, and require the captured wide-session version footer; preserve draft/palette refusal using real negative captures. This is a separate grounded geometry defect, not a failed iteration of the confirmed startup timing fix.

<!-- fr:journal kind=finding scope=debug id=captured-wide-sidebar-input created=2026-10-10T02:38:04+00:00 state=open -->
### captured-wide-sidebar-input · finding [open] · Captured wide-session textarea geometry fix awaits installed live preview

Real wide idle/draft/palette viewport captures were taken once before the parser change, same-width runtime identifiers redacted, and original compressed captures moved through edit tools into tests/fixtures/herdr/opencode/wide-*.json. Decompressed SHA-256 checks protect exact capture bytes. RED positive idle and explicit draft tests exposed the full-row border/width defect; GREEN now measures only the captured border span and permits sidebar suffix only with the captured wide-session OpenCode version footer. Draft/palette and a synthetic unknown footer remain refusals. 171 affected tests passed, ruff green. This is grounded recognition of the existing native sidebar, not a guessed layout or acceptance verdict.
