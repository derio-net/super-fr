# Journal: 2026-09-14-ste-output-tone

<!-- fr:journal kind=decision scope=spec id=d1-scope created=2026-09-14T21:28:07 -->
### d1-scope · decision · Scope: agent replies + skill-prescribed text

Operator chose agent chat replies plus the text skills tell the agent to write (announcements, status reports, PR bodies, journal entries, phase-executor returns). fr CLI and hook messages are out of scope.

<!-- fr:journal kind=decision scope=spec id=d2-activation created=2026-09-14T21:28:18 -->
### d2-activation · decision · Activation: forced plugin output style + shipped rule

Plugin output style with force-for-plugin: true and keep-coding-instructions: true (Claude Code main thread and forks). The same rules ship as plugins/super-fr/rules/ for subagents, OpenCode and Hermes, because output styles do not reach them.

<!-- fr:journal kind=decision scope=spec id=d3-insights created=2026-09-14T21:28:28 -->
### d3-insights · decision · Explanatory plugin: keep only the Insight blocks

Operator: 'can we only keep the Insight blocks? If not, keep both'. Feasible: explanatory-output-style is a SessionStart additionalContext hook, not an output style, so no force-for-plugin collision. The STE style keeps Insight blocks when another instruction asks for them, writes them in STE, and cancels any permission to exceed length limits.

<!-- fr:journal kind=decision scope=spec id=d4-test-plan created=2026-09-14T21:28:38 -->
### d4-test-plan · decision · Test Plan: operator walk + CI tests

Post-merge: operator updates plugin, restarts, runs one fr skill, checks the reply against the STE checklist. Pre-merge: unit tests pin the style file, the rule, and their wiring into every harness.

<!-- fr:journal kind=decision scope=spec id=d5-no-dictionary created=2026-09-14T21:28:48 -->
### d5-no-dictionary · decision · No ASD dictionary; paraphrased writing rules only

Agent decision, not operator-owned: ASD-STE100 Issue 9 is free to obtain but permits reproduction only with ASD written authority. The style paraphrases the STE writing-rule principles and does not ship the approved-word list or verbatim rule text.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-09-14T21:38:09 -->
### spec-review-1 · review · Spec review: 4 findings, all fixed

Checked against Q&A d1-d4 and the codebase. All named files and tests exist; fr validate artifacts and fr acceptance check pass. R1 scope creep: §5.A listed commit message bodies, not in d1 — removed. R2 ambiguous identity test: 'after the header' had no boundary — added ste-shared start/end markers (§3, §5.E.2). R3 filler test matched its own quoted examples — test strips double-quoted strings first (§5.E.4). R4 missing risk: Claude Code without force-for-plugin support — added to §6, detected by Test Plan step 2.
