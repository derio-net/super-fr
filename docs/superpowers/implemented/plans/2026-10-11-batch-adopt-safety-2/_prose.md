# Batch adopt safety — implementation plan

Three asks, three agentic phases, from spec `2026-10-11-batch-adopt-safety-2-design.md`:

1. **Phase 1 (skeleton, #1081):** the held adopt message, `--no-hold`, the plan printing the exact message, the
   stop report echoing flags, and the optional `AdoptTarget` fields (`cwd`, `session`, `harness`) that phases 2
   and 3 both read. Change fragment here.
2. **Phase 2 (#1069):** adopting a session on the default branch. The gitseam read methods, the new
   `fr.isolation.adopt` seam with the batch tripwire's allowance widened by exact imports, and
   `_adopt_from_default` with R7's refusals, R8's untouched base clone and R9's resume.
3. **Phase 3 (#1071):** `adopt --list`, with pure ref and state helpers, `Checkout.facts`, `GhClient.ref_kind`,
   a per-row guarded listing, the scenario and the fr-triage skill sentence plus its mirrors.

Phases 2 and 3 both depend only on phase 1. They touch `triage_batch_cmd.py` in different functions, and run
serially.

Run tests in the devcontainer workspace through `fr isolation exec -- uv run pytest ...`. Long suites follow the
brief's long_commands rule.
