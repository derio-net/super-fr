# Journal: 2026-10-11-batch-adopt-safety-2

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-10-11T18:48:13+00:00 input=true -->
### operator-brief · discovery · Batch adopt-safety-2 brief (#1081, #1069, #1071), verbatim

batch adopt: hold adopted agents, adopt sessions on main, better --list

Batch `adopt-safety-2` of derio-net/super-fr: 3 issues, delivered as ONE pull request.

## super-fr#1081: triage batch adopt: the R6 message sets adopted agents working; add --hold
Confirmed: the adopt message still says the session is `driven by fr triage batch drive` (`triage_batch_cmd.py:1730`) with no hold; 3 of 9 idle agents started work unasked (one pushed, one merged main).

## super-fr#1069: triage batch adopt: a session on the default branch cannot be adopted
`triage_batch_cmd.py:1581` still refuses the default branch. Held by scope `s-c8805331` (its driver stopped refreshing 2026-10-09 ~20:05 UTC; operator released these to this scope 2026-10-10) (batch `adopt-safety-and-discovery`).

## super-fr#1071: triage batch adopt --list: show branch, workspace and PR, and recognise all ref shapes
`adopt --list` found refs for 3 of 42 tabs, 2 wrong. Held by scope `s-c8805331` (its driver stopped refreshing 2026-10-09 ~20:05 UTC; operator released these to this scope 2026-10-10).

## Why these belong together
Re-run of adopt-safety, whose dispatch failed on 2026-10-11 (herdr: the brief was never submitted, no turn began). Adopt's message set idle agents working unasked.

## Delivery rules
- Work on branch `feat/batch-adopt-safety-2`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#1081
  Closes derio-net/super-fr#1069
  Closes derio-net/super-fr#1071
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

<!-- fr:journal kind=decision scope=spec id=hold-default created=2026-10-11T18:48:13+00:00 -->
### hold-default · decision · Hold is the default; --no-hold opts out

Operator chose: adopt's message always ends with an explicit hold (acknowledge only; no commits, merges, migrations, pushes or pipeline runs; wait for the operator); `--no-hold` drops it. Matches the operator's 'nothing without express confirmation' rule. (R1-R4)

<!-- fr:journal kind=decision scope=spec id=default-branch-cuts-workspace created=2026-10-11T18:48:13+00:00 -->
### default-branch-cuts-workspace · decision · A default-branch session gets a new fr workspace; dirty base clone refused

Operator chose: adopt runs the in-process `fr isolation up --branch feat/batch-<id>` from origin/<default>, binds the agent's session, and the held message names the workspace path for the agent to move to. A dirty base clone is refused; uncommitted work is never carried. (R5-R9)

<!-- fr:journal kind=decision scope=spec id=unpushed-default-refused created=2026-10-11T18:48:13+00:00 -->
### unpushed-default-refused · decision · Unpushed commits on the local default branch are refused

Operator chose: commits on local <default> that origin lacks refuse the adoption, listing them; adopt never resets or rewrites main. (R7)

<!-- fr:journal kind=decision scope=spec id=list-forge-reads created=2026-10-11T18:48:13+00:00 -->
### list-forge-reads · decision · --list reads the forge once per distinct ref and per repo+branch

Operator chose: classify each distinct ref issue-vs-PR once per listing, one open-PR lookup per session branch; a failed read prints `(?)` and the listing continues; no --offline flag. (R15-R17)

<!-- fr:journal kind=decision scope=spec id=verification-strategy created=2026-10-11T18:48:13+00:00 -->
### verification-strategy · decision · Verification: candidate scenarios + one post-merge live row

Operator chose: candidate strategy (installed build, scenarios over a fake herdr and fake gh for the held message and --list), default-branch path verified by CI unit tests over a real temp repo, plus one post-merge live row on the herdr host.

<!-- fr:journal kind=finding scope=spec id=sr-f1 created=2026-10-11T19:01:58+00:00 state=open review_scope=in -->
### sr-f1 · finding [open] (reviewer: in scope) · Design B/D imports fr.isolation and new gitseam helpers the batch tripwire forbids; no allowance change named

See the fr-spec-reviewer return (spec-review-1) for file:line evidence.

<!-- fr:journal kind=finding scope=spec id=sr-f2 created=2026-10-11T19:01:58+00:00 state=open review_scope=in -->
### sr-f2 · finding [open] (reviewer: in scope) · Reuse the existing workspace selection; R9 'exists counts as done' strands a half-started devcontainer

See the fr-spec-reviewer return (spec-review-1) for file:line evidence.

<!-- fr:journal kind=finding scope=spec id=sr-f3 created=2026-10-11T19:01:58+00:00 state=open review_scope=in -->
### sr-f3 · finding [open] (reviewer: in scope) · Default-branch message gives no push command though the new branch's upstream is origin/<default>

