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

<!-- fr:journal kind=root-cause scope=debug id=claude-mcp-child-not-second-agent created=2026-10-10T02:57:36+00:00 -->
### claude-mcp-child-not-second-agent · root-cause · Claude replacement treats its native MCP sidecar as a second foreground agent

Real owned target: one Claude 2.1.296 root launched with --model haiku, idle/interactive-ready, no Claude prompt sent; its existing configured node mcp-server.cjs child is listed in the same foreground process group. Six bounded samples consistently returned both processes, so this is not a transient status-line/render wait. A real process capture confirms the foreground group equals the unique Claude root pid and both processes have the same disposable base cwd. The phase-2 observer rejects any list longer than one before inspecting Claude, conflating this initialized tool server with another agent/background job. Correct narrowly: still require exactly one Claude root and exact model/cwd/name/prompt, permit only this captured same-group/same-cwd two-argument node MCP sidecar; reject duplicate Claude roots and all unknown children. No client permissions or MCP configuration will be changed.

<!-- fr:journal kind=finding scope=debug id=captured-claude-mcp-root created=2026-10-10T03:03:03+00:00 state=open -->
### captured-claude-mcp-root · finding [open] · Narrow captured Claude/MCP foreground recognition awaits installed live confirmation

Captured the actual persistent same-group startup MCP sidecar before any Claude prompt; only runtime paths/pids were redacted while identity relations were preserved. RED observer regression failed on the original len(processes)==1 assumption. The fix selects exactly one Claude root only in the captured two-process configuration (node mcp-server.cjs, two argv entries, same cwd, foreground group equal to Claude pid), retaining all existing name/model/cwd/status/prompt/draft/background checks. Unknown children, other cwd/group, extra args and duplicate Claude roots still refuse. 214 targeted tests, ruff and mypy over 307 source files passed. No MCP or permission config changed, and no failed pre-submission target is certified merely from its model.

<!-- fr:journal kind=repro scope=debug id=claude-cold-initialization-workers created=2026-10-10T03:12:22+00:00 -->
### claude-cold-initialization-workers · repro · Claude ready title also precedes foreground initialization workers settling

A fresh OWN unprompted diagnostic Claude tab confirms this distinct timing boundary: agent start returned at +4.494s while process snapshots contained rg, short-lived unknown/argv-less processes and configured MCP bootstrappers (node/npx/vibe-kanban). Exact observer correctly refused every ambiguous sample. At +9.032s only the unique Claude root plus the captured native MCP server remained, and the unchanged qualified observer passed without any prompt/focus/native-key action. Diagnostic tab was closed. This confirms target validation must wait boundedly for the existing safe predicate, not accept additional unknown children or bypass process checks.

<!-- fr:journal kind=discovery scope=debug id=bounded-claude-target-settle created=2026-10-10T03:16:56+00:00 -->
### bounded-claude-target-settle · discovery · Wait for the captured safe Claude predicate rather than accepting initialization workers

The cold diagnostic confirmed +4.494s title readiness versus +9.032s qualified process/prompt readiness. A failing targeted test reproduced unknown startup workers before the captured stable Claude/MCP pair. launch_target now polls boundedly only for ambiguous foreground/no-prompt startup observations, retaining the exact safe predicate; all other draft/dialog/status/model/cwd/name errors still refuse. A second regression pins timeout without any prompt/key input. 94 affected tests passed, ruff/mypy green. The known MCP recognition and this settle wait will now be verified together on a fresh installed candidate; no unseen behavior is marked passed.

<!-- fr:journal kind=root-cause scope=debug id=post-uptake-workers-block-activation created=2026-10-10T03:28:13+00:00 -->
### post-uptake-workers-block-activation · root-cause · Post-uptake activation incorrectly reuses pre-input foreground-work exclusion

The fresh candidate now qualified the Claude target, submitted the recovery brief, confirmed activity and atomically saved batch success/launch. Descriptor activation then refused ambiguous foreground process while the confirmed Claude target was doing its requested read-only recovery inspections. After that turn settled, explicit repair finalized the descriptor without another success event or any prompt/start. Source input eligibility must remain strict, but post-uptake activation is read-only identity confirmation and already explicitly allows working/blocked status. It should require one exact expected root process in its foreground group, model/name/pane/base cwd intact, without mistaking that confirmed target own task children for another agent. Duplicate roots, wrong group/model/name remain refusals; no eligibility weakening before any prompt.

<!-- fr:journal kind=discovery scope=debug id=activation-versus-input-safety created=2026-10-10T03:32:14+00:00 -->
### activation-versus-input-safety · discovery · Keep strict input readiness separate from read-only post-uptake identity

A failing regression pins the actual post-uptake task-worker case. Read-only identity observation now selects a unique expected harness root only when its pid is the foreground group leader; full model/name/pane/cwd/status checks still apply. Safe input observation remains unchanged and refuses those workers, duplicate roots and unknown source states. This is used only for existing non-input activation/diagnostic observations; repair still requires persisted uptake. 141 targeted tests, ruff and mypy passed. Real combined candidate replacement will be rerun before claiming completion.

<!-- fr:journal kind=finding scope=debug id=captured-wide-sidebar-input-resolved created=2026-10-10T03:35:24+00:00 state=fixed resolves=captured-wide-sidebar-input -->
### captured-wide-sidebar-input-resolved · finding [fixed] · resolves captured-wide-sidebar-input: Captured wide-session textarea geometry fix awaits installed live preview

Fresh installed 039b07d3 real wide-session replacement preview now passes with byte-identical fixture batch state and no keys; the old 82d755cf preview had refused the same idle sidebar. Real captured draft/palette negative cases remain unit-pinned; actual final-candidate refusal cases will be repeated. No arbitrary layout/theme was accepted.

<!-- fr:journal kind=finding scope=debug id=captured-claude-mcp-root-resolved created=2026-10-10T03:35:27+00:00 state=fixed resolves=captured-claude-mcp-root -->
### captured-claude-mcp-root-resolved · finding [fixed] · resolves captured-claude-mcp-root: Narrow captured Claude/MCP foreground recognition awaits installed live confirmation

Fresh combined candidate aa48026f confirmed real Claude target startup, prompt uptake, active descriptor and model-only haiku-to-sonnet replacement with original pane/name/dispatch/branch/reservation unchanged. The captured native MCP sidecar is recognized; cold initialization workers are waited out and working-target activation now checks identity rather than input safety. Unknown/duplicate source roots still refuse. No MCP configuration/permissions changed.

<!-- fr:journal kind=finding scope=debug id=unknown-model-falls-back-native-client created=2026-10-10T04:04:59+00:00 state=open -->
### unknown-model-falls-back-native-client · finding [open] · Native OpenCode accepted unknown requested model but displayed a different model

The deliberate disposable bad-start request used syntactically valid missing-provider/1089-disposable-not-a-model. Native OpenCode did not fail startup: process argv retained that --model value, real candidate observed uptake and wrote launch success, but the captured live session showed Build · GPT-5.6 Sol. This is NOT counted as an induced startup-failure pass. Native requested-argument versus actual selected-provider/model semantics are not confidently understood enough to fix unasked; process argv alone did not establish the UI model in this negative case. No provider/forge response was faked. The natural owned Claude trust-startup failure and later source-exit/confirmed-shell repairs were separately observed, with no replay, but the intentional bad-model startup-failure subcase remains unproven. Full accepted client-live verdict is withheld.
