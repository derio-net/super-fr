# Plugin split — seam report

**Date:** 2026-06-05
**Status:** brainstorm artifact — inventory + seam analysis, no decisions yet
**Goal:** find the seams along which superpowers-for-vk could split into a
VK-independent base and a VK-dependent satellite; assess whether the split
makes sense and how each half would work.

## Operator framing (the two modes)

The plugin supports two modes today:

- **local-mode** — everything runs with a single agent in one session:
  brainstorm → spec → plan → inline TDD execution → **one PR per repo**.
  Great for one-shotting a quick feature. Flagship: `vk-goal`.
- **dispatch-mode** — the plan is split into phases, implemented by multiple
  agents that handle everything autonomously, but **each PR is a manual
  quality gate**. Necessary for larger and more sensitive work. VibeKanban
  (via the bridge) currently handles this mode.

The split should make this mode boundary *explicit and tangible*, ideally
distributable as separate parts. Target audience for the base: teams with
GitHub Issues but no VibeKanban.

## Inventory — CLI surface

*(Snapshot at 2.4.2, pre-dispatch-guards. 2.5.0 added `vk status`,
`vk archive`, `vk undispatch`, and `vk migrate dirs` — all base-layer;
see the spec's §Architecture for the current verb set.)*

| Command | What it does | Mode | VK-coupling |
|---|---|---|---|
| `vk plan create` | Scaffold v2 plan folder + spec row | both | none |
| `vk plan edit` | Tick a step / complete a phase | both | none |
| `vk plan rework / rework-add / rework-list` | Sibling rework plans | both | none |
| `vk plan self-review` | Soft lints beyond schema | both | none |
| `vk init scaffold` | Devcontainer profile + secrets scaffolding | both | none |
| `vk isolation up/exec/status/down` | Worktree + devcontainer lifecycle | both | none |
| `vk migrate v1-to-v2` | Plan format migration | both | none |
| `vk skills` | CLI/skill doc surface | both | none |
| `vk spec status` | Spec rollup from gh observation | both | low — projects `vk-ready` states even for never-dispatched plans (known wart) |
| `vk pickup` | Phase scope markdown for an agent | both | dual-use — invoked inline by vk-execute AND embedded in bridge card prompts |
| `vk apply` | Render → observe → diff → apply GH Issues + labels | both, double duty | medium — see "the label protocol" below |
| *(library only)* `vk.bridge.*` + `vk._mcp_client` | Card/workspace dispatch daemon on the pod | dispatch | total |

## Inventory — skills

| Skill | Role | Mode | VK-coupling in the doc |
|---|---|---|---|
| `vk-isolation` | Worktree + devcontainer discipline | both | none ("exec-bridge" is unrelated to the VK bridge) |
| `vk-init` | Operator interview → profile scaffold | both | none |
| `vk-brainstorming` | Isolation-wrapped brainstorming | both | none |
| `vk-plan` | Phase-structured planning | both | none |
| `vk-goal` | Autonomous goal→PR pipeline | local | low — pure inline; ends in a PR |
| `vk-progress` | Status/drift reporting | both | low — reads gh state only |
| `vk-execute` | Phase execution | both | medium — documents label lifecycle, "(or let the bridge) close", "Bridge integration" section |
| `vk-dispatch` | `vk apply` ceremony | dispatch | high — trigger is "send to VK"; reachability gate exists "so the bridge's checkout can see the URLs on its next tick" |

## The three code layers

**Layer 1 — superpowers wrapper (local workflow).** No gh, no VK. The
skills and CLI that wrap superpowers' brainstorm/plan/execute craft in
isolation and phase-structured plan files: `vk-brainstorming`,
`vk-isolation`, `vk-init`, `vk-plan`, the inline core of `vk-execute`,
`vk-goal` as orchestrator. Code: `plan/` (parser, models, format),
`plan_ops.py`, `isolation/`, `spec.py`, `commands/{plan,isolation,init,
skills,spec}_cmd.py`, `migrate.py`. Devcontainer support lives entirely
here. ~4,500 LOC.

**Layer 2 — GitHub dispatch + observation.** Needs `gh`, not VK.
`apply.py`, `observe.py`, `render.py`, `gh.py`/`ghclient.py`/
`real_ghclient.py`, `labels.py`, `diff.py`, `states.py`,
`commands/apply_cmd.py`. Owns: tracking issues, the label lifecycle,
phases-as-issues, multi-repo dispatch, enriched issue bodies, the
reachability gate. ~2,000 LOC.

**Layer 3 — the VibeKanban runner.** `bridge/` + `_mcp_client.py`
(~2,300 LOC). A daemon library — deliberately not wired into the CLI —
consumed by the pod's bridge daemon. Watches the labels Layer 2 creates,
turns `vk-ready` phases into VK cards + workspaces, manages slots,
dedup, lifecycle hooks, orphan reaping.

### Layer 3 splits again: runner framework vs VK adapter

*(Corrected 2026-06-06 after code review — the first version of this
section overstated the separation.)*

Inside the bridge, the *roles* split into generic runner machinery
(concurrency budget, dedup, prompt construction, transition hooks,
PR-state reconciliation, metrics) vs VK adapter (card/workspace
creation) — but the *code* does not split that cleanly today. Only
`lifecycle.py` is genuinely VK-free. `slots.py` (`count_active_ws(mcp)`),
`config.py` (`known_repos(mcp)`, the `vibe-kanban-mcp` wire shape),
`dedup.py` (`fetch_existing_titles(mcp, project_id=…)`), and
`pr_state.py` (`MCPCardClient`, `archive_for_card`) all take MCP clients
and assume VK data shapes; `prompt.py` hardcodes "You are a VK-spawned
agent"; `metrics.py` names every metric `willikins_vk_bridge_*`. The
saving grace is that the MCP surface is duck-typed via Protocols
(`MCPDispatch`, `MCPArchiver`, `MCPWorkspaceClient`), so a runner
framework CAN be extracted — but it is a de-VK-ification refactor
(generalize the Protocols, rename workspace-isms, parameterize prompt
and metric strings), not a free relocation of already-generic modules.

## Mapping layers onto the two modes

The mode boundary does NOT coincide with a layer boundary — that is the
central finding:

- **local-mode = Layer 1 + Layer 2-as-tracking.** `vk-goal` and inline
  `vk-execute` run `vk apply` for *observability*: tracking issues let
  `vk spec status` and the operator see progress, and enriched bodies
  document the work. No one consumes `vk-ready` as a queue.
- **dispatch-mode = Layer 2-as-queue + Layer 3.** The same labels become
  a dispatch protocol: `vk-ready` means "runner, pick this up." The
  reachability gate, pickup-as-prompt, and `vk-synced` only have meaning
  here.

**Layer 2 serves double duty** — state tracking (both modes) and dispatch
queue (dispatch-mode only). Surfaces that only make sense when a runner
is alive:

1. `vk-ready` as a *promise of pickup* — without a runner, dispatched
   issues queue forever. Known wart: inline-shipped plans project
   `vk-ready` indefinitely in `vk spec status` because nothing will ever
   pick them up.
2. `vk-synced` — explicitly "set by the vk-issue-bridge".
3. The dispatch-reachability gate — exists only because a remote
   observer pulls the repo on a tick.
4. `vk pickup` output embedded in card prompts; the "BEFORE YOU BEGIN"
   preamble compensates for shared-pod checkout staleness.
5. Issue bodies enriched to double as VK card descriptions.
6. `vk-dispatch`'s wait-for-pickup semantics and `vk-execute`'s
   "let the bridge close" / "Bridge integration" sections.

## What a second runner implementation could look like

The label protocol + issue body + plan folder is already the full
contract a runner needs. Candidate runners that consume it unchanged:

- **GitHub Actions runner**: workflow on `labeled: vk-ready` → spins a
  Claude Code action job → `vk pickup` → execute phase → PR. No pod, no
  board. Closest to "teams with GH Issues, no VK".
- **Headless CLI runner**: the bridge minus VK — same tick loop
  (`discover_plans` is already board-agnostic), but `dispatch_phase`
  spawns `claude -p` in a `vk isolation` workspace instead of creating a
  card. Reuses slots/dedup/prompt/lifecycle after the de-VK-ification
  described above.
- **Human team as runner**: `vk-ready` issues are a queue humans assign
  themselves; any Claude Code session + `vk-execute` completes a phase.
  The manual-PR-gate property is inherent.
- **Other boards**: Linear/Jira adapter replacing the MCP client behind
  the existing duck-typed Protocols.

## Naming observations

- The CLI (`vk`), every skill (`vk-*`), the labels (`vk-ready`,
  `vk-synced`), and the plugin name (superpowers-for-vk) all carry the
  VibeKanban brand — including the surfaces with zero VK coupling
  (isolation, init, plan). A VK-free base distributed under `vk-*`
  naming misleads.
- `vk-ready`/`vk-blocked`/`vk-synced`/`plan:<slug>`/`spec:<slug>`/
  `phase:<n>` labels are in the wild across DERIO_NET repos (frank,
  paperclip, …); renaming them is a migration, not a find-and-replace.
  (`vk-blocked` is load-bearing — the #251 dependency-gating fix turns
  on it.)

## Open questions (for the design phase)

1. Where does Layer 2 live — base as a runner-agnostic protocol,
   satellite with the bridge, or split (tracking in base,
   queue-semantics activated by a runner)?
2. Should plans declare their mode (`_meta.mode: local|dispatch`) so
   spec status stops projecting `vk-ready` for local plans, the
   reachability gate applies only to dispatch plans, and skill docs can
   branch cleanly?
3. Packaging: one repo / two plugins, two repos, or one repo with an
   optional extra (`pip install X[vk]`)? Where does the pod's bridge
   daemon install from?
4. Naming: what do the base CLI, base skills, and labels get renamed to,
   and what compat shims do existing repos need?
5. Does the bridge's runner-framework 70% (slots, dedup, prompt,
   lifecycle, pr_state) belong to the base/protocol package so future
   runners share it, leaving only the VK adapter in the satellite?
