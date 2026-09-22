# Subagent dispatch on OpenCode

Spec: `docs/superpowers/specs/2026-09-19-opencode-subagent-dispatch-design.md`
Issue: [#494](https://github.com/derio-net/super-fr/issues/494) (diagnosis: [#493](https://github.com/derio-net/super-fr/issues/493))

## What this plan is actually fixing

Not a missing capability. Three stale claims that agreed with each other — a
`parity.yaml` row, a line of `fr-goal` prose, and an upstream issue — and, behind
them, artifacts we simply never shipped. OpenCode has had a dispatch primitive the
whole time; this repo's own experiment used it thirteen times while the skill told
the model it did not exist.

So the risk here is not "will it work." It is **shipping a file and calling it a
feature.** `plugins/super-fr/agents/fr-phase-executor.md` could be mirrored perfectly
into `.opencode/agent/` and nothing would change, because `fr-goal` §5 still
instructs the model to run phases inline and both sync scripts copy that instruction
byte-for-byte into every harness's mirror. **Phase 4 is the phase that makes this a
feature.** Phases 1–3 make it possible; phase 4 makes it happen; phase 5 proves it
happened.

## Phase order, and why

**1 — skeleton.** The fourth sync category, base agent only, ending in a live
`opencode agent list` that shows the generated mirror registering as a real subagent
with the permissions we meant. That is the walking skeleton in the literal sense: the
thinnest slice that touches the real runtime. A mock here would prove nothing, because
"does OpenCode read this file the way we think" is the entire question phase 1 exists
to answer.

**2 — tiers.** OpenCode's task tool takes `{prompt, description, subagent_type,
command}` and then resolves the agent *by name*. There is no model parameter. So
per-phase model tiering has exactly one channel — one agent per tier, each carrying
its own `model:` — and the tier set comes from `fr.types.PhaseHeader.tier`, imported,
never re-listed.

**3 — installer.** The mirror serves this repo; a consumer needs the files in
`~/.config/opencode/agent/`. This phase carries the one ordering change in the plan:
delivery moves after the `fr` CLI install, because it now asks `fr models resolve`
what each tier's model is. The integration test is not optional polish — a text
assertion over `install.sh` cannot show that an install works, and this repo has been
bitten by exactly that gap before.

**4 — prose and row.** See above. Also the `TOOL_VOCABULARY` addition, which is what
keeps the new tool name inside a scoped clause instead of leaking a
harness-specific name into every mirror.

**5 — proof and bookkeeping.** One real dispatch against a free model, evidenced from
`opencode.db` rather than from output that a primary agent could have role-played.
Then the acceptance rows move explicitly, and the version bumps minor.

**6 — manual, back-loaded.** A full `/fr-goal` run on a paid model and a real consumer
install. Back-loaded because no agentic phase depends on it: the PR ships with this
phase unimplemented and the operator pushes the evidence to the same PR.

## Things that will be tempting to get wrong

- **Translating `tools:` additively.** Claude Code's `tools:` is an allowlist —
  everything it omits is denied. OpenCode's permission defaults are permissive. Map
  only the allows and the mirrored executor becomes strictly more powerful than its
  source, including the ability to dispatch further subagents, which contradicts the
  "exactly one writer, phases run serially" contract in the agent's own body. The
  mapping is closed: `task: deny` and `webfetch: deny` are part of the translation,
  and both were verified live to round-trip.

- **Letting the frontmatter layout float.** The installer rewrites `model:` in bash.
  That is only safe because the generator emits a fixed order with a single-line
  quoted `description:` and `mode: subagent` as the anchor. If a later change makes
  the description a folded block again, the installer silently stops finding its
  anchor.

- **Baking a user's model into a committed file.** `sync-opencode.py` reads the
  *repo's* `docs/superpowers/models.yaml` — committed, deterministic. User-level
  bindings are resolved at install time, into the global copies. super-fr itself has
  no repo models file, so its own mirror ships model-free and inherits; that is the
  expected state, not an omission.

- **Citing `run-metrics.csv` as though it were on main.** It is not — it lives on
  `feat/presentation-showdown`. The numbers are quoted inline in the spec for exactly
  this reason.

- **Reusing `opencode/north-mini-code-free`.** Gone from the current model list. Pick
  a free model that exists at execution time and journal which one.
