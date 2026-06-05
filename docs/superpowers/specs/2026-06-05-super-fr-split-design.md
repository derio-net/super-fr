# super-fr split — Design (DRAFT)

**Status:** Draft — blocked-by
`2026-06-05-dispatch-guards-and-implemented-lifecycle-design.md`, which
ships first and edits the same modules (`render.py`, `diff.py`,
`apply_cmd.py`, `spec.py`, four skill docs). Reevaluate this spec against
the merged result before planning; see §Reevaluation checklist.

Companion artifact: `docs/superpowers/brainstorms/2026-06-05-plugin-split-seam-report.md`
(full CLI/skill inventory and seam analysis this design rests on).

## Problem

The plugin supports two modes whose boundary is implicit:

- **local-mode** — one agent, one session: brainstorm → spec → plan →
  inline TDD execution → one PR per repo. One-shots a quick feature.
- **dispatch-mode** — the plan splits into phases implemented by multiple
  autonomous agents; each phase PR is a manual quality gate. Required for
  larger and more sensitive work. VibeKanban (via the bridge) is the only
  runner today.

The implicit boundary causes real costs: the brand (`vk` CLI, `vk-*`
skills, `vk-ready` labels, plugin name) claims VibeKanban everywhere,
including the ~70% of the surface with zero VK coupling; teams with
GitHub Issues but no VK cannot adopt the dispatch protocol; the label
lifecycle serves double duty (tracking vs queue) that the code cannot
distinguish; and the bridge's generic runner machinery (slots, dedup,
prompt, lifecycle hooks) is welded to its one VK adapter.

## Decisions (made in brainstorm, 2026-06-05)

| Decision | Choice |
|---|---|
| Base audience | Teams with GitHub Issues, no VK |
| Local-mode tracking | Keeps GitHub tracking issues (observability stays) |
| Split shape | Approach B: three packages — base / dispatch protocol / VK adapter |
| Packaging | One repo, lockstep versions, uv workspace |
| Mode declaration | None in plan files — runner chosen at dispatch time, recorded on the Issue |
| Rebrand depth | Full, no shims, no deprecation: **v3 breaking release** |
| Names | Repo `derio-net/super-fr`; CLI `fr`; skills `/fr-*`; packages `fr`, `fr-dispatch`, `fr-vk` |

## Architecture — three packages

```
fr             Layer 1 + tracking duty
               plan/ (parser, models, format), plan_ops, isolation/,
               spec, migrate, pickup, apply/observe/render/diff,
               gh + ghclient + real_ghclient, labels (state labels),
               states, _urls, _yaml
               + (inherited from dispatch-guards) status, archive,
                 undispatch, migrate dirs, plan_locally_complete,
                 Diff.suppressed
fr-dispatch    Queue protocol + generic runner framework
               queue labels (fr:ready / fr:in-progress / fr:pr-ready),
               reachability gate, runner registry, discover_plans + tick,
               slots, dedup, prompt, lifecycle, pr_state, metrics,
               runner Protocols (the existing duck-typed MCP seam,
               generalized)                       → depends on fr
fr-vk          VibeKanban adapter
               _mcp_client, dispatch_phase (card + workspace creation),
               workspaces, bridge daemon CLI, private label vk:synced
                                                  → depends on fr-dispatch
```

Dependency direction is enforced by import-direction CI tests (B2 style):
`fr` imports neither sibling; `fr-dispatch` never imports `fr-vk`
(adapters register via entry points, below).

**The one documented soft point:** `fr apply --to <runner>` lives in the
base CLI but requires `fr-dispatch`. The flag's handler does
`importlib.util.find_spec("fr_dispatch")`; missing → exit 2 with
"dispatching to a runner requires fr-dispatch". No other base code path
references the siblings.

