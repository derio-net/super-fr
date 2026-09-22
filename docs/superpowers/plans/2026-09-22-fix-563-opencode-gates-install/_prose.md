# Plan: OpenCode Gates Install + Live Conformance — #563

## Overview

This plan implements the fix for issue #563: `install.sh` must deliver the `fr-opencode-plugin`
to consumers so OpenCode runs with the isolation edit gate and idle adapter, and adds live
conformance probes to prove the gates work.

## Phase 1: Plugin build + delivery in install.sh (skeleton)

**Goal**: Make `install.sh` build the fr-opencode-plugin as a single binary via `bun build --compile`
and deliver it to `~/.config/opencode/plugins/` when OpenCode is detected.

**Walking skeleton**: The first test run of `install.sh` into a temp HOME with `OPENCODE_SKILLS_INSTALL=1`
will verify the binary is present and executable. This exercises the delivery infrastructure end-to-end.

**Tasks**:
1. Add build step before OpenCode delivery block
2. Add delivery to `OPENCODE_PLUGINS_DIR` in OpenCode block
3. Add uninstall removal
4. Verify with temp HOME install/uninstall

## Phase 2: Parity delivery tripwire test

**Goal**: Add a test that fails when `parity.yaml` credits OpenCode with a surface that `install.sh`
does not deliver.

**Tasks**:
1. Create `tests/unit/test_install_copies_opencode_plugin.py`
2. Test runs `install.sh` into temp HOME, asserts binary delivered
3. Asserts every `enforced`/`partial` OpenCode surface in `parity.yaml` has corresponding delivered artifact
4. Test runs in CI automatically via pytest

## Phase 3: Conformance probes (vendored from agnostic-fr)

**Goal**: Mirror agnostic-fr's conformance engine/mock/probe structure exactly (vendored since
agnostic-fr is private) and create 6 live probes that run the real `opencode` binary.

**Structure** (copied to `packages/fr-conformance/`):
- `engine.py` - launches real harness binary, snapshots repo before/after
- `mock/server.py` - deterministic mock model (OpenAI-compatible)
- `mock/scenario.py` - scripted turns + tool calls → harness wire protocol
- `probes.py` - fixture repo + scenario + assertion over side effects
- `registry/opencode.yaml` - launch cmd, wire protocol, baseURL override
- `probes/` - 6 test files

**6 Probes** (from issue #563):
1. `test_edit_gate_refuses` - base clone write refused
2. `test_edit_gate_allows` - worktree write allowed (negative control)
3. `test_patch_fails_closed` - patch on base clone refused
4. `test_bash_ungated` - bash write allowed (pins documented gap)
5. `test_idle_adapter_continues` - idle run continued
6. `test_idle_adapter_respects_held_gate` - held gate blocks idle continuation

## Phase 4: CI integration

**Goal**: Add GitHub Actions workflow that runs the conformance probes with real `opencode` binary.

**Tasks**:
1. Create `.github/workflows/opencode-conformance.yml`
2. Install `opencode` via `npm install -g @opencode-ai/opencode` (with npm cache)
3. Run `pytest packages/fr-conformance/probes/ -v`
4. **No skipif** — missing binary = CI failure (not green skip)

## Phase 5: Parity footnote updates + version bump

**Goal**: Update `parity.yaml` scope_notes to reflect live probe results, then minor version bump.

**Tasks**:
1. Update `fr-isolation-required` / opencode scope_note
2. Update `fr-run-idle-guard` / opencode scope_note (footnote [3])
3. Run `scripts/bump-version.py minor` (touches install.sh → mandatory bump)

## Acceptance linkage

Each phase advances specific matrix rows (born with spec):
- Phase 1 → `opencode-plugin-delivered`
- Phase 2 → `opencode-parity-delivery-tripwire`
- Phase 3 → all 6 probe rows
- Phase 5 → parity footnotes updated (no matrix row, but verified by `fr harness parity --check`)

## Tier assignments

- Phase 1: mechanical (CLI/script changes)
- Phase 2: mechanical (test only)
- Phase 3: standard (conformance harness + probes)
- Phase 4: mechanical (CI workflow)
- Phase 5: mechanical (doc update + version bump)

All agentic phases are fully agent-completable. No manual phases needed.
