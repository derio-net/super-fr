"""`fr triage` — backlog triage that runs on any harness.

Spec: docs/superpowers/specs/2026-09-21-fr-triage-design.md. The engine is
deterministic and ships in the `fr` wheel; the `fr-triage` skill is thin prose
over it. Triage state lives under fr's cache root, never in a repo, so it is not
an artifact kind (spec §3.B).
"""
