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
