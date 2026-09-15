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

<!-- fr:journal kind=decision scope=spec id=d6-reframe created=2026-09-15T20:16:43 -->
### d6-reframe · decision · Reframe: chattiness problem first, STE is one opt-in answer

Operator, 2026-09-15: a forced style plus a global rule touches everything a super-fr user does and needs exceptions for other skills and Claude settings, so results stay non-deterministic. The skill audit and the artifact lint are prerequisites that should have come before the STE solution. Extend this spec and branch in place; no follow-up PRs.

<!-- fr:journal kind=decision scope=spec id=d7-repurpose created=2026-09-15T20:16:49 -->
### d7-repurpose · decision · Repurpose PR 474: remove forced style and rule, keep opt-in style

Remove the ste-output-tone rule and its wiring (install.sh, OpenCode mirror, Hermes SOUL block, AGENTS.md), the fr-phase-executor STE line, and force-for-plugin. Keep the STE output style as opt-in (selected in /config) with its tests. Supersedes d2. Keep the hermetic test fix 97e0b32 in this branch.

<!-- fr:journal kind=decision scope=spec id=d8-skill-audit created=2026-09-15T20:16:55 -->
### d8-skill-audit · decision · Skill audit: remove mid-run status reports and per-row presentation

Operator selected: mid-run status reports (fr-goal, fr-debugging report at gates, blocks and the end only) and row presentation (fr-brainstorming and fr-acceptance present new rows as a short table). Not selected: PR body sections, announce lines.

<!-- fr:journal kind=decision scope=spec id=d9-lint created=2026-09-15T20:17:03 -->
### d9-lint · decision · Artifact lint: warn only, journal entries and plans

fr journal add and fr plan self-review print warnings for sentences over 25 words and filler words. Nothing fails. The plan's spec is checked by the same function in fr plan self-review.

<!-- fr:journal kind=decision scope=spec id=d10-measure-and-reports created=2026-09-15T20:17:19 -->
### d10-measure-and-reports · decision · Baseline measurement and result-plus-next-step reports

Record the 2026-09-15 baseline in the spec (11 super-fr sessions: 68% end-of-turn words, 31% narration, 2% Insight, about 23 words per tool call; transcript gaps noted) and re-measure on a new fr-goal session after merge. fr-goal operator updates are the result in 1-3 lines, then the next step; full evidence goes to the journal and PR body.

<!-- fr:journal kind=review scope=spec id=spec-review-rev2 created=2026-09-15T20:26:12 -->
### spec-review-rev2 · review · Revised spec review: 1 finding, fixed

Checked the revised spec against d6-d10 and the codebase. Code claims hold: plan_cmd exits 1 only on error issues; Plan (fr/parser.py) has dir, repo_root, prose, prose_path() and spec_path; journal add writes through err_console-capable code; both sync scripts delete a mirror whose source is gone; fr-goal is at the 120-line cap; explainer 01-fr-goal.md:329 stays true with a defense column. R5-1: the spec had 5 sentences over 25 words, so it failed its own lint. Fixed by splitting them; a re-check finds 0.
