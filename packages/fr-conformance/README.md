# fr-conformance

Live conformance probes for harness gate verification.

Mirrors the `agnostic-fr` conformance structure:
- `engine.py` - launches real harness binary, snapshots repo before/after
- `mock/server.py` - deterministic mock model (OpenAI-compatible)
- `mock/scenario.py` - scripted scenarios for each probe
- `probes.py` - probe runner and assertions
- `registry/opencode.yaml` - harness launch config
- `probes/` - individual probe tests

## Probes

| Probe | Description |
|-------|-------------|
| test_edit_gate_refuses | OpenCode refuses write in base clone of fr-enabled repo |
| test_edit_gate_allows | OpenCode allows write in valid fr worktree (negative control) |
| test_patch_fails_closed | OpenCode refuses patch on base-clone target |
| test_bash_ungated | OpenCode allows bash write in base clone (documented gap) |
| test_idle_adapter_continues | Idle adapter continues advanceable run |
| test_idle_adapter_respects_held_gate | Idle adapter respects held operator gate |

## Running Probes

```bash
# Install opencode binary first
npm install -g @opencode-ai/opencode

# Run probes
pytest packages/fr-conformance/probes/ -v
```

## CI Integration

The `.github/workflows/opencode-conformance.yml` workflow runs these probes on every PR.
