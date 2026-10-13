# Journal: 2026-10-11-batch-adopt-safety-2

<!-- fr:journal kind=discovery scope=plan id=p1-scenario-origin-shim created=2026-10-11T20:56:14+00:00 phase=1 -->
### p1-scenario-origin-shim · discovery · adopt scenario needs a git shim for origin (phase 1)

fr requires `remote get-url origin` to look like the batch's forge repo, and `get-url` applies insteadOf, so an offline clone cannot satisfy both that and fetch. tests/scenarios/fixtures/triage-adopt/bin/git answers only that call; every other git call is the real git.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-10-11T20:56:14+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

RED-only task (tests added); nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-10-11T20:56:14+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

adopt_message and the plan/step wiring were written once, with _pr_ref hoisted above the plan so plan and send share it; nothing duplicated left

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-10-11T20:56:14+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

scenario, fragment and matrix move only; no production code to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-10-11T20:56:14+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

no existing harness-mapping helper in fr_herdr.restart is reusable (it only checks for claude/opencode kinds in-line); runner.py gets one small _HARNESSES map

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-10-11T21:00:32+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · stop-report re-run command interpolates --checkout (and ids) unquoted (phase 1)

triage_batch_cmd.py stop report: a path with spaces gives a broken copy-paste command. Fix: shlex.quote.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-10-11T21:00:32+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · stop-report test lacks a negative case (phase 1)

Only the both-flags case was tested; an always-echoed --no-hold would silently un-hold a re-run.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-10-11T21:00:32+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · herdr _agent_cwd/_agent_session duplicate restart.py's reads; P1.T4.S3 outcome unrecorded (phase 1)

runner.py's helpers repeat restart.py:532/537.

<!-- fr:journal kind=review scope=plan id=p1-review-1 created=2026-10-11T21:00:32+00:00 phase=1 -->
### p1-review-1 · review · Phase 1 code review (phase 1)

Dispatched read-only reviewer checked R1-R4, R10 and the R9 flag echo against spec §A/§C, ran the adopt and herdr tests and the hold scenario. Raised p1-r1..p1-r3, all in scope; all fixed (shlex-quoted re-run args, negative stop-report test, agent_cwd/agent_session moved to fr_herdr._herdr and shared by runner and restart).

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-10-11T21:00:32+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: stop-report re-run command interpolates --checkout (and ids) unquoted (phase 1)

Stop report quotes batch id, tab, branch and --checkout with shlex.quote.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-10-11T21:00:32+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: stop-report test lacks a negative case (phase 1)

Added test_the_stop_report_echoes_neither_flag_when_not_given.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-10-11T21:00:32+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: herdr _agent_cwd/_agent_session duplicate restart.py's reads; P1.T4.S3 outcome unrecorded (phase 1)

agent_cwd/agent_session now live in fr_herdr._herdr, used by both runner.list_sessions and restart; this is P1.T4.S3's refactor.

<!-- fr:journal kind=decision scope=plan id=p2-reusable-workspace-takes-ahead created=2026-10-11T21:29:20+00:00 phase=2 -->
### p2-reusable-workspace-takes-ahead · decision · reusable_workspace takes the caller's ahead count instead of running git (phase 2)

The spec gives `reusable_workspace(repo_root, branch, session_id)`. It now takes a keyword `ahead: int`: the command computes it with the new `Checkout.ahead` (the max of the local branch and `origin/<branch>` against `origin/<default>`), so `fr.isolation.adopt` runs no git and never imports `fr.triage.gitseam`, and the git read stays in the seam the spec names for it.

<!-- fr:journal kind=decision scope=plan id=p2-two-extra-seam-reads created=2026-10-11T21:29:20+00:00 phase=2 -->
### p2-two-extra-seam-reads · decision · adopt.workspace_path and Checkout.current_branch added beyond the plan's list (phase 2)

The plan prints the workspace path before `--yes`, so `fr.isolation.adopt` gains `workspace_path(repo_root, branch)` (the recorded worktree, else `types.default_worktree_path`, which `local.py` now also uses), and `_ISOLATION_ALLOWED` admits it with the other three adopt imports. R7's first refusal names the branch the base clone is on, read by a new `Checkout.current_branch()` (None when detached), which phase 3's listing can reuse. Both have unit tests.

<!-- fr:journal kind=discovery scope=plan id=p2-default-refusal-test-retired created=2026-10-11T21:29:20+00:00 phase=2 -->
### p2-default-refusal-test-retired · discovery · the old default-branch refusal test was removed and its matrix anchor re-pointed (phase 2)

