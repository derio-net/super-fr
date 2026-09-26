# Journal: 2026-09-26-release-scripts-hardening

<!-- fr:journal kind=decision scope=spec id=d-widen-code created=2026-09-26T12:07:40 -->
### d-widen-code · decision · Widen requires_bump to plugins/*/skills, not the docs

Per gh#671 and the brief; rules stay super-fr only as AGENTS.md documents.

<!-- fr:journal kind=decision scope=spec id=d-fail-loud created=2026-09-26T12:07:40 -->
### d-fail-loud · decision · No [project].version raises ValueError, no first-match fallback

A fallback would reintroduce the defect on the unattended release path.

<!-- fr:journal kind=decision scope=spec id=gate-no-questions-brainstorm created=2026-09-26T12:07:40 -->
### gate-no-questions-brainstorm · decision · Operator gate `brainstorm` cleared without asking

Batch dispatch: the operator's brief already fixed every decision (anchor to [project]; widen code not docs for plugins/*/skills; uv run --no-project python; one phase; claude-sonnet-5 for every tier). No operator-owned choice remained.
