# Journal: 2026-09-25-writes-dot-dir-prefix

<!-- fr:journal kind=decision scope=spec id=d1 created=2026-09-25T00:44:21 -->
### d1 · decision · Segment-wise strip for relative redirect targets

Operator chose the segment-wise strip (drop '.' and leading '..' segments, then trailing-segment match). This keeps the existing ../x.log leniency on purpose.

<!-- fr:journal kind=decision scope=spec id=d2 created=2026-09-25T00:44:21 -->
### d2 · decision · Model tiers left unbound

Operator: inherit the session model, and dispatch untiered agents.

<!-- fr:journal kind=decision scope=spec id=d3 created=2026-09-25T00:44:22 -->
### d3 · decision · No post-merge Test Plan; dogfood at this deliver

This run's deliver names .fr-deliver/tests.log through uv run fr, which is the live proof.

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-09-25T00:46:16 state=open review_scope=in -->
### s1 · finding [open] (reviewer: in scope) · Dogfood deliver writes an untracked .fr-deliver/ that nothing ignores

spec §3.3; .gitignore has no .fr-deliver entry. Risk: a test log gets committed to a public repo.

<!-- fr:journal kind=finding scope=spec id=s1-resolved created=2026-09-25T00:46:17 state=fixed resolves=s1 -->
### s1-resolved · finding [fixed] · resolves s1: Dogfood deliver writes an untracked .fr-deliver/ that nothing ignores

Spec §3.3 now adds .fr-deliver/ to .gitignore in this change.

<!-- fr:journal kind=review scope=spec id=sr1 created=2026-09-25T00:46:17 -->
### sr1 · review · Independent spec review (fr-spec-reviewer): 1 finding, s1 (in scope), fixed

Every file:line, the PurePosixPath semantics and the §2 consequences were verified by the reviewer. s1 was fixed in spec §3.3.
