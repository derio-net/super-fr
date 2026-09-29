# Journal: 2026-09-29-fr-goal-light-path

<!-- fr:journal kind=decision scope=plan id=p1-chain-commits-per-iteration created=2026-09-29T07:59:39+00:00 phase=1 -->
### p1-chain-commits-per-iteration · decision · _advance_chain gives each iteration its own _RunWrites, so a chained advance still commits once per step (phase 1)

`advance_cmd` is now a thin wrapper over `_advance_chain`, which runs
`_advance_once` inside a fresh `_RunWrites(verb="advance")` per iteration
and commits it in `finally`. The subjects are exactly what one
`fr run advance` per step used to write (`advance c1 done`, `advance b running`).
`resolve --record` calls the same chain after `apply_record`'s commit has
landed, so the apply commit and each advance commit stay separate (spec §B
"Commits"). `_advance_once` maps `typer.Exit(1)` to `cli-failed` and every
other exit to `refused`; prints are unchanged. The orchestrator-model notice
moved from the per-step body to once per chain.

<!-- fr:journal kind=decision scope=plan id=p1-refused-chain-after-record created=2026-09-29T07:59:39+00:00 phase=1 -->
### p1-refused-chain-after-record · decision · a refusal in the advance after an applied record exits 2 and says the record is applied (phase 1)

Spec §B names exit 1 for a chained cli failure (`record applied; <step> failed
(exit N)`) but no code for a refusal inside the chained advance (for example
the next unit already held). It exits 2 with `record applied; the advance after
it was refused (above)` so nobody re-applies the record.

<!-- fr:journal kind=discovery scope=plan id=p1-group-inline-completion-chains created=2026-09-29T07:59:39+00:00 phase=1 -->
### p1-group-inline-completion-chains · discovery · _advance_group's inline group completion returns cli-done, so the chain goes on (phase 1)

`_advance_group` completes a group with nothing left to dispatch (units
resolved before members were learned) and moves the cursor without a brief.
That is the same cursor move as a passed cli step, so it returns `cli-done` and
`_advance_chain` continues to the next step instead of stopping silently.

<!-- fr:journal kind=discovery scope=plan id=p1-record-on-last-step-does-not-advance created=2026-09-29T07:59:39+00:00 phase=1 -->
### p1-record-on-last-step-does-not-advance · discovery · resolve --record on the run's last step skips the advance (phase 1)

A `deliver` record already prints the closeout handoff; advancing a finished
run would hit `advance`'s run-complete branch and print it a second time.
`_advance_after_record` returns early when the cursor step is done and has no
successor.

<!-- fr:journal kind=discovery scope=plan id=p1-fixture-walks-take-the-chained-brief created=2026-09-29T07:59:39+00:00 phase=1 -->
### p1-fixture-walks-take-the-chained-brief · discovery · test walks that advanced past plan-review / journal-check now take the brief from the same call (phase 1)

`_drive_to_implement` (integration) and `_fr_goal_at_implement` (unit) now
return the implement-phase brief printed by the plan-review advance; their
callers stop issuing a second advance (which is refused as held). Tests about
the record apply alone (`test_record_apply._resolve`,
`test_run_evidence_visual._resolve`) pass `--no-advance`; `_at_deliver` relies
on the one-call resolve. The idle-guard test moved to a two-agent shape and the
teardown test gates its second cli step, because a cli-only shape now runs to
its end in one advance.

<!-- fr:journal kind=finding scope=plan id=p1-skill-prose-still-advances-after-record created=2026-09-29T07:59:39+00:00 phase=1 state=open review_scope=in -->
### p1-skill-prose-still-advances-after-record · finding [open] (reviewer: in scope) · fr-goal skill still says `fr run advance` after `resolve --record`; that advance is now refused as held (phase 1)

With R4 a done record already briefs the next unit, so the skill's
"then `fr run advance <run-id>` again to brief `review-phase`" (pinned by
`test_run_resolve_requires_advance.py::test_the_skill_describes_the_sequence_fr_now_enforces`)
now exits 2 (ALREADY HELD) if followed literally. Spec §B's last line ("The skill
prose drops every then `fr run advance` that follows a `resolve --record`") is
owed by the prose phase (phase 3, R7); left untouched here as out of this
phase's task list.

<!-- fr:journal kind=finding scope=plan id=r1-1 created=2026-09-29T08:18:10+00:00 phase=1 state=open review_scope=in -->
### r1-1 · finding [open] (reviewer: in scope) · _advance_once classifies any typer.Exit(1) under _advance_step as cli-failed (phase 1)

Reviewer (in scope — this change is the first to infer "cli step failed" from an exit code): run_cmd.py _advance_once read together with _advance_after_record. Correct today (the only Exit(1) on the path is the cli branch) but any future Exit(1) under _advance_step would read as a cli failure and print `record applied; <agent-step> failed (exit None)`. Fix: the cli branch returns "cli-failed"; every typer.Exit is "refused".

