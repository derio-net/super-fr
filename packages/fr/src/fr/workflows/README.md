Packaged copy of `plugins/super-fr/workflows/` — **generated, do not edit here.**

The canonical manifests live in `plugins/super-fr/workflows/`. This directory
is the same bytes, shipped INSIDE the `fr` wheel, so `resolve_workflow` can
still find a shipped shape on a host that has no Claude Code marketplace clone
(a hermes pod, an OpenCode consumer, a bare `uv tool install fr`). Without it
`fr run start fr-goal` failed there and `fr workflow check --all` reported
"no workflow shapes found" while exiting 0.

To update: `cp plugins/super-fr/workflows/*.yaml packages/fr/src/fr/workflows/`.
`tests/unit/test_tripwire_shipped_workflows.py` fails when the two diverge.
