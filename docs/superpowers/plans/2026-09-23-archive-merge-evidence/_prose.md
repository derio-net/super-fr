# Plan: merge evidence for fr status and fr archive (#526, #544)

Spec: `docs/superpowers/specs/2026-09-23-archive-merge-evidence-design.md`.

**Why.** `fr status` called locally complete plans "merged" and suggested
`fr archive --all`. That command then archived them, because `archive_gate`'s
undispatched arm never checks merge state. Every fr-goal branch hits this
before its PR exists.

**Shape.**

1. **Phase 1 (skeleton).** Add one helper, `fr.archive.merge_evidence`, which
   materialises `origin/<default>` once. It is the single definition of
   "merged": every agentic phase is complete on the ref. The CI tripwire is
   rewired onto it.
2. **Phase 2.** The `fr status` sweep reports four buckets and suggests only
   per-plan `fr archive <dir>`.
3. **Phase 3.** `archive_gate` requires a `landed` keyword argument, which
   closes #544. Release housekeeping is in this phase too.
4. **Phase 4 (trailing, manual).** The live before-and-after check the
   operator asked for.

Phases 2 and 3 both depend only on phase 1. They run serially on the shared
branch.

**The one design turn to know.** Manual phases are excluded from merge
evidence. fr-goal ships its trailing manual phase unticked and ticks it after
merge. If every phase had to be complete on `main`, no fr-goal plan would ever
look merged, and `fr archive` would refuse them all. The manual phase is still
judged in the working tree before archiving.
