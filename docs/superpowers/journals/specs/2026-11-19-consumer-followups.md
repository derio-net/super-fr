<!-- fr:journal-schema=4 -->
# Journal: 2026-11-19-consumer-followups

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-19T22:22:30+00:00 input=true -->
### operator-brief · discovery · Batch consumer-followups: super-fr#1552, #1553, #1554 as one PR

Batch `consumer-followups` of derio-net/super-fr: 3 issues, delivered as ONE pull request,
on branch `feat/batch-consumer-followups`; draft PR opened once the spec is committed, body
carrying `Closes derio-net/super-fr#1552`, `#1553`, `#1554` one per line; no member issue as
a phase tracking_issue; never add `approved-fr`.

- #1552 The isolation gate and the pipeline sentinel also judge in the plugin's directory
  (consumer-delivery spec review s-r13; evidence index.ts:281, :287, :291).
- #1553 Gitea matrix job checkout persists gitea.token for PR code (consumer-delivery p2-r8;
  pre-existing, R12 named only the debt job).
- #1554 tea fail-soft sites swallow the named login-page TeaError (consumer-delivery
  l-errors-r5; predates R14).
Why together: follow-ups filed by the consumer-delivery run (wave 20).

<!-- fr:journal kind=decision scope=spec id=q1-gates-scope created=2026-11-19T22:22:30+00:00 decided_by=operator -->
### q1-gates-scope · decision · #1552: all three gate sites (shell gate, edit gate, sentinel) judge in the session's directory

Operator chose 'All three' over shell+sentinel only and no behaviour change. Matches Claude Code, whose hooks read the session cwd.

<!-- fr:journal kind=decision scope=spec id=q2-fallback created=2026-11-19T22:22:30+00:00 decided_by=operator -->
### q2-fallback · decision · #1552: a failed or empty session lookup falls back to the plugin directory, uncached