**Runner registry:** `fr-dispatch` resolves `--to <name>` via the
`fr.runners` entry-point group. `fr-vk` registers `vk`; a future
GitHub-Actions runner registers `gha`; a headless-CLI runner registers
`local-daemon`. A runner implements the Protocols `fr-dispatch` already
defines implicitly today (the `FakeMcpClient` seam, promoted to public
contract).

## Runner choice at dispatch time

No plan-side mode field — consistent with dispatch-guards' doctrine
("if it can be derived, don't store it"). The choice is recorded where it
acts: on the GitHub Issue, as labels.

- `fr apply` — reconcile tracking issues only: state labels, no queue
  label. This is local-mode's entire gh footprint.
- `fr apply --to vk` — same reconcile, plus `fr:ready` + `runner:vk` on
  phases entering the queue. The reachability gate (plan/spec on
  `origin/HEAD`) applies only on `--to` invocations — it exists for
  remote observers and inline users never pay it.
- Downstream projection derives from observation: `fr status` /
  `fr spec status` show "queued" only when a runner label is observed.
  Per-phase mixing is legal (phase 1 executed inline, phases 2–4 queued).
- `fr undispatch` (shipping in dispatch-guards) is the inverse, already
  designed to leave runner workspaces to the runner's own reaper.

### Label taxonomy (v3)

| Label | Owner | Replaces |
|---|---|---|
| `fr:ready`, `fr:in-progress`, `fr:pr-ready` | fr-dispatch (protocol) | `vk-ready`, `in-progress`, `pr-ready` |
| `runner:<name>` | fr-dispatch (protocol) | — (new) |
| `vk:synced` | fr-vk (adapter-private dedup marker) | `vk-synced` |
| `plan:<slug>`, `phase:<n>` | fr (attributes) | unchanged |
| `manual` | fr | unchanged |

Adapter-private labels are namespaced by runner name; the protocol never
reads them.

## Plugins (marketplace lists two)

- **super-fr (base):** skills `fr-brainstorming`, `fr-isolation`,
  `fr-init`, `fr-plan`, `fr-execute` (inline-only; lifecycle/bridge
  sections removed), `fr-goal`, `fr-progress`. Installer installs the
  `fr` package. Complete for local-mode by itself.
- **super-fr-dispatch:** skills `fr-dispatch` (the `--to` ceremony:
  pre-flight incl. the gh-evidence check from dispatch-guards,
  reachability gate, writeback commit with Issue URLs) and `fr-runner`
  (new: operate/verify/debug a runner — tick health, stuck cards, orphan
  workspaces; the operator surface the bridge never had). Installer
  installs `fr-dispatch` + the default adapter `fr-vk`.
- The pod consumes no Claude plugins: it pip-installs `fr-vk` (pulling
  `fr-dispatch` + `fr` transitively), replacing today's `vk` install.

Operator-level rules (`~/.claude/rules/vk-plan-override.md`) are replaced
by `fr`-named equivalents in the same sweep (§Migration); skill override
routing (`writing-plans` → `fr-plan`) carries over verbatim.

## Versioning

Single lockstep version across the three packages and both plugin
manifests; `bump-version.py` grows from three files to the workspace set
and stays the only bump path. First release of the split is **3.0.0**.
No 2.x compat: a 2.x client meeting a v3 repo (or vice versa) fails loud,
by design.

## Migration

Strictly sequenced after dispatch-guards merges. Each step is an
independently shippable PR in this repo unless noted:

1. **Rebase + inherit:** absorb dispatch-guards (new verbs, suppressed
   diffs, `implemented/` taxonomy, skill-doc text) into the split's
   module map. Update this spec from Draft to Final (§Reevaluation).
2. **Workspace split:** uv workspace; move modules into `fr` /
   `fr-dispatch` / `fr-vk` per §Architecture; import-direction +
   cross-package contract tests (the bridge regression suite now runs
   against `fr`'s public `diff()`/`Diff.suppressed` from the
   `fr-dispatch` side). Pure refactor, CLI still `vk`.
