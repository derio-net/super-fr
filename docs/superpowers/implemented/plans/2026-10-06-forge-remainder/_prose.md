# Forge remainder — implementation plan

Spec: `docs/superpowers/specs/2026-10-06-forge-remainder-design.md`. Batch `forge-remainder`, PR #994.

The plan has two agentic phases, one per independently reviewable ask:

1. **#892: the host reaches the forge (R5, R6).**
   - `fr.gh` gains a scoped `GH_HOST`, and `RealGhClient(host=)` honours it.
   - `client_for` threads a *declared* GitHub host.
   - `client_for_url` is shared by `pr_state` and the triage batch verbs.
   - This is the skeleton phase: its first task is the smoke.
2. **#742: empty the allowlist (R1–R4, R7, R8).**
   - The isolation lookups and triage collect move onto the adapter.
   - The bridge classifies every forge error.
   - The tripwire loses `KNOWN`, and the skill prose turns forge-neutral.
   - It depends on phase 1, because the GitHub adapter's default runner uses phase 1's `host_scope`.

No phase names #742 or #892 as its `tracking_issue`, because the batch PR closes both issues.
