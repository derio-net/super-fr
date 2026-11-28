# Triage privacy — plan

Spec: `docs/superpowers/specs/2026-11-28-triage-privacy-design.md`.

Two phases, one per independently reviewable ask:

1. **Collect keeps outsider text out of facts** (#1633, #1632, #1631; R1-R7, R10). All three
   change what collect writes into `facts.json` and share the facts schema bump to 22 and its
   older-schema load, so they land together. Order: the v2 digest smoke, canonical comment
   pinning, collect's digest and the load, the admit command and dispatch re-read, PR-title
   withholding with every display and queue reader, then the reopened-PR truncation guard.
2. **The privacy guard scans carried state** (#1634; R8, R9). Independent of facts' shape; it
   reads the state directory. Then docs currency and the last row.

TDD throughout: each task is red, green, refactor. The repo declares `tests: ci`, so each
executor runs the fast tier last.