3. **Rebrand:** repo → `derio-net/super-fr`; CLI binary → `fr`; skill
   dirs → `fr-*`; two plugin manifests; installer rewrite; `vk skills` →
   `fr skills` content. v3.0.0 tags here.
4. **Protocol v3:** `--to` flag + runner registry + label taxonomy;
   `fr-vk` adapter behind it; bridge daemon entry point moves to `fr-vk`.
5. **Pod cutover:** bridge pod installs `fr-vk`; its checkout/cron config
   updates; old `vk` daemon retired the same day (no dual-running — the
   two would fight over label states).
6. **Repo sweep (subagents, parallel):** one batch per checkout root
   (`~/Docs/projects/DERIO_NET/`, `~/Docs/projects/agentic-stoa/`), one
   subagent per repo in its own worktree, producing one PR per repo that
   bundles: label rename (`vk-ready`→`fr:ready` etc. via gh), `fr migrate
   dirs` (the dispatch-guards legacy hard-stop fires once, here),
   in-repo rules/docs references, and `.claude/settings*` allowlist
   updates (`vk status*` → `fr status*` — allowlists reference the binary
   name and break silently otherwise).
7. **Operator config:** user-level rules files, the vk-plan-override
   mirror, shell completion. Last, because everything before it must
   already answer to `fr`.

Rollback story: steps 2–4 are in-repo and revert cleanly; step 5–6 are
the point of no return — hence the sweep bundles everything per repo in
one reviewable PR rather than trickling renames.

## Interactions with dispatch-guards (why this is a draft)

1. Its `plan_locally_complete` + suppressed creates + factual staleness
   header dissolve most of the tracking-vs-queue ambiguity this design
   originally chased — our baseline improves before we start.
2. Its new verbs (`status`, `archive`, `undispatch`, `migrate dirs`) are
   all base-package; `undispatch` already respects the dispatch/adapter
   seam (leaves cards to `reap_orphans`).
3. Its `diff(force_create=)` / `Diff.suppressed` and the shared
   apply/status read-helper become **public cross-package API** under the
   split; its "bridge suite passes untouched" guarantee must be preserved
   as a contract test at the new boundary.
4. Its legacy-layout hard-stop and our v3 break must hit each repo once,
   together (step 6).
5. Its `vk status*` allowlistability survives only if the sweep updates
   allowlists to `fr status*`.
6. Both efforts edit the same files — no parallel implementation;
   sequence strictly after its merge.

## Reevaluation checklist (run when dispatch-guards is live)

- [ ] Re-derive §Architecture's module map from the merged tree (new
      commands files, the shared read-helper's location).
- [ ] Confirm the bridge regression suite still passes with `diff()`
      defaults across the package boundary as planned.
- [ ] Re-read the four updated skill docs and re-split their text between
      `fr-execute` (inline) and `fr-dispatch`/`fr-runner`.
- [ ] Check no new plan-file fields appeared that violate the
      runner-at-dispatch-time decision.
- [ ] Promote this spec Draft → Final, then hand off to fr-plan
      (vk-plan).

## Out of scope

- Building the GitHub-Actions or headless runners — the registry and
  Protocols make room; the adapters are their own features.
- Converting other boards (Linear/Jira) — same.
- Any change to superpowers upstream; the base remains a wrapper.
- History rewrite of existing labels/issues — old closed Issues keep old
  labels; only open/active surfaces migrate.

## Testing

- Import-direction tests per package (extend the B2 single-source style).
- Cross-package contract test: bridge tick semantics against `fr`'s
  public diff/observe surface.
- Runner-registry test: a fake entry-point runner receives dispatch.
- Label-taxonomy round-trip: `--to vk` projects `fr:ready` + `runner:vk`;
  plain `apply` never emits queue labels; observe-side recognizes both.
- Sweep rehearsal: the per-repo migration runs against a fixture repo in
  CI (labels, dirs, allowlists) before any real repo.

## Implementation Plans

(added by fr-plan after Draft → Final)
