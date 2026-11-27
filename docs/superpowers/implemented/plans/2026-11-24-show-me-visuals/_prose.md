# Show me: a visual shape in every spec and every PR

Spec: `2026-11-24-show-me-visuals-design.md` (issue derio-net/super-fr#1641).

Two agentic phases, one per independently reviewable ask:

1. **The engine** (skeleton). `fr.shape` owns the shape-block grammar. The spec gate refuses a
   spec with no valid `## Design shape` at brainstorm and every spec-reviewing step. The PR body
   gains the required `## Shape of the change`, and `deliver` refuses a missing or invalid shape
   file. The lens brief names the shape file, archive and adopt move it, and the ops trust tree
   treats it as fr bookkeeping. Its first task is the smoke: a new test file importing a new module.
2. **The prose.** The `fr-show-me` skill (the vocabulary), the sentences in fr-goal and
   fr-brainstorming that use it, the spec reviewer's design-shape check (an agent edit, so the
   `agents` artifact kind moves one version with its rerender hop), the explainer page, docs
   currency and the change fragment.

Phase 2 depends on phase 1 because its prose names the brief key and refusals phase 1 builds.

The repo declares `tests: ci`. Each executor runs the fast tier from its brief last, on single test
files while iterating, because the host is shared.