`test_triage_batch_adopt.py::test_the_default_branch_is_refused` pinned the behaviour R5 replaces. It is deleted; row `triage-batch-adopt-refusals` now cites `test_triage_batch_adopt_default.py#test_the_base_clone_is_left_untouched` (via `fr acceptance set-status --drop-level/--level`), and `fr acceptance check` passes.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-10-11T21:29:20+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

three small read methods, each one git call in the main worktree; nothing duplicated to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-10-11T21:29:20+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

the seam's five functions are thin wrappers over sessions/types; the one duplication it would have caused (the default worktree path) was extracted at once as types.default_worktree_path, now used by local.py's _worktree_up_core too

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t3 created=2026-10-11T21:29:20+00:00 phase=2 -->
### no-refactor-p2-t3 · discovery · no-refactor-because P2.T3 (phase 2)

RED-only task (tests added); nothing to clean

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-10-11T21:46:34+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · cwd refusal accepts an agent in any linked worktree of the clone (phase 2)

Only main_worktree was compared; an agent on feat/foo adopted with a mistaken --branch main would be stranded.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-10-11T21:46:34+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · enter_workspace resumes via up(path=None) (phase 2)

A workspace recorded at a non-default path failed worktree add on every re-run and lost its session bindings.

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-10-11T21:46:34+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · bind_session misses ValueError from a corrupt state record (phase 2)

pydantic ValidationError stopped adopt instead of warning.

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-10-11T21:46:34+00:00 phase=2 state=open review_scope=in -->
### p2-r4 · finding [open] (reviewer: in scope) · current_branch uses rev-parse --abbrev-ref (phase 2)

Yields heads/main on an ambiguous ref (a tag named main), falsely refusing.

<!-- fr:journal kind=finding scope=plan id=p2-r5 created=2026-10-11T21:46:34+00:00 phase=2 state=open review_scope=in -->
### p2-r5 · finding [open] (reviewer: in scope) · triage-batch-adopt-refusals notes overwritten (phase 2)

Lost the description of the phase-1 refusals.

<!-- fr:journal kind=finding scope=plan id=p2-r6 created=2026-10-11T21:46:34+00:00 phase=2 state=open review_scope=in -->
### p2-r6 · finding [open] (reviewer: in scope) · missing command-level tests for R7 reuse and cwd rules (phase 2)

No tests for bound-session reuse with commits, a remote-only batch branch, or cwd in a linked worktree.

<!-- fr:journal kind=finding scope=plan id=p2-r7 created=2026-10-11T21:46:34+00:00 phase=2 state=open review_scope=out -->
### p2-r7 · finding [open] (reviewer: out of scope) · resume picks the backend from FR_ISOLATION_TARGET, not the workspace's recorded mode (phase 2)