See the fr-spec-reviewer return (spec-review-1) for file:line evidence.

<!-- fr:journal kind=finding scope=spec id=sr-f4 created=2026-10-11T19:01:58+00:00 state=open review_scope=in -->
### sr-f4 · finding [open] (reviewer: in scope) · R16 leaves undefined how a <repo>#<n> ref becomes owner/repo, and drops owner/repo#n

See the fr-spec-reviewer return (spec-review-1) for file:line evidence.

<!-- fr:journal kind=finding scope=spec id=sr-f5 created=2026-10-11T19:01:58+00:00 state=open review_scope=in -->
### sr-f5 · finding [open] (reviewer: in scope) · checkout_facts loses the forge host; R17 does not cover client-build or git failures

See the fr-spec-reviewer return (spec-review-1) for file:line evidence.

<!-- fr:journal kind=finding scope=spec id=sr-f6 created=2026-10-11T19:01:58+00:00 state=open review_scope=in -->
### sr-f6 · finding [open] (reviewer: in scope) · session_row(target) in fr/triage/batch.py cannot take an AdoptTarget: fr.triage may not import fr_dispatch

See the fr-spec-reviewer return (spec-review-1) for file:line evidence.

<!-- fr:journal kind=finding scope=spec id=sr-f7 created=2026-10-11T19:01:58+00:00 state=open review_scope=in -->
### sr-f7 · finding [open] (reviewer: in scope) · R12 leaves the batch predicate, detached HEAD and unreadable default branch undefined

See the fr-spec-reviewer return (spec-review-1) for file:line evidence.

<!-- fr:journal kind=finding scope=spec id=sr-f8 created=2026-10-11T19:01:58+00:00 state=open review_scope=in -->
### sr-f8 · finding [open] (reviewer: in scope) · R15 matches PRs by head name with no OPEN or trust filter

See the fr-spec-reviewer return (spec-review-1) for file:line evidence.

<!-- fr:journal kind=finding scope=spec id=sr-f9 created=2026-10-11T19:01:58+00:00 state=open review_scope=in -->
### sr-f9 · finding [open] (reviewer: in scope) · herdr mapping: prefer foreground_cwd, map opencode/hermes harness too

See the fr-spec-reviewer return (spec-review-1) for file:line evidence.

<!-- fr:journal kind=finding scope=spec id=sr-f10 created=2026-10-11T19:01:58+00:00 state=open review_scope=in -->
### sr-f10 · finding [open] (reviewer: in scope) · R7/R9: any existing workspace counts as this adoption's; nothing checks main worktree is on <default>

See the fr-spec-reviewer return (spec-review-1) for file:line evidence.

<!-- fr:journal kind=finding scope=spec id=sr-f11 created=2026-10-11T19:01:58+00:00 state=open review_scope=in -->
### sr-f11 · finding [open] (reviewer: in scope) · Resumable stop report's re-run command drops --no-hold

See the fr-spec-reviewer return (spec-review-1) for file:line evidence.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-10-11T19:01:58+00:00 -->
### spec-review-1 · review · Spec review of 2026-10-11-batch-adopt-safety-2-design

Dispatched fr-spec-reviewer raised 11 findings, sr-f1..sr-f11, all in scope (tripwire seam, workspace resume, push target, ref grammar, per-row robustness, import direction, state precedence, PR trust filter, herdr field mapping, reuse refusal, --no-hold in the stop report). All five operator decisions verified honoured. All fixed in the spec.

<!-- fr:journal kind=finding scope=spec id=sr-f1-resolved created=2026-10-11T19:01:58+00:00 state=fixed resolves=sr-f1 -->
### sr-f1-resolved · finding [fixed] · resolves sr-f1: Design B/D imports fr.isolation and new gitseam helpers the batch tripwire forbids; no allowance change named

Fixed in spec §B 'The isolation seam': a new fr/isolation/adopt.py owns every isolation call; _ISOLATION_ALLOWED grows by exactly its imports with the pinned allowance test updated in the same diff; checkout facts become a Checkout classmethod (Checkout.facts) so the gitseam surface stays Checkout/Worktree/GitError.

<!-- fr:journal kind=finding scope=spec id=sr-f2-resolved created=2026-10-11T19:01:58+00:00 state=fixed resolves=sr-f2 -->
### sr-f2-resolved · finding [fixed] · resolves sr-f2: Reuse the existing workspace selection; R9 'exists counts as done' strands a half-started devcontainer

Fixed in §B: enter_workspace uses the same backend selection fr.run.workspace._select_target wraps and ALWAYS calls up() (documented resume), so a container that never started is started on re-run; repo_root is main_worktree(); the R8 paragraph now names up's config writes.

