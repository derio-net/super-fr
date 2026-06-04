# Ticket context enrichment

**Spec:** `docs/superpowers/specs/2026-06-04-ticket-context-enrichment-design.md`

## What this plan delivers

GitHub Issues (created by `vk apply` via `render_body`) and VK cards (created
by `vk.bridge.dispatch.dispatch_phase`) stop being bare pointers. After this
plan, every ticket description embeds:

1. a clickable GitHub blob link to the plan's spec (`plan.meta.spec`,
   cross-repo `owner/repo:path` notation handled),
2. the plan's prose (`_prose.md`) in a collapsed `<details>` block,
3. the ticket's phase YAML document (`NN.yaml`) verbatim in a collapsed
   `<details>` + fenced block.

Because v2 bodies are self-healing projections (`observe` reads the live
body, `diff` emits `IssueBodyChange` on drift), the embedded phase YAML
tracks step ticks and completion stamps automatically — GitHub shows live
progress without any new sync machinery.

The VK card description doubles as the spawned agent's workspace prompt
(VK derives the prompt from the linked card via `start_workspace.issue_id`),
so the enrichment lands in front of the executing agent too.

## Shape of the change

- **Phase 1** — `parse()` loads `_prose.md` and raw `NN.yaml` texts onto the
  frozen `Plan` dataclass (`prose`, `phase_texts`). The renderer stays pure
  (no I/O); defaults keep direct `Plan(...)` constructions valid.
- **Phase 2** — `render.py` gains `spec_url()` and `enrichment_block()`
  (deterministic fence-length escaping for YAML that itself contains
  fences; deterministic truncation under GitHub's 65,536-char cap), and
  `render_body()` wires both in. The "static body template" doctrine is
  retired in the docstring.
- **Phase 3** — `dispatch_phase()` appends the same enrichment to the VK
  card description after the four pinned lines (titles untouched —
  `pr_state`/`dedup` parse titles only). Skill docs updated, patch version
  bump.

## Constraints honoured

- Bridge audit rule: `vk.bridge.*` was read end-to-end before design;
  nothing parses card descriptions or Issue bodies in v2, so embedding is
  safe.
- No body-section parsing introduced (rejected create-only enrichment).
- Single PR: spec + plan + implementation ship together on one branch.
