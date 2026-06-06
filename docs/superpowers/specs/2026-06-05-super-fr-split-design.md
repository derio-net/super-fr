# super-fr split — Design (DRAFT)

**Status:** Draft, reevaluated — the blocker
(`2026-06-05-dispatch-guards-and-implemented-lifecycle-design.md`) shipped
as 2.5.0 (#263, merged 2026-06-06) and this spec's second pass ran against
the merged tree; see §Reevaluation findings. Awaiting operator approval to
go Final and hand off to planning.

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
               + (landed in 2.5.0, all base) archive.py,
                 commands/{status,archive,undispatch}_cmd.py,
                 migrate dirs, plan_locally_complete + archive_gate
                 (render.py), build_plan_report/PlanReport + the
                 legacy-layout hard-stop (commands/common.py),
                 plan_ops.clear_tracking_issue
fr-dispatch    Queue protocol + runner framework
               queue labels (fr:ready / fr:in-progress / fr:pr-ready /
               fr:blocked / fr:synced), reachability gate, runner
               registry, discover_plans + tick, slots, dedup, prompt,
               lifecycle, pr_state, metrics, runner Protocols
               (generalized from the duck-typed MCP seam)
                                                  → depends on fr
               NOTE: extracting these modules is a de-VK-ification
               refactor, not a relocation — today only lifecycle.py is
               VK-free; slots/config/dedup/pr_state take MCP clients
               and assume VK shapes (workspaces, cards, project_id),
               prompt.py and metrics.py hardcode VK strings. Step 2
               scopes this work explicitly.
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

**CLI composition note (from 2.5.0):** the legacy-layout hard-stop lives
in `commands/common.py` and every tree-resolving verb opts in. Any verb
`fr-dispatch` registers onto the `fr` CLI must call the same guard —
this becomes part of the documented extension contract alongside the
runner registry.

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
- `fr undispatch` (shipped in 2.5.0) is the inverse, already designed to
  leave runner workspaces to the runner's own reaper. It is a **base**
  verb: local-mode also creates tracking issues, so closing erroneous
  ones is not dispatch-only — its primary doc home is the base
  (`fr-progress` remedies), with the `fr-dispatch` skill referencing it
  for queue cleanup.

### Label taxonomy (v3)

| Label | Owner | Replaces |
|---|---|---|
| `fr:ready`, `fr:in-progress`, `fr:pr-ready`, `fr:blocked` | fr-dispatch (protocol) | `vk-ready`, `in-progress`, `pr-ready`, `vk-blocked` |
| `fr:synced` | fr-dispatch (protocol — the "already handed to a runner" idempotency marker) | `vk-synced` |
| `runner:<name>` | fr-dispatch (protocol) | — (new) |
| `plan:<slug>`, `phase:<n>`, `spec:<slug>` | fr (attributes) | unchanged |
| `manual` | fr | unchanged |

**Synced-marker ownership (resolved 2026-06-06 after code review):** the
"already dispatched, don't re-dispatch" predicate is read by
`discover_plans`/`tick` — protocol layer — today (`vk-ready` AND NOT
`vk-synced`, the #251 deadlock fix builds on it). So the marker cannot
be adapter-private: it becomes `fr:synced`, owned by fr-dispatch, set by
the protocol after the adapter's `dispatch_phase` returns success.
Adapters MAY still stamp private labels namespaced by runner name
(`vk:<whatever>`); the protocol never reads those — but none are
required for correctness.

Runner names feed the dynamic `runner:<name>` template and therefore go
through the same `_bounded_label_name` 50-char machinery as `plan:` /
`spec:` slugs — the registry contract states this constraint.

## Plugins (marketplace lists two)

- **super-fr (base):** skills `fr-brainstorming`, `fr-isolation`,
  `fr-init`, `fr-plan`, `fr-execute` (inline-only; lifecycle/bridge
  sections removed), `fr-goal`, `fr-progress`. Installer installs the
  `fr` package. Complete for local-mode by itself.
- **super-fr-dispatch:** skills `fr-dispatch` (the `--to` ceremony: the
  2.5.0 three-step pre-flight — `fr status` audit, gh-evidence check for
  never-dispatched plans, reachability gate — plus writeback commit with
  Issue URLs in the body) and `fr-runner`
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
manifests; `bump-version.py` stays the only bump path — but note this is
real surgery, not a file-list extension: the script currently hardcodes
one root `pyproject.toml`, while uv-workspace members each carry their
own. Lockstep needs either N per-member writes or a single
source-of-truth version the members read dynamically; `--check` (and the
CI `version-sync` job) must validate every member plus both plugin
JSONs. First release of the split is **3.0.0**.
No 2.x compat: a 2.x client meeting a v3 repo (or vice versa) fails loud,
by design.

## Migration

Strictly sequenced after dispatch-guards merges. Each step is an
independently shippable PR in this repo unless noted:

1. **Rebase + inherit:** ✅ done 2026-06-06 — branch rebased on 2.5.0,
   module map re-derived from the merged tree (this spec's second pass).
   Remaining: operator approves Draft → Final.
2. **Workspace split:** uv workspace; move modules into `fr` /
   `fr-dispatch` / `fr-vk` per §Architecture; import-direction +
   cross-package contract tests (the bridge regression suite now runs
   against `fr`'s public `diff()`/`Diff.suppressed` from the
   `fr-dispatch` side). Pure refactor, CLI still `vk`.
3. **Rebrand:** repo → `derio-net/super-fr`; CLI binary → `fr`; skill
   dirs → `fr-*`; two plugin manifests; installer rewrite; `vk skills` →
   `fr skills` content; **this repo's own CI workflows**
   (`.github/workflows/vk-spec-status.yml` pins
   `vk @ git+…/superpowers-for-vk@v2.0.0` and runs the `vk` binary —
   both 404/vanish at the rename; `_pr_spec_status.yml` calls it).
   v3.0.0 tags here.
4. **Protocol v3:** `--to` flag + runner registry + label taxonomy;
   `fr-vk` adapter behind it; bridge daemon entry point moves to `fr-vk`.
5. **Pod cutover:** bridge pod installs `fr-vk`; its checkout/cron config
   updates; old `vk` daemon retired the same day (no dual-running — the
   two would fight over label states). **Dual-read, not dual-run:** for
   the rollout window, `fr-vk`'s discovery recognizes BOTH `vk-ready`
   and `fr:ready` (and both synced spellings) — otherwise every
   not-yet-swept repo's queued phases go dark between this step and its
   step-6 PR. This is the one sanctioned exception to "no compat": old
   labels in the wild are *data* to migrate, not API to shim. The
   dual-read is removed in step 7 once the sweep completes.
6. **Repo sweep (subagents, parallel):** one batch per checkout root
   (`~/Docs/projects/DERIO_NET/`, `~/Docs/projects/agentic-stoa/`), one
   subagent per repo in its own worktree, producing one PR per repo that
   bundles: label rename (`vk-ready`→`fr:ready` etc. via gh), in-repo
   rules/docs references, and `.claude/settings*` allowlist updates
   (`vk status*` → `fr status*` — allowlists reference the binary name
   and break silently otherwise). The `migrate dirs` bundling originally
   planned here is moot: the 2.5.0 rollout already ran it per repo
   (PRs #107/#480/#12/#226), so all repos are on the `implemented/`
   layout before the sweep starts.
7. **Cleanup + operator config:** remove the step-5 label dual-read once
   every repo's sweep PR is merged; user-level rules files, the
   vk-plan-override mirror, shell completion. Last, because everything
   before it must already answer to `fr`.

Rollback story: steps 2–4 are in-repo and revert cleanly; step 5–6 are
the point of no return — hence the sweep bundles everything per repo in
one reviewable PR rather than trickling renames.

## Reevaluation findings (2026-06-06, against the merged 2.5.0 tree)

The draft's blocked-by interactions, resolved item by item:

1. ✅ **Module map re-derived.** All 2.5.0 additions are base-package as
   predicted, now pinned to real locations (§Architecture): the shared
   read pipeline is `commands/common.py::build_plan_report` returning
   `PlanReport`; the archive gate is `render.py::archive_gate` (shared by
   archive/apply/status, exactly the one-definition shape the split
   needs); the legacy-layout hard-stop lives in `commands/common.py` and
   becomes part of the CLI extension contract for `fr-dispatch` verbs.
2. ✅ **Bridge contract confirmed.** The 73-test bridge suite passed
   untouched against `diff(force_create=)` defaults — that suite is the
   ready-made cross-package contract suite at the `fr`/`fr-dispatch`
   boundary (migration step 2 relocates it, semantics frozen).
3. ✅ **Skill text re-split mapped.** vk-dispatch's new three-step
   pre-flight moves whole into the `fr-dispatch` skill; the
   archive/status text added to vk-goal/vk-progress is base-side; the
   `undispatch` documentation gets a base home (`fr-progress` remedies)
   since local-mode tracking issues need it too — the one assignment the
   draft had wrong (it was dispatch-plugin-only).
4. ✅ **No new plan-file fields.** `plan/models.py` and `plan/parser.py`
   untouched by 2.5.0 — the "derive, don't store" doctrine held, and the
   runner-as-Issue-labels design needs no rework.
5. ✅ **Hard-stop already absorbed fleet-wide.** The 2.5.0 rollout ran
   `migrate dirs` per repo (PRs #107/#480/#12/#226), so the v3 sweep no
   longer bundles it (migration step 6 simplified).
6. ✅ **`vk status*` allowlists** confirmed as a real migration surface —
   the skill doc explicitly markets allowlist-safety; step 6 covers the
   rename to `fr status*`.

Remaining before planning: operator approves Draft → Final, then hand
off to fr-plan (vk-plan).

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
