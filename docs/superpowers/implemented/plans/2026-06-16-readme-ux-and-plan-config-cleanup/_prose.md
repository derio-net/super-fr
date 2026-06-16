# README UX pass + plan-config dead-key cleanup

Implements `docs/superpowers/specs/2026-06-16-readme-ux-and-plan-config-cleanup-design.md`.

Two cohesive usability/cleanup goals, delivered as one PR:

1. **Kill the dead `plan-config.yaml` config.** `plan.save_to` and the entire
   `dispatch:` block are read by no code (only `validate-plans.sh` reads the
   live `plan.filename` + `header.*`). A new text-based normalizer
   (`fr.plan_config`) strips them while preserving the live keys, comments, and
   formatting. It's wired into `fr repair` and `fr migrate v1-to-v2` so any repo
   those touch gets cleaned idempotently. The `fr repos sync` template stops
   generating the dispatch stub, the dead `def_for_name` helper is deleted, and
   this repo's own file is stripped as the dogfood proof.

2. **Make the README user-first.** Re-sequence to a benefit-led IA where install
   + first-success come before architecture, the skill tables gain
   `How invoked` / `When` columns, and maintainer-leaning content (flow
   diagrams, Python-package internals, maintenance CLI commands) is relocated
   deeper via progressive disclosure — one file, nothing cut.

## Phase map

- **Phase 1** — `fr.plan_config` normalizer (`strip_dead_keys` text +
  `strip_dead_keys_file`). Pure, unit-tested, no CLI coupling.
- **Phase 2** — wire the normalizer into `fr repair` (dry-run default, reported
  through `RepairResult`).
- **Phase 3** — wire it into `fr migrate v1-to-v2`.
- **Phase 4** — drop the dispatch stub from `render_plan_config`, delete
  `def_for_name`, strip this repo's `plan-config.yaml`.
- **Phase 5** — README restructure + minor version bump + full CI gate.

TDD throughout. No manual phase — every change is agent-completable; the only
human step is the standard PR merge. Phases 2/3/4 each build on Phase 1's
normalizer; Phase 5 (README) lands last because its Per-repo section reflects
the dispatch-keys-removed reality from Phase 4.
