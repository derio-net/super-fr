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