Operator chose the plugin directory (today's behaviour, same as nag/bind/claim/idle) over refusing the call.

<!-- fr:journal kind=decision scope=spec id=q3-tea-sites created=2026-11-19T22:22:30+00:00 decided_by=operator -->
### q3-tea-sites · decision · #1554: all six RealTeaClient fail-soft sites re-raise a named login page

Operator chose all six over glab's parallels only. Other TeaErrors stay fail-soft.

<!-- fr:journal kind=decision scope=spec id=q4-verification created=2026-11-19T22:22:30+00:00 decided_by=operator -->
### q4-verification · decision · Verification: strategy candidate, every row verify none (CI/bun tests), no Test Plan, no gate

Operator chose CI tests and no post-merge walk over adding a live OpenCode walk gated tester.

<!-- fr:journal kind=lens scope=spec id=lens-security-1 created=2026-11-19T22:22:30+00:00 lens=security step=brainstorm -->
### lens-security-1 · lens · R1-R4 change what the isolation gates judge, and R5 removes a persisted CI token; examine both for a new allow path

<!-- fr:journal kind=finding scope=spec id=s-r1 created=2026-11-19T22:29:53+00:00 state=open review_scope=in -->
### s-r1 · finding [open] (reviewer: in scope) · §C 'Callers already handle a raised forge error' is unverified and wrong for some callers of the six tea sites

ops/gate.py:336 Gate.default lets a raised TeaError become a traceback; isolation/local.py:3030/:3167 turn it into a refusal (behaviour change); migrate.py:934 hides it. glab re-raises at only three sites (:402, :428, :465). Fix: list each site's callers, map FORGE_ERRORS to StageFailed in Gate.default, state the isolation change as intended.

<!-- fr:journal kind=finding scope=spec id=s-r2 created=2026-11-19T22:29:53+00:00 state=open review_scope=in -->
### s-r2 · finding [open] (reviewer: in scope) · The session lookup on execute.before's hot path has no timeout and is retried on every call while it fails

index.ts:278-294 would await session.get on every tool call; a hanging get stalls every call. Fix: bound the lookup; a timeout is the fallback, uncached.

<!-- fr:journal kind=finding scope=spec id=s-r3 created=2026-11-19T22:29:53+00:00 state=open review_scope=in -->
### s-r3 · finding [open] (reviewer: in scope) · R2 covers only relative targets; the edit gate's unresolvable-patch probe also moves to the session's repo

index.ts:197 normalizeTarget(directory, '.fr-unresolvable-patch-target'). Fix: state it in R2 and test it.

<!-- fr:journal kind=finding scope=spec id=s-r4 created=2026-11-19T22:29:53+00:00 state=open review_scope=in -->
### s-r4 · finding [open] (reviewer: in scope) · §B says 'golden files, if any', but two Gitea goldens exist; the new per-run fetch warning is not stated

tests/fixtures/acceptance_scaffold/gitea-actions.golden:48 and gitea-actions.published.golden; amend.py:349-358 warning on a private repo.

<!-- fr:journal kind=finding scope=spec id=s-r5 created=2026-11-19T22:29:53+00:00 state=open review_scope=out -->
### s-r5 · finding [open] (reviewer: out of scope) · In CI, a Gitea checkout with a default branch outside main/master/trunk/develop has no default ref, so the check refuses

amend.py:322-336; pre-existing, independent of the credential.

<!-- fr:journal kind=finding scope=spec id=s-r6 created=2026-11-19T22:29:53+00:00 state=open review_scope=out -->
### s-r6 · finding [open] (reviewer: out of scope) · Child sessions have no sentinel of their own, so the shell and push guards never fire for them in any directory

guard.ts:184-190, push.ts:48-53, sentinel.ts:209-228; pre-existing, independent of the directory.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-11-19T22:29:53+00:00 -->
### spec-review-1 · review · independent spec review: 6 findings (4 in scope, all fixed; 2 out)

fr-spec-reviewer (separate context) verified q1-q4 are honoured and checked every cited file:line, plus the callers of the six tea sites. s-r1..s-r4 fixed in the spec (07bcac956, R7 added and the tea row's origins corrected); s-r5, s-r6 out of scope, named in Out of scope.

<!-- fr:journal kind=lens scope=spec id=lens-errors-1 created=2026-11-19T22:29:53+00:00 lens=errors step=spec-review -->
### lens-errors-1 · lens · R6 turns six fail-soft reads into raises; every caller's handling of a raised TeaError (ops gate, isolation, migrate) needs examining

<!-- fr:journal kind=finding scope=spec id=s-r1-resolved created=2026-11-19T22:29:53+00:00 state=fixed resolves=s-r1 -->
### s-r1-resolved · finding [fixed] · resolves s-r1: §C 'Callers already handle a raised forge error' is unverified and wrong for some callers of the six tea sites

§C lists each site's callers; R7 added (Gate.default maps FORGE_ERRORS to StageFailed; isolation refusal stated as intended; migrate degrade kept, with reason).

<!-- fr:journal kind=finding scope=spec id=s-r2-resolved created=2026-11-19T22:29:53+00:00 state=fixed resolves=s-r2 -->
### s-r2-resolved · finding [fixed] · resolves s-r2: The session lookup on execute.before's hot path has no timeout and is retried on every call while it fails

R4 and §A bound the lookup at 2 s; a timeout is the fallback, uncached; verification covers a hanging lookup.

<!-- fr:journal kind=finding scope=spec id=s-r3-resolved created=2026-11-19T22:29:53+00:00 state=fixed resolves=s-r3 -->
### s-r3-resolved · finding [fixed] · resolves s-r3: R2 covers only relative targets; the edit gate's unresolvable-patch probe also moves to the session's repo

R2 and §A name the unresolvable-patch probe; verification covers it.

<!-- fr:journal kind=finding scope=spec id=s-r4-resolved created=2026-11-19T22:29:53+00:00 state=fixed resolves=s-r4 -->
### s-r4-resolved · finding [fixed] · resolves s-r4: §B says 'golden files, if any', but two Gitea goldens exist; the new per-run fetch warning is not stated

§B names both goldens and states the per-run fetch warning on a private repo.

<!-- fr:journal kind=finding scope=spec id=s-r5-resolved created=2026-11-19T22:29:53+00:00 state=open resolves=s-r5 out_of_scope=true -->
### s-r5-resolved · finding [out-of-scope] · resolves s-r5: In CI, a Gitea checkout with a default branch outside main/master/trunk/develop has no default ref, so the check refuses

Predates this change: R5 changes only whether the fetch is authenticated, not how the default ref is found. Named in Out of scope.

<!-- fr:journal kind=finding scope=spec id=s-r6-resolved created=2026-11-19T22:29:53+00:00 state=open resolves=s-r6 out_of_scope=true -->
### s-r6-resolved · finding [out-of-scope] · resolves s-r6: Child sessions have no sentinel of their own, so the shell and push guards never fire for them in any directory

Predates this change: no sentinel for a child is independent of which directory is judged. Named in Out of scope.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-19T22:29:55+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  gitea-matrix-no-persisted-token: none
  opencode-gates-session-directory: none
  tea-fail-soft-login-page: none
row_kinds:
  gitea-matrix-no-persisted-token: none
  opencode-gates-session-directory: none
  tea-fail-soft-login-page: none
run_gate: none
run_kind: candidate
```

<!-- fr:journal kind=decision scope=spec id=tier-2026-11-19-consumer-followups-p1 created=2026-11-19T22:32:03+00:00 -->
### tier-2026-11-19-consumer-followups-p1 · decision · hard: R1-R4 change what the OpenCode isolation gates judge on every tool call of every session
