# Spec: OpenCode Gates Install + Live Conformance — #563

## Background

`scripts/install.sh` delivers skills, slash commands, and agents to OpenCode but **does not deliver
`packages/fr-opencode-plugin`** — the code plugin carrying:

- `fr-isolation-required` edit gate (`tool.execute.before`)
- `fr-run-idle-guard` idle adapter (`session.idle` → `prompt_async`)

So for any repo other than super-fr itself, OpenCode runs with neither gate. The parity matrix
reports both as `partial` on OpenCode, but `fr.harness.observe` reads wiring from super-fr's
**source tree** (`packages/fr-opencode-plugin/src`), not from what `install.sh` delivers to a
consumer. This is the failure class the repo keeps rediscovering: a check that reports a
capability present because it looks where the capability is being *built*, not where it is *used*.

## Goal

1. **Deliver the plugin** from `install.sh` into `~/.config/opencode/plugins/` when OpenCode is
   present (reusing the existing detection gate).
2. **Make parity check delivery**, not only wiring — a tripwire fails when `parity.yaml` credits
   OpenCode with a surface `install.sh` does not deliver.
3. **Prove the gates work** with live conformance probes (mirroring `agnostic-fr`'s engine/mock/probe
   structure, vendored since agnostic-fr is private).
4. **CI runs the probes** with the `opencode` binary installed; skip = fail for this suite.
5. **Minor version bump** (touches `install.sh`).

## Operator Decisions (batched Q&A)

| Question | Decision | Rationale |
|---|---|---|
| Delivery mechanism | `bun build --compile` → single binary | Zero-friction install, no node_modules, no runtime deps. bun already a dep. |
| Conformance approach | Mirror agnostic-fr exactly | Proven mechanism, same probe semantics. |
| Code sharing | Vendor (copy) conformance code | agnostic-fr is private; vendored code becomes public in super-fr. |
| CI binary install | `npm install -g @opencode-ai/opencode` in CI | Standard; cache `~/.npm` and binary to amortize cost. Skipif removed → CI fails if binary missing. |

## Design

### 1. Plugin build + delivery

**Build step** (added to `scripts/install.sh` before OpenCode delivery block):
```bash
# Build fr-opencode-plugin to a single binary
cd "$PLUGIN_ROOT/packages/fr-opencode-plugin"
bun build --compile src/index.ts --outfile "$PLUGIN_ROOT/.build/fr-opencode-plugin"
```

**Delivery** (in the existing OpenCode block, after agents):
```bash
OPENCODE_PLUGINS_DIR="$HOME/.config/opencode/plugins"
mkdir -p "$OPENCODE_PLUGINS_DIR"
cp "$PLUGIN_ROOT/.build/fr-opencode-plugin" "$OPENCODE_PLUGINS_DIR/fr-opencode-plugin"
echo "  Installed $OPENCODE_PLUGINS_DIR/fr-opencode-plugin"
```

**Uninstall** (in `--uninstall` block):
```bash
rm -f "$HOME/.config/opencode/plugins/fr-opencode-plugin"
```

**Version tracking**: The binary is rebuilt on every `install.sh` run (fast, ~2s). No separate version
file needed — the installer's version is the source of truth.

### 2. Parity delivery tripwire

Add a test `tests/unit/test_install_copies_opencode_plugin.py` that:
- Runs `install.sh` into a temp `$HOME` (with `OPENCODE_SKILLS_INSTALL=1`)
- Asserts `~/.config/opencode/plugins/fr-opencode-plugin` exists and is executable
- Asserts every OpenCode surface in `parity.yaml` with `state: enforced` or `partial`
  has a corresponding delivered artifact (plugin binary for hooks, config for interactions)

### 3. Conformance probes (vendored from agnostic-fr)

**Structure** (copied to `packages/fr-conformance/`):
```
packages/fr-conformance/
├── engine.py          # launches real harness binary, snapshots repo before/after
├── mock/
│   ├── server.py      # deterministic mock model (OpenAI-compatible /chat/completions)
│   └── scenario.py    # scripted turns + tool calls → harness wire protocol
├── probes.py          # fixture repo + scenario + assertion over side effects
├── registry/
│   └── opencode.yaml  # launch cmd, wire protocol (openai-chat), baseURL override
└── probes/
    ├── test_edit_gate_refuses.py
    ├── test_edit_gate_allows.py
    ├── test_patch_fails_closed.py
    ├── test_bash_ungated.py
    ├── test_idle_adapter_continues.py
    └── test_idle_adapter_respects_held_gate.py
```