<!-- fr:journal kind=finding scope=plan id=r1-2 created=2026-09-29T08:18:10+00:00 phase=1 state=open review_scope=in -->
### r1-2 · finding [open] (reviewer: in scope) · Chain edge cases untested: refusal after apply, deliver-record closeout, inline group completion, --redispatch, model notice (phase 1)

Reviewer (in scope — the executor's three stated decisions and two new behaviours had no test; deleting the last-step early return or reverting group completion to "brief" stayed green). Fix: one test each.

<!-- fr:journal kind=finding scope=plan id=r1-3 created=2026-09-29T08:18:10+00:00 phase=1 state=open review_scope=in -->
### r1-3 · finding [open] (reviewer: in scope) · resolve --record exit 2 now means both 'refused, nothing applied' and 'applied, advance refused' (phase 1)

Reviewer (in scope — this change introduced the second meaning): a caller branching on exit code alone would re-apply a consumed record. Advisory; the stderr line says "record applied". Fix: name the case in the skill prose.

<!-- fr:journal kind=discovery scope=plan id=r1-deliver-record-closeout created=2026-09-29T08:18:10+00:00 phase=1 -->
### r1-deliver-record-closeout · discovery · resolve --record on deliver printed no closeout handoff at all (found while fixing r1-2) (phase 1)

resolve_in_process holds back the flag-form body's stdout, which is where the closeout handoff printed, so a record-form deliver never relayed `fr pickup --run`. Fixed in 329aa318: _resolve_record_cmd prints the handoff once after the outcome line for a done deliver; pinned by test_o.

<!-- fr:journal kind=review scope=plan id=review-phase-1 created=2026-09-29T08:18:10+00:00 phase=1 -->
### review-phase-1 · review · independent code review of phase 1: 3 findings (all in scope), all fixed (phase 1)

Reviewer ae42ae7153a2b5c23 (dispatched feature-dev:code-reviewer, opus) reviewed 97c49baa against spec §B, plan 01.yaml and the p1-* journal entries. Raised r1-1 (low), r1-2 (medium), r1-3 (low); endorsed the executor's three decisions; found loop cap, one-commit-per-step, done-only chaining, flag handling, held-unit refusals, output order and the adapted existing tests sound; no input- findings. Received: each finding verified against the code and fixed — r1-1 and r1-2 in 329aa318 (tests m–r, plus the deliver-record closeout bug), r1-3 in 393a1673 (skill prose). The pre-existing p1-skill-prose-still-advances-after-record fixed in 31eda282.

<!-- fr:journal kind=finding scope=plan id=r1-1-resolved created=2026-09-29T08:18:10+00:00 phase=1 state=fixed resolves=r1-1 -->
### r1-1-resolved · finding [fixed] · resolves r1-1: _advance_once classifies any typer.Exit(1) under _advance_step as cli-failed (phase 1)

329aa318: cli branch returns cli-failed; every typer.Exit in _advance_once is refused; test_m pins it.

<!-- fr:journal kind=finding scope=plan id=r1-2-resolved created=2026-09-29T08:18:10+00:00 phase=1 state=fixed resolves=r1-2 -->
### r1-2-resolved · finding [fixed] · resolves r1-2: Chain edge cases untested: refusal after apply, deliver-record closeout, inline group completion, --redispatch, model notice (phase 1)

329aa318: tests n (refusal after apply, exit 2, record committed), o (deliver record prints closeout once), p (inline group completion continues), q (--redispatch one brief), r (model notice once per chain).

<!-- fr:journal kind=finding scope=plan id=r1-3-resolved created=2026-09-29T08:18:10+00:00 phase=1 state=fixed resolves=r1-3 -->
### r1-3-resolved · finding [fixed] · resolves r1-3: resolve --record exit 2 now means both 'refused, nothing applied' and 'applied, advance refused' (phase 1)

393a1673: fr-goal SKILL.md names exit 1 / exit 2-with-'record applied' after an applied record and says never re-apply; mirrors synced.

<!-- fr:journal kind=finding scope=plan id=p1-skill-prose-still-advances-after-record-resolved created=2026-09-29T08:18:10+00:00 phase=1 state=fixed resolves=p1-skill-prose-still-advances-after-record -->
### p1-skill-prose-still-advances-after-record-resolved · finding [fixed] · resolves p1-skill-prose-still-advances-after-record: fr-goal skill still says `fr run advance` after `resolve --record`; that advance is now refused as held (phase 1)

31eda282: fr-goal §1/§6 say resolve --record briefs the next unit; the separate advance is gone; pinned wording updated in test_run_resolve_requires_advance.py; mirrors synced.

<!-- fr:journal kind=decision scope=plan id=p2-tree-computed-at-verification created=2026-09-29T08:35:06+00:00 phase=2 -->
### p2-tree-computed-at-verification · decision · the phase log's code tree is computed at verification, and equals the tree after the record's commit (phase 2)

`_verify_phase_tests_log` hashes HEAD's code tree while verifying, i.e. before
`apply_record`'s commit. Spec §D says "after the record's own commit"; the two
are equal by construction, because that commit (`commit_records`) stages only the
paths the record wrote — runs, records, journals, plan, matrix — all under
`FR_ARTIFACT_PREFIXES`, which the code tree excludes. The docstring states this.
An uncommitted code change at record time is not in the tree; freshness still
counts it, and deliver's reuse refuses while any code path is dirty.

<!-- fr:journal kind=decision scope=plan id=p2-freshness-without-a-merge-base created=2026-09-29T08:35:06+00:00 phase=2 -->
### p2-freshness-without-a-merge-base · decision · with no merge-base (no remote default branch), freshness counts every tracked code path (phase 2)

`newest_code_mtime(repo, None)` compares the log against every tracked code path
plus uncommitted ones, failing toward stricter, never toward "nothing changed".
The merge-base comes from `default_merge_base` (remote default ref, as
proportionality resolves it). The log file itself is ignored when it sits in the
worktree.

<!-- fr:journal kind=decision scope=plan id=p2-untracked-counts-marker-does-not created=2026-09-29T08:35:06+00:00 phase=2 -->
### p2-untracked-counts-marker-does-not · decision · untracked (non-ignored) files are dirty code paths; the `.fr-isolation` marker never is (phase 2)

`dirty_code_paths` uses `git status --untracked-files=all`: a new source file not
yet added can change what the suite runs, so reuse refuses over it. The isolation
marker is excluded by name (`ISOLATION_MARKER`) because a workspace whose
`info/exclude` lacks it (the unit-test fixture repo) would otherwise refuse every
reuse over a file that is fr's, not code.

<!-- fr:journal kind=decision scope=plan id=p2-reuse-refusal-names-paths-via-history created=2026-09-29T08:35:06+00:00 phase=2 -->
### p2-reuse-refusal-names-paths-via-history · decision · deliver's refusal counts changed paths by finding the commit whose code tree matches the witness (phase 2)

The witness stores only `tree=<sha256>` (spec format), so the "<n> paths, e.g.
<path>" in the refusal comes from `code_paths_since_tree`: the newest of HEAD's
last 200 commits whose code tree equals the recorded one, diffed to the working
tree. When no such commit is found the refusal says so instead of a count.

<!-- fr:journal kind=decision scope=plan id=p2-holder-transcript-rules created=2026-09-29T08:35:06+00:00 phase=2 -->
### p2-holder-transcript-rules · decision · a phase log's writer is the holder's transcript; a holder this session never dispatched is refused (phase 2)

`_phase_log_windows` reads `witness_transcript(session, holder)` — the subagent
transcript (all sidechain, so `wrote_since(..., main_thread=False)`) or the main
thread when the unit ran inline. `witness_transcript` returning False (a bogus or
foreign agent id) is a refusal, as for `visual`; an unreadable session, or
OpenCode/Hermes (no child-session reader, spec §D/§E), records `unobserved=tests`
after the predates-the-unit check. `orchestrator_wrote_since` is now a thin
wrapper over `wrote_since(..., main_thread=True)`.

<!-- fr:journal kind=decision scope=plan id=p2-pr-body-tests-section created=2026-09-29T08:35:06+00:00 phase=2 -->
### p2-pr-body-tests-section · decision · the PR body gains an optional `## Tests` section, rendered only when deliver carries tests evidence (phase 2)

`render_pr_body` adds `## Tests` before `## Proportionality` when `step/deliver`
has a `tests` witness: "Full suite reused from `<unit>` — `<log>@<sha>`, on code
tree `<12>`, unchanged at delivery." or "Full suite run at delivery — `<witness>`.".
It is not in `REQUIRED_SECTIONS`, so no live PR is refused for lacking it.

<!-- fr:journal kind=discovery scope=plan id=p2-deliver-suite-reuse-row-owed created=2026-09-29T08:35:06+00:00 phase=2 -->
### p2-deliver-suite-reuse-row-owed · discovery · acceptance row deliver-suite-reuse now has unit evidence; implement-phase cannot move it (phase 2)

`tests/unit/test_run_suite_reuse.py` verifies R6 (phase log recorded with its
tree, hand-written/stale/records-dir logs refused, reuse passes on an unchanged
tree and after bookkeeping-only commits, refused after a code change). The row
`deliver-suite-reuse` is still `not-implemented`; implement-phase does not emit
`acceptance`, so the move (`--status ci --level
unit=super-fr:tests/unit/test_run_suite_reuse.py`) belongs to a step that does
(deliver).
