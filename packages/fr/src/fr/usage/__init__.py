"""`fr usage` — what a harness session cost, and what it spent it on.

Spec: docs/superpowers/specs/2026-09-25-lean-cost-aware-process-design.md §5.A.
One reader per harness normalizes a session into a `UsageRecord`
(`fr.usage.model`); `fr.usage.classify` names what each tool call was for;
`fr.usage.rollup` splits the harness's own dollars across activities and run
steps; `fr.usage.render` prints the result. Nothing here writes a registered
artifact: collected records live under `$HOME/.cache/fr/usage/`.

Two invariants hold throughout. **Unavailable is never zero**: a source that
cannot be read yields `UsageRecord.unavailable` and renders `—`. **Dollars come
from the harness**: only the fixed price RATIOS in `fr.usage.model.WEIGHTS`
split a harness figure; no list price appears anywhere.
"""