<!-- fr:journal kind=finding scope=spec id=sr-f3-resolved created=2026-10-11T19:01:58+00:00 state=fixed resolves=sr-f3 -->
### sr-f3-resolved · finding [fixed] · resolves sr-f3: Default-branch message gives no push command though the new branch's upstream is origin/<default>

Fixed in R6 and §A: the default-branch message says publish only with `git push -u origin <new>`, never push <default>; pinned by the held-text test.

<!-- fr:journal kind=finding scope=spec id=sr-f4-resolved created=2026-10-11T19:01:58+00:00 state=fixed resolves=sr-f4 -->
### sr-f4-resolved · finding [fixed] · resolves sr-f4: R16 leaves undefined how a <repo>#<n> ref becomes owner/repo, and drops owner/repo#n

Fixed in R16 and §D: parse_refs recognises owner/name#n, name#n (resolved to the agent's owner/name when names match, else unresolved `(?)`) and bare #n; resolve_ref specified.

<!-- fr:journal kind=finding scope=spec id=sr-f5-resolved created=2026-10-11T19:01:58+00:00 state=fixed resolves=sr-f5 -->
### sr-f5-resolved · finding [fixed] · resolves sr-f5: checkout_facts loses the forge host; R17 does not cover client-build or git failures

Fixed in R17 and §D: Checkout.facts returns the origin URL; make_client built per host inside each row's guard; any per-row git/client/forge failure degrades only that row.

<!-- fr:journal kind=finding scope=spec id=sr-f6-resolved created=2026-10-11T19:01:58+00:00 state=fixed resolves=sr-f6 -->
### sr-f6-resolved · finding [fixed] · resolves sr-f6: session_row(target) in fr/triage/batch.py cannot take an AdoptTarget: fr.triage may not import fr_dispatch

Fixed in §D: the pure helpers (parse_refs, resolve_ref, session_state) take plain values; the command unpacks the runner's object.

<!-- fr:journal kind=finding scope=spec id=sr-f7-resolved created=2026-10-11T19:01:58+00:00 state=fixed resolves=sr-f7 -->
### sr-f7-resolved · finding [fixed] · resolves sr-f7: R12 leaves the batch predicate, detached HEAD and unreadable default branch undefined

Fixed in R12: ordered precedence with batch = label contains /run/batch- (adopt's own test), unknown for unreadable default, a new `detached` state.

<!-- fr:journal kind=finding scope=spec id=sr-f8-resolved created=2026-10-11T19:01:58+00:00 state=fixed resolves=sr-f8 -->
### sr-f8-resolved · finding [fixed] · resolves sr-f8: R15 matches PRs by head name with no OPEN or trust filter

Fixed in R15 and §D: OPEN only, isCrossRepository false, newest first, looked up only for adoptable rows (never the default branch).

<!-- fr:journal kind=finding scope=spec id=sr-f9-resolved created=2026-10-11T19:01:58+00:00 state=fixed resolves=sr-f9 -->
### sr-f9-resolved · finding [fixed] · resolves sr-f9: herdr mapping: prefer foreground_cwd, map opencode/hermes harness too

Fixed in R10 and §C: cwd from foreground_cwd else cwd; harness claude|opencode|hermes else None; the exact-equality herdr test is named as updated.

<!-- fr:journal kind=finding scope=spec id=sr-f10-resolved created=2026-10-11T19:01:58+00:00 state=fixed resolves=sr-f10 -->
### sr-f10-resolved · finding [fixed] · resolves sr-f10: R7/R9: any existing workspace counts as this adoption's; nothing checks main worktree is on <default>

Fixed in R7 and §B: refuse when the main worktree is not on <default>; an existing batch-branch workspace is reusable only with no commits beyond origin/<default> or when this session is already bound; git reads run in main_worktree().

<!-- fr:journal kind=finding scope=spec id=sr-f11-resolved created=2026-10-11T19:01:58+00:00 state=fixed resolves=sr-f11 -->
### sr-f11-resolved · finding [fixed] · resolves sr-f11: Resumable stop report's re-run command drops --no-hold

Fixed in R9 and §B step 3: the stop report echoes --no-hold and --checkout on both paths.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-11-batch-adopt-safety-2-p2 created=2026-10-11T19:05:52+00:00 -->
### phase-split-2026-10-11-batch-adopt-safety-2-p2 · decision · ask: #1069 adopting a session on the default branch (R5–R9) is its own independently reviewable ask

Phase 2 serves only #1069's requirements and its own acceptance row.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-11-batch-adopt-safety-2-p3 created=2026-10-11T19:05:55+00:00 -->
### phase-split-2026-10-11-batch-adopt-safety-2-p3 · decision · ask: #1071 the adopt --list columns and ref classification (R11–R18) is its own independently reviewable ask

Phase 3 serves only #1071's requirements and its own acceptance row.
