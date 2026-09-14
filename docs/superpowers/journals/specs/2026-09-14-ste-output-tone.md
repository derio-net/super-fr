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
