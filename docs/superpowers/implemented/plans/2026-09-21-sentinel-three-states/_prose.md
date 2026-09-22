# Plan — the sentinel's three states

Implements `docs/superpowers/specs/2026-09-21-sentinel-three-states-design.md` (#472, #529, #432).
The count of linked worktrees is replaced by a recorded fact: `attach` stamps the session's
sentinel with a cache-relative `workspace`; the guard reads fresh (no key) / live / orphaned from
the sentinel alone. Phase 2 (the hook) depends on phase 1's format; phase 3 is independent.
