Implements the super-fr split (spec: 2026-06-05-super-fr-split-design.md,
FINAL): three uv-workspace packages — `fr` (superpowers wrapper + GH
tracking), `fr-dispatch` (queue protocol + de-VK-ified runner framework),
`fr-vk` (VibeKanban adapter, the only runner shipped) — plus the full v3
rebrand: CLI `fr`, skills `/fr-*`, plugins super-fr + super-fr-dispatch,
labels `fr:*` with `runner:<name>`, repo renamed to derio-net/super-fr at
merge time. No backward compatibility except the sanctioned label
dual-read during cutover.

One PR, evolving #262 (operator decision): spec, plan, and implementation
ship together on feat/plugin-split-design. Phases 1–4 are agentic and
each ends fully green (real exit codes); Phase 5 is the back-loaded
manual cutover (repo rename → merge → pod → sweep → dual-read removal).

Key constraints from review: only lifecycle.py was VK-free — Phase 2 is
a de-VK-ification refactor, not a relocation; the 73-test bridge suite
is the frozen cross-package contract; CI workflows pin the repo URL and
binary name; allowlists reference `vk *` and break silently (sweep
handles them).
