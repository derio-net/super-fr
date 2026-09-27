# spec: writers agree on canonical_spec_ref

Triage batch `spec-ref-writers` (derio-net/super-fr#709, #710, #711), one PR.
Spec: `docs/superpowers/specs/2026-09-27-spec-ref-writers-design.md`.

One agentic phase, three TDD tasks — one per issue — plus a closing gate task:

1. **#709** — `canonical_spec_ref` keeps a ref whose lexically-normalised path
   leaves `repo_root` verbatim, whether or not the target exists.
2. **#710** — `fr archive` repairs through one `_repair_in_passing` helper,
   once per invocation; `_report_sweep` only reports.
3. **#711** — the v1→v2 migration stores `canonical_spec_ref(v1plan.spec)`.

Out of bounds (other running batches): `fr/isolation/`, `scripts/install.sh`,
`commands/apply_cmd.py`, `run/telemetry.py`, `run/long_commands.py`,
`fr/triage/`.
