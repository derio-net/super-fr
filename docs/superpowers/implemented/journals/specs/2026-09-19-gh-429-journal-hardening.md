# Journal: 2026-09-19-gh-429-journal-hardening

<!-- fr:journal kind=decision scope=spec id=duplicate-add-fails created=2026-09-19T00:19:47 -->
### duplicate-add-fails · decision · Duplicate journal adds fail loudly

Operator approved exit 2 with a concise existing-id error that directs users to fr journal resolve.

<!-- fr:journal kind=decision scope=spec id=scope-confirmed created=2026-09-19T00:19:47 -->
### scope-confirmed · decision · All remaining issue items are in scope

Operator confirmed duplicate-add failure, scope validation, and duplicate parsed-id rejection are one change.

<!-- fr:journal kind=decision scope=spec id=models-terra created=2026-09-19T00:19:48 -->
### models-terra · decision · All implementation tiers use Terra

Operator selected github-copilot/gpt-5.6-terra for mechanical, standard, and hard OpenCode tiers.

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-09-19T00:20:20 -->
### spec-review · review · Spec review passed

Reviewed against issue #429 and current journal commands. Existing resolve is append-only; the design limits changes to create feedback, scope validation, and parser ambiguity.