isolation_cmd._target reads the env even for an existing workspace (gh#569 wants the recorded mode).

<!-- fr:journal kind=review scope=plan id=p2-review-1 created=2026-10-11T21:46:34+00:00 phase=2 -->
### p2-review-1 · review · Phase 2 code review (phase 2)

Dispatched read-only reviewer verified R7 ordering, R8 untouched base clone, R9 resume, R6 message, the closed tripwire allowance and the refactor's phase-1 parity; raised p2-r1..p2-r6 in scope (all fixed with tests in 4a98cad6 / c282122b) and p2-r7 out of scope.

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-10-11T21:46:34+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: cwd refusal accepts an agent in any linked worktree of the clone (phase 2)

_refuse_agent_elsewhere accepts cwd only inside the main worktree or the batch branch's recorded workspace; refused/accepted tests added.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-10-11T21:46:34+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: enter_workspace resumes via up(path=None) (phase 2)

enter_workspace passes path=Path(recorded.worktree) to up; custom-path resume test keeps the binding.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-10-11T21:46:34+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: bind_session misses ValueError from a corrupt state record (phase 2)

bind_session also catches ValueError; tested.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-10-11T21:46:34+00:00 phase=2 state=fixed resolves=p2-r4 -->
### p2-r4-resolved · finding [fixed] · resolves p2-r4: current_branch uses rev-parse --abbrev-ref (phase 2)

current_branch uses symbolic-ref -q HEAD; tested with a tag named main.

<!-- fr:journal kind=finding scope=plan id=p2-r5-resolved created=2026-10-11T21:46:34+00:00 phase=2 state=fixed resolves=p2-r5 -->
### p2-r5-resolved · finding [fixed] · resolves p2-r5: triage-batch-adopt-refusals notes overwritten (phase 2)

Phase-1 notes restored with the default-branch sentence appended via fr acceptance set-status; reports regenerated; fr acceptance check passes.

<!-- fr:journal kind=finding scope=plan id=p2-r6-resolved created=2026-10-11T21:46:34+00:00 phase=2 state=fixed resolves=p2-r6 -->
### p2-r6-resolved · finding [fixed] · resolves p2-r6: missing command-level tests for R7 reuse and cwd rules (phase 2)

Tests added: bound workspace with commits reused, origin-only batch branch refused, cwd cases.

<!-- fr:journal kind=finding scope=plan id=p2-r7-resolved created=2026-10-11T21:46:34+00:00 phase=2 state=open resolves=p2-r7 out_of_scope=true -->
### p2-r7-resolved · finding [out-of-scope] · resolves p2-r7: resume picks the backend from FR_ISOLATION_TARGET, not the workspace's recorded mode (phase 2)

Not caused by this change: the spec chose fr isolation up's own backend selection, and `fr isolation up` itself resumes by FR_ISOLATION_TARGET the same way; belongs to isolation up's resume (gh#569 territory).

<!-- fr:journal kind=decision scope=plan id=p3-list-output-not-rich created=2026-10-11T22:26:42+00:00 phase=3 -->
### p3-list-output-not-rich · decision · adopt --list writes with typer.echo, not the rich console (phase 3)

The rich console expands tabs to spaces, which breaks the tab-separated columns (R11); typer.echo keeps them literal. The header and every row go through it.

<!-- fr:journal kind=decision scope=plan id=p3-facts-branch-is-worktree-head created=2026-10-11T22:26:42+00:00 phase=3 -->
### p3-facts-branch-is-worktree-head · decision · Checkout.facts branch is the HEAD of the agent's own worktree (phase 3)

R13 says the session's current branch; an agent may sit in a linked worktree, so facts uses head_branch (the worktree at cwd), not current_branch (the main worktree). main_worktree is returned separately for the fr-workspace lookup.

<!-- fr:journal kind=discovery scope=plan id=p3-scenario-fixtures-projected created=2026-10-11T22:26:42+00:00 phase=3 -->
### p3-scenario-fixtures-projected · discovery · scenario gh fixtures are projections of captured REST payloads (phase 3)

tests/scenarios/fixtures/triage-adopt-list/ pulls-head.json and issue-N.json keep only the fields the REST client reads, projected from tests/fixtures/github_rest captures with the repo renamed to example-org/widgets; the PR-flavoured issue payload adds the pull_request key GitHub's issues route carries on a PR.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t1 created=2026-10-11T22:26:42+00:00 phase=3 -->
### no-refactor-p3-t1 · discovery · no-refactor-because P3.T1 (phase 3)

pure helpers were written once, small and side-effect free; nothing duplicated to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t2 created=2026-10-11T22:26:42+00:00 phase=3 -->
### no-refactor-p3-t2 · discovery · no-refactor-because P3.T2 (phase 3)

Checkout.facts reuses origin_url, default_branch, main_worktree and _head_branch; ref_kind is one short method per client

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t4 created=2026-10-11T22:26:42+00:00 phase=3 -->
### no-refactor-p3-t4 · discovery · no-refactor-because P3.T4 (phase 3)

scenario, skill sentence, mirrors and matrix move only; no production code to clean

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-10-11T22:35:07+00:00 phase=3 state=open review_scope=in -->
### p3-r1 · finding [open] (reviewer: in scope) · parse_refs reads feat-#12 as a named ref (phase 3)

_ANY_REF let a name end in '-' or '.', so a hyphen-prefixed bare #n printed as an unresolved feat-#12 (?).

<!-- fr:journal kind=review scope=plan id=p3-review-1 created=2026-10-11T22:35:07+00:00 phase=3 -->
### p3-review-1 · review · Phase 3 code review (phase 3)

Dispatched read-only reviewer verified R11-R18 (header, state precedence, workspace/PR/ref lookups with once-per-key memoisation, per-row failure isolation, ref_kind on every client with @_hosted, Checkout.facts, import direction, exact _ISOLATION_ALLOWED growth, SKILL.md sentence and the origin/main merge keeping both sides, scenario fixtures redacted). Raised p3-r1, in scope; fixed with a test.

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-10-11T22:35:07+00:00 phase=3 state=fixed resolves=p3-r1 -->
### p3-r1-resolved · finding [fixed] · resolves p3-r1: parse_refs reads feat-#12 as a named ref (phase 3)

Names must end in a word character and a bare #n may follow a hyphen; test_parse_refs_reads_a_hyphen_prefixed_number_as_bare.

<!-- fr:journal kind=finding scope=plan id=p2-r7-resolved-2 created=2026-10-13T00:01:59+00:00 state=open resolves=p2-r7 tracked_by=https://github.com/derio-net/super-fr/issues/1166 -->
### p2-r7-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1166] · resolves p2-r7: resume picks the backend from FR_ISOLATION_TARGET, not the workspace's recorded mode

Filed at archive as https://github.com/derio-net/super-fr/issues/1166.
