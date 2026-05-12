# vk-v2-library Rework 1 — Renderer Fix + `vk.bridge` Library

**Parent:** `docs/superpowers/archived-plans/2026-05-09-vk-v2-library/` (Complete)

**Why this exists.** Two items surfaced after the parent plan shipped and
were scoped out of it. Both stem from the parent being a single-target
plan (`target_repo: derio-net/superpowers-for-vk`) that didn't touch the
bridge, while spec §"Bridge integration — `vk.bridge.*`" describes a
library-and-thin-wrapper split that crosses repos.

1. **Renderer mis-numbers cross-phase dependencies.** `vk.render._render_body`
   writes `- Blocked by #{phase_number}` instead of the dependency's
   tracking Issue number. The bridge parses `#N` as an Issue number, so
   any v2 plan with cross-phase deps gets silently mis-gated. Single-phase
   plans and plans where every phase declares `depends_on: []` are
   unaffected, which is why the bug never bit during the parent plan's
   own dispatch (which never went through `vk apply`).

2. **`vk.bridge.*` library was never written.** Spec lines 560-577 describe
   `vk.bridge.discover_plans()` and `vk.bridge.tick()` as the intended API
   the bridge should import. Today the bridge at
   `agent-images/kali/scripts/vk-issue-bridge.py` (note: NOT `willikins/`
   as the spec mistakenly said) maintains its own parser and dispatch
   loop. That works but duplicates logic that should live in `vk`.

Plan B (sibling, in agent-images) refactors the live bridge to consume
this library. Plan B is blocked on the v2.1.0 release this plan ships.

## Architecture

### Phase 1 — Renderer fix

The renderer takes a `Plan` and a `PhaseDoc` and produces the body text.
For `## Dependencies`, the integer in `- Blocked by #N` must be a GitHub
Issue number, not a phase number.

Source of truth for the mapping `phase_number → issue_number`:

- **Persisted state:** each `phase.tracking_issue` (set after first
  successful `apply()` run, stored in the phase yaml).
- **In-flight state:** `created_issues: dict[int, str]` returned by
  `apply()` for Issues created in the current run.

The renderer must accept the map as a parameter rather than rebuilding
it on its own. `diff.py` already iterates the plan and knows which
phases are getting created vs updated; it's the natural place to
assemble the map and pass it to `_render_body`.

### Phase 2 — `vk.bridge` module

A new sub-package `vk.bridge` exposing two functions:

```python
def discover_plans(repo: str, gh: GhClient) -> list[Plan]:
    """Return v2 plans in `repo` whose Issues carry `vk-ready` label."""

def tick(plan: Plan, gh: GhClient, vk_mcp: VkMcpClient) -> TickResult:
    """One cron iteration: observe → render → diff → apply (GH-only)
    → update VK board cards from the rendered state.
    Never writes to the consumer repo's checkout — apply mutates only GH."""
```

Plus:

```python
@dataclass(frozen=True)
class TickResult:
    synced: int        # cards updated / created
    errors: int        # caught GH or MCP failures
    skipped: int       # plans without vk-ready Issues
    failures: tuple[str, ...]
```

`VkMcpClient` is an injected interface so the bridge can stub it in
tests. We don't ship an MCP client implementation — the live bridge
already has one (`agent-images/kali/scripts/vk_mcp_client.py`).

These functions are NOT registered in the `vk` CLI (`vk apply` etc.).
Per spec line 562: "Not part of the operator-facing CLI."

### Phase 3 — Release v2.1.0

Minor bump (new public API surface). Standard ceremony: version files,
changelog, tag, install, smoke check.

## Hand-off

After Phase 3 ships, Plan B (sibling in `derio-net/agent-images`)
imports `vk.bridge.tick` from the new release and replaces the live
bridge's hand-rolled loop.
