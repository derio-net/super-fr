# Journal: 2026-09-26-archive-repair-scope

<!-- fr:journal kind=decision scope=spec id=canonical-spec-form created=2026-09-26T15:09:01 -->
### canonical-spec-form · decision · Canonical spec: form is the bare filename

Operator chose bare <name>-design.md (lifecycle-independent). plan create normalizes to it; validator/resolver keep accepting the full path.

<!-- fr:journal kind=decision scope=spec id=repair-scope created=2026-09-26T15:09:01 -->
### repair-scope · decision · Single-plan archive repairs only the archived plan's rows

Operator chose an only_plans filter on repair_repo; --all, --sweep-only and fr repair stay repo-wide.

<!-- fr:journal kind=decision scope=spec id=no-test-plan created=2026-09-26T15:09:01 -->
### no-test-plan · decision · No post-merge Test Plan

Bug fix, CI tests only.
