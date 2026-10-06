Packaged copy of `plugins/super-fr/verifications/` — **generated, do not edit here.**

The canonical strategy manifests live in `plugins/super-fr/verifications/`. This
directory is the same bytes, shipped INSIDE the `fr` wheel, so `resolve_strategy`
can still find a shipped strategy on a host that has no Claude Code marketplace
clone (a hermes pod, an OpenCode consumer, a bare `uv tool install fr`).

To update: `cp plugins/super-fr/verifications/*.yaml packages/fr/src/fr/verifications/`.
`tests/unit/test_tripwire_shipped_verifications.py` fails when the two diverge.
