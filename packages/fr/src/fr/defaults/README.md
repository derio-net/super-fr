Packaged copy of `plugins/super-fr/defaults/` — **generated, do not edit here.**

The canonical shipped defaults (`workflows/`, `verifications/`, `lenses/`) live in
`plugins/super-fr/defaults/`. This directory holds the same bytes INSIDE the `fr`
wheel, so `fr._shipped` finds a shipped default on a host with no Claude Code
marketplace clone (a hermes pod, an OpenCode consumer, a bare `uv tool install fr`).

To update: `uv run --no-project python scripts/sync-defaults-data.py`
(`--check` exits 1 on drift). `tests/unit/test_tripwire_shipped_defaults.py` fails
when the two diverge.