**Probe scenarios** (from issue #563):

| Probe | Scenario | Asserts |
|---|---|---|
| edit gate refuses | fr-enabled repo, base clone, model calls `write` on tracked file | file unchanged; refusal surfaced to model |
| edit gate allows (control) | same, inside valid fr worktree with marker | file changed |
| patch fails closed | `patch` on base-clone target | refused |
| bash is ungated | `bash` writes base-clone file | written (pins documented gap) |
| idle adapter continues | advanceable run, model ends turn | follow-up prompt reaches session |
| idle adapter respects held gate | pending operator gate, model ends turn | **no** follow-up |

**CI integration**: New workflow `.github/workflows/opencode-conformance.yml`:
- Installs `opencode` via `npm install -g @opencode-ai/opencode` (cached)
- Runs `pytest packages/fr-conformance/probes/ -v`
- **No skipif** — missing binary = CI failure (not green skip)

### 4. Parity footnote updates

After probes pass live, update `parity.yaml` scope_notes for:
- `fr-isolation-required` / opencode: change from "partial (not live-proven)" to reflect actual probe results
- `fr-run-idle-guard` / opencode: same — footnote [3] currently says "NOT live-proven"

## Acceptance Rows (born with spec)

| ID | Capability | Acceptance | Origin | Level | Status |
|---|---|---|---|---|---|
| opencode-plugin-delivered | install.sh delivers fr-opencode-plugin | Plugin binary present in ~/.config/opencode/plugins/ after install | super-fr:scripts/install.sh | unit | not-implemented |
| opencode-edit-gate-refuses | edit gate refuses base-clone writes | Real OpenCode binary refuses write in base clone | super-fr:packages/fr-conformance/probes/test_edit_gate_refuses.py | live | not-implemented |
| opencode-edit-gate-allows | edit gate allows worktree writes | Real OpenCode binary allows write in valid worktree | super-fr:packages/fr-conformance/probes/test_edit_gate_allows.py | live | not-implemented |
| opencode-patch-fails-closed | patch on base-clone target refused | Real OpenCode binary refuses patch in base clone | super-fr:packages/fr-conformance/probes/test_patch_fails_closed.py | live | not-implemented |
| opencode-bash-ungated | bash writes base-clone file | Real OpenCode binary allows bash write in base clone | super-fr:packages/fr-conformance/probes/test_bash_ungated.py | live | not-implemented |
| opencode-idle-continues | idle adapter continues advanceable run | Real OpenCode binary continues session on idle | super-fr:packages/fr-conformance/probes/test_idle_adapter_continues.py | live | not-implemented |
| opencode-idle-respects-gate | idle adapter respects held operator gate | Real OpenCode binary does NOT continue when gate held | super-fr:packages/fr-conformance/probes/test_idle_adapter_respects_held_gate.py | live | not-implemented |
| opencode-parity-delivery-tripwire | parity credits only delivered surfaces | Tripwire fails if parity.yaml credits OpenCode surface not installed | super-fr:tests/unit/test_install_copies_opencode_plugin.py | unit | not-implemented |

## Test Plan

1. **Unit**: `test_install_copies_opencode_plugin.py` — install into temp home, verify binary delivered.
2. **Live conformance**: 6 probes in `packages/fr-conformance/probes/` — each runs real `opencode` binary against fixture repo, asserts side effects.
3. **Integration**: `fr harness parity --check` passes with updated footnotes reflecting live probe results.
4. **Uninstall**: `--uninstall` removes plugin binary and nothing else.

## Non-goals

- Publishing fr-opencode-plugin to npm (future, if consumers want `opencode.json` plugin array).
- Hermes/Copilot/Codex conformance (separate issues).
- Changing the plugin's logic (it mirrors `fr-isolation-required.sh` exactly — any bug fixes are separate).

## Migration notes

- Existing consumers who re-run `install.sh` get the plugin automatically.
- No breaking changes to CLI or artifact shapes.
- Version bump: **minor** (new delivered surface).

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|--------|--------|
| 2026-09-22-fix-563-opencode-gates-install | `derio-net/super-fr` | `2026-09-22-fix-563-opencode-gates-install` | — |
