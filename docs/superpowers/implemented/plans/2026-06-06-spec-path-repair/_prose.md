Fixes the stale-path bug class found 2026-06-06: spec-table File cells
(and `_meta.yaml` `parent_plan:`/`spec:` refs) recorded under the
pre-2.5.0 `archived-plans/` convention are invisible to path resolution
after `vk migrate dirs` — `_resolve_local_plan_dir` and
`_archive_path_variants` anchor on a literal `plans` segment that
`archived-plans` never matches. Rows report Unreachable and owning
specs never qualify for auto-archive.

The fix reverses 2.5.0's "spec tables are never rewritten" doctrine to
**normalize once, idempotently**: refs become lifecycle-independent
bare slugs that cannot go stale, a shared `vk.refs` resolver accepts
every historical form forever, and repair (standalone `vk repair`, plus
in-passing inside `vk archive` / `vk migrate dirs`) converges old refs
with loud warnings for anything unresolvable.

Spec: `docs/superpowers/specs/2026-06-06-spec-path-repair-design.md`
(decisions table: bare-slug form, all three surfaces, repair verbs,
post-merge fleet sweep).

TDD throughout; the Phase 1 regression test asserts the original
`None` resolution dead. Phase 4 dogfoods the repair on this repo's own
five+ stale specs as in-PR evidence.
