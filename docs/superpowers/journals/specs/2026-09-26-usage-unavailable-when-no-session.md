# Journal: 2026-09-26-usage-unavailable-when-no-session

<!-- fr:journal kind=decision scope=spec id=placeholder-empty-session-id created=2026-09-26T15:04:03 -->
### placeholder-empty-session-id · decision · Placeholder entry uses session ''

Operator chose the empty session id (the convention readers already use for 'no session id given'); no schema change, no migration.

<!-- fr:journal kind=decision scope=spec id=placeholder-dropped-on-real-capture created=2026-09-26T15:04:03 -->
### placeholder-dropped-on-real-capture · decision · Later real capture drops the placeholder

Operator chose drop: _merge discards a session '' / 'no session found' entry once real sessions exist.

<!-- fr:journal kind=decision scope=spec id=first-resolve-unchanged created=2026-09-26T15:04:03 -->
### first-resolve-unchanged · decision · require_sessions path keeps skipping

Operator chose: only deliver/closeout/archive write the placeholder.

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-09-26T15:05:51 state=open review_scope=in -->
### s1 · finding [open] (reviewer: in scope) · fr run cost never prints the unavailable reason

Spec claimed cost prints the reason; cost.py:162-165 only counts. check: codebase.

<!-- fr:journal kind=finding scope=spec id=s2 created=2026-09-26T15:05:51 state=open review_scope=in -->
### s2 · finding [open] (reviewer: in scope) · _merge could leave placeholder beside carried-forward real sessions

Placeholder must be built after merge, only when merged is empty. check: consistency.

<!-- fr:journal kind=finding scope=spec id=s3 created=2026-09-26T15:05:51 state=open review_scope=in -->
### s3 · finding [open] (reviewer: in scope) · session '' key collision in effective_entries stated harmless without proof

No dollar error but counts as unavailable; needs a two-host test. check: codebase.

<!-- fr:journal kind=finding scope=spec id=s4 created=2026-09-26T15:05:51 state=open review_scope=in -->
### s4 · finding [open] (reviewer: in scope) · needs_capture interaction and reason vocabulary unstated

Clarify placeholder-only capture makes needs_capture False; new reason is a vocabulary member. check: consistency.

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-09-26T15:05:51 -->
### spec-review · review · independent spec review: 4 findings

fr-spec-reviewer raised s1-s4, all in scope; code references otherwise verified (capture.py, file.py, cost.py, structure.py, readers).

<!-- fr:journal kind=finding scope=spec id=s1-resolved created=2026-09-26T15:05:51 state=fixed resolves=s1 -->
### s1-resolved · finding [fixed] · resolves s1: fr run cost never prints the unavailable reason

Spec 3.4/Test Plan 2/goal reworded: cost shows count, reason lives in file; surfacing reason is a non-goal.

<!-- fr:journal kind=finding scope=spec id=s2-resolved created=2026-09-26T15:05:51 state=fixed resolves=s2 -->
### s2-resolved · finding [fixed] · resolves s2: _merge could leave placeholder beside carried-forward real sessions

Spec 3.2 rewritten: placeholder built after merge only if merged list empty; test required.

<!-- fr:journal kind=finding scope=spec id=s3-resolved created=2026-09-26T15:05:51 state=fixed resolves=s3 -->
### s3-resolved · finding [fixed] · resolves s3: session '' key collision in effective_entries stated harmless without proof

Spec section 5 states the collision honestly and pins it with a two-host test.

<!-- fr:journal kind=finding scope=spec id=s4-resolved created=2026-09-26T15:05:51 state=fixed resolves=s4 -->
### s4-resolved · finding [fixed] · resolves s4: needs_capture interaction and reason vocabulary unstated

Spec 3.4 states needs_capture behaviour and structure validator round-trip.
