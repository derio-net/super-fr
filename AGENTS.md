# Agent instructions — super-fr

Internal working notes for agents maintaining **this repo** (super-fr itself,
not a repo that merely installs it). User-facing rules the plugin ships to
*consumer* repos live in `plugins/super-fr/rules/`; this file is for agents
changing super-fr's own source. Claude Code reads this via `CLAUDE.md`'s
`@AGENTS.md` import; OpenCode reads it directly plus `opencode.json`'s
`instructions` array (`.opencode/instructions/*.md` — generated, see below).

## Repo shape

uv workspace monorepo, version lockstepped across every manifest (see
"Release / version bumping"). `packages/`:

- `fr` — the CLI/engine: plan-as-folder model, GitHub tracking (render →
  observe → diff → apply, single mutation path in `apply.py`, dry-run by
  default), isolation lifecycle. Entrypoint `fr = "fr.cli:app"`.
  - **`fr journal`** (`fr/journal/`, `commands/journal_cmd.py`) — scope-keyed
    (`spec|plan|debug`) durable run-state under
    `docs/superpowers/journals/{specs,plans,debug}/` (one subdir per scope so
    the tree is glanceable; archived to `implemented/journals/<scope>/`).
    `add` (idempotent
    on `--id`) / `render` (raw, feeds PR bodies) / `check` (fail-closed on open
    findings). `fr plan create` seeds a plan journal; parsing never depends on
    one (back-compat). fr-goal & fr-debugging write it as they run.
  - **`fr models`** (`fr/models.py`, `commands/models_cmd.py`) — `tier → model`
    bindings (`~/.config/fr/models.yaml`, repo override > user) for fr-goal
    subagent dispatch; `PhaseHeader.tier` is the harness-neutral hint.
  - **fr-goal subagent execution** (2026-07-22 spec): fr-goal dispatches each
    phase to the `plugins/super-fr/agents/fr-phase-executor` agent (serial,
    shared workspace); `scripts/ensure-phase-executor-allowlist.sh` (called by
    install.sh) allowlists it in the org agent-worktree hook, else fr-goal
    falls back to inline.
  - **`fr/workflow`** (2026-08-14 spec, `workflow-shapes-and-workitem-dispatch`)
    — the shape axis: `model.py` (`WorkflowManifest`/`Step` schema,
    `parse_manifest`), `resolve.py` (repo > shipped resolution — `fr run
    start`'s real call site), `check.py` (`fr workflow check`: duplicate
    ids, dangling `needs`, cycles, unknown capabilities), `artifacts.py`
    (`REPO_TRACKED_ARTIFACTS`/`IMPLIED_INPUTS_BY_UNIT`/`required_inputs` —
    the vocabulary reachability derives from), `reachability.py`
    (path-level "is this on `origin/HEAD`", no item type — `fr_dispatch`'s
    item-level gate calls into it, never the reverse), `shapes.py`
    (`FR_GOAL_PHASE_DISPATCH` — the default phase-granularity shape `fr
    apply`/the bridge still dispatch against; not yet resolved from a real
    manifest end to end, see the acceptance matrix). `fr.capabilities`
    (`CAPABILITIES`, the closed set `requires:` validates against) is a
    sibling of `fr/workflow`, not inside it; `fr_dispatch.capabilities` is
    a two-line re-export kept for import back-compat.
  - **`fr/run`** — the durable cursor (`docs/superpowers/runs/<run-id>.yaml`,
    git-tracked), driven by `fr run {start,adopt,status,advance,resolve,check}`
    (`model.py`'s `RunState`/`StepRecord`, `commands/run_cmd.py`). `advance`
    executes a `kind: cli` step directly and never a `kind: agent` one — it
    emits a dispatch brief instead; `resolve` is the only way an `agent`
    step's cursor moves past `running`. `plugins/super-fr/workflows/` ships
    the manifests this resolves (`fr-goal.yaml`, the pipeline `/fr-goal`
    itself now narrates); a repo may override one wholesale under
    `docs/superpowers/workflows/<name>.yaml`. Shipped manifests are NOT
    mirrored to OpenCode/Hermes like skills/rules are — `fr run` is a CLI
    surface every harness drives the same way, not a per-harness prompt.
  - **`fr/tracker`** — the tracker protocol (`model.py`'s `Tracker` Protocol
    + `TrackedItem`, a structural stand-in for `WorkItem` so `fr` never
    imports `fr_dispatch`; `github.py`'s `GithubTracker` is the one
    concrete adapter). No second adapter exists yet — protocol-level only.
- `fr-dispatch` — runner-agnostic protocol/tick framework. Runners register
  via the `fr.runners` entry-point group, not by editing this package.
  `work_item.py` (`WorkItem`, the `item_id`/`parent_id` identity grammar)
  and `item_graph.py` (`build_items` — the one item builder for all three
  decomposition units, `run`/`phase`/`spec`) are the dispatch-cutover core;
  `reachability.py` is the item-level gate wrapping `fr.workflow.reachability`.
- `fr-vk`, `fr-cncd` — runner adapters (`vk`, `cncd`) implementing that
  protocol. `fr-cncd` is real but predates its own README/CLAUDE mentions —
  don't assume tables in `README.md` are exhaustive; check `packages/*/pyproject.toml`
  and `plugins/super-fr/skills/` against prose before trusting a list.
- `fr-opencode-plugin` — **the one non-Python package**: TypeScript/Bun,
  ports the `fr-isolation-required` Claude Code hook to an OpenCode
  `tool.execute.before` plugin. Excluded from the uv workspace
  (`pyproject.toml`'s `[tool.uv.workspace].exclude`) and has its own
  `package.json`/version, so `uv run pytest` does not cover it — but it IS
  wired into CI, as the `opencode-plugin-test` job (`bun test`). Run that
  locally inside `packages/fr-opencode-plugin/` if you touch it.

`plugins/super-fr` and `plugins/super-fr-dispatch` are the Claude Code plugin
manifests (skills + rules + hooks) built from those packages.

## Dev commands

```bash
uv sync                                             # install workspace deps
uv run pytest -q --no-cov                           # fast; full `pytest` (CI) also gates cov-fail-under=75
uv run pytest tests/unit/test_foo.py::test_bar -q   # single test
uv run ruff check packages/ tests/                  # lint
uv run ruff format packages/ tests/                 # format (no --check: writes)
uv run mypy packages/fr/src packages/fr-dispatch/src packages/fr-vk/src packages/fr-cncd/src
uv run --no-project python scripts/bump-version.py --check   # version lockstep
```

No local pre-commit hook — `.github/workflows/ci.yml` (`lint`, `typecheck`,
`test`, `validate-artifacts`, `opencode-plugin-test`, `version-sync`,
`version-bump-required` jobs) is the single source of truth for the gate; if
this file and `ci.yml` ever disagree, trust `ci.yml` and fix this file. Run
`ruff format` then `pytest` yourself before pushing — CI is slow to fail-loud.

## Skills/rules: canonical source vs. generated mirrors

Never hand-edit a generated file — `scripts/sync-opencode.py` overwrites it
and a CI tripwire will catch drift anyway:

- Canonical: `plugins/super-fr/skills/<name>/SKILL.md`,
  `plugins/super-fr/rules/*.md` (currently `fr-isolation-required.md`,
  `fr-plan-override.md`, `no-claude-p-batch.md`), plus the THREE
  repo-local-only rules with no plugin counterpart —
  `.claude/rules/acceptance-matrix.md`, `.claude/rules/artifact-versioning.md`
  and `.claude/rules/explainers-currency.md` (still *sources*, edit them
  directly; the list lives in `sync-opencode.py`'s `REPO_LOCAL_ONLY_RULES`).
- Generated: `.opencode/skills/<name>/SKILL.md` and
  `.opencode/instructions/*.md`. After editing a canonical skill/rule, run
  `scripts/sync-opencode.py` (no flag writes; `--check` verifies) and commit
  the regenerated mirror — `test_tripwire_opencode_skills_sync.py` /
  `test_tripwire_opencode_instructions_sync.py` fail on drift.
- `.claude/rules/fr-isolation-required.md` is the one exception: a
  **manually maintained**, deliberately condensed repo mirror of
  `plugins/super-fr/rules/fr-isolation-required.md`. No script covers it —
  update both by hand if the rule's mechanics change.
- `scripts/install.sh` must copy every canonical skill/rule to consumer
  machines; `test_install_copies_rules.py` / `test_install_copies_opencode_skills.py`
  fail if a shipped file isn't wired in.
- **Shipped workflow manifests are a separate, NOT-mirrored category.**
  `plugins/super-fr/workflows/*.yaml` (spec §4.A) has no OpenCode/Hermes
  copy — `fr run` is a CLI surface every harness drives identically, so
  there is nothing harness-specific to generate. It rides install.sh's
  existing wholesale marketplace rsync (no per-file `cp`, unlike
  skills/rules — see the comment above that rsync in `install.sh`);
  `test_install_copies_workflows.py` / `test_install_sh.py::TestInstallWorkflows`
  are its drift guards, and `test_tripwire_shipped_workflows.py` guards
  every shipped manifest passing `fr workflow check`.

## This repo dogfoods fr-isolation on itself

super-fr is itself fr-enabled — `.devcontainer/dev` + `.devcontainer/admin`
profiles exist, and `docs/superpowers/plans/` currently holds three live plans.
Either alone qualifies it. Both the Claude Code PreToolUse hook and
the OpenCode plugin (`.opencode/plugins/fr-isolation-required.ts`, thin
re-export of `packages/fr-opencode-plugin`) block Edit/Write/MultiEdit
outside a valid `.fr-isolation` workspace — editing this repo's own source is
not exempt. Escapes, in preference order: enter isolation (`fr isolation up`),
add an operator-managed path to `.fr-isolation-allow`, or set `FR_BASE_OK=1`
for one deliberate base-clone edit. Two docker-less modes now exist alongside
the default devcontainer mode: **host-worktree** (`FR_ISOLATION_TARGET=worktree`
— fr worktree in the host env, no profile) and **external** (a preparer-written
`mode: external` marker fr adopts, validated by container evidence). Full
decision tree in `plugins/super-fr/rules/fr-isolation-required.md`. (The
OpenCode port only
gates the `edit`/`write`/`patch`/`multiedit` tool calls, not `bash` — a known
gap, not a sanctioned bypass.)

## Release / version bumping

**Any PR that changes user-observable plugin behavior MUST bump the version
before it merges.** The installer caches by version; forgetting this strands
the change on old clients until the number moves next.

Bump if the PR changes any of: `plugins/*/skills/**`, `packages/*/src/**`
(Python), `plugins/super-fr/rules/**`, or `scripts/install.sh` /
`scripts/install-validator-wrapper.sh` / `scripts/validate-plans.sh` (skill
validation itself is `tests/unit/test_skill_validation.py`, not a script —
don't look for `validate-skills.sh`, it was deleted). Do **not** bump for
`docs/**`, `tests/**`, `.github/**`, or `README.md`/`CLAUDE.md`/`AGENTS.md`
alone. Mixed PRs bump.

The workspace-root `pyproject.toml`'s `[project].version` is canonical. Use
`scripts/bump-version.py {patch,minor,major,X.Y.Z,--check}` — never hand-edit
the version-bearing surfaces (member `pyproject.toml`s, per-plugin
`plugin.json`, root `marketplace.json`, or
`packages/fr-opencode-plugin/package.json`). It also runs `uv sync` and verifies
`uv run fr --version`; commit the changed manifests + `uv.lock` together.

Patch = default (skill copy, CLI fixes, refactors). Minor = user-visible
workflow additions (new subcommand/skill/mandatory behavior) — e.g. the
OpenCode-support release. Major = breaking CLI/plan-schema changes (e.g.
2.0.0's plan-folder rewrite) — rare but not unprecedented, don't assume it
can't happen. If in doubt, patch.

On merge to `main`, `.github/workflows/auto-tag.yml` tags `vX.Y.Z` and
publishes a release automatically from the `pyproject.toml` change — no
human action needed.

## Marketplace names are `<org>--<repo>`; the bare org name is retired

A Claude Code marketplace name is a **1:1 namespace over one source repo**:
its manifest at `~/.claude/plugins/marketplaces/<name>/.claude-plugin/marketplace.json`
is a single file listing every plugin of that marketplace, and `install.sh`
populates it with `rsync -a --delete <repo root>/` — replace, never merge.
Two repos claiming one name is therefore mutual eviction, not a conflict.

super-fr installs as **`derio-net--super-fr`**; blog-craft as
`derio-net--blog-craft`. The bare org name `derio-net` is **retired** — super-fr
and blog-craft both claimed it and evicted each other — and both installers
purge it on sight (registry keys, directory, cache, and every `*@derio-net`
id, all dangling once no repo owns the name). Retiring beat awarding it to a
winner: no repo owns an org-level namespace, so the same trap is closed for
`optionality-fr` and any future derio-net plugin, and `<org>--<repo>` makes
the 1:1 rule self-documenting. Root cause in
`docs/superpowers/journals/debug/2026-07-23-marketplace-config-clobber.md`.

Invariants for any installer touching `~/.claude/plugins`, pinned by
`tests/integration/test_install_marketplace_namespace.py`:

- **Name yourself `<org>--<repo>`**, matching your own manifest's `name`.
- **Write the keys you own unconditionally.** `if ! jq -e '."<key>"'` reads as
  idempotence but means first-writer-wins, so another repo's wrong
  `source.repo` survives every reinstall. Converge on your value instead.
- **Only delete keys you own** — or keys nobody owns, like the retired bare
  name. `--uninstall` removing a *live* shared key deregisters every plugin in
  it, not just yours.

Renaming a marketplace moves a path that consumer repos have **committed**:
`scripts/validate-plans.sh` delegates to `marketplaces/<name>/scripts/`. Write
the new path, but keep recognizing the old one, or `ensure_validator_wrapper`
classifies every deployed wrapper as foreign and refuses to upgrade it
(`tests/unit/test_plan_validator_wrapper_rename.py`).

## Bridge audit rule

Any brainstorm, spec, or plan touching dispatch / sync / cron / VK card /
workspace / GitHub Issue label-lifecycle surfaces **MUST start by reading
`fr_dispatch.*` + `fr_vk.*`** (`packages/fr-dispatch/src/`,
`packages/fr-vk/src/`) end-to-end first. Confabulating what the bridge does
without reading it is the root cause documented in #147. These two packages
are the canonical read-target for any bridge-behavior investigation (they
replaced a pre-rebuild single script, `agent-images/kali/scripts/vk-issue-bridge.py`).
Since the 2026-08-14 workitem-dispatch cutover, the seam is **split, not
moved**: `fr_dispatch.tick`'s decision-making (unit/capability/reachability
rules) now calls into `fr.workflow.*` + `fr.capabilities` + `fr.tracker`
(`packages/fr/src/fr/`) rather than owning that logic itself — a bridge
investigation touching *why* an item was or wasn't dispatched needs both
packages, not `fr_dispatch`/`fr_vk` alone; the wire protocol
(`Runner`/`WorkItem`/`tick`'s outer signature) is still entirely
`fr_dispatch`'s.

## Standing conventions enforced by tests, not just prose (#328)

Full rule text auto-loads for both tools (`.claude/rules/` for Claude Code,
`opencode.json`'s `instructions` for OpenCode) — this is a pointer to what
exists and how it's checked, not a restatement:

- **`no-claude-p-batch`** — never shell out to `claude -p` per-element in
  batch work (cold-starts a full session each call: ~22k tokens/~$0.37/~5s).
  Tripwire: `tests/unit/test_tripwire_claude_p.py` (fails on `claude -p` in
  `packages/*/src/**`).
- **`fr-isolation-required`** — see above.
- **acceptance matrix** (2026-07-04) — business-level acceptance tests live
  in `docs/acceptance/matrix.yaml`; any PR that changes a spec's Test Plan,
  adds tests for an existing row, or ships a surface a `not-implemented` row
  waits on updates the matrix in the *same* PR. Gate: `fr acceptance check`
  via `.github/workflows/acceptance-report.yml`. Driver skill: `fr-acceptance`.

## PR workflow

- Feature branch → PR → review → merge; branch-protection blocks direct
  commits to `main`, including housekeeping (archiving a plan, spec-index
  updates).
- `fr apply --yes` refuses to dispatch a plan's phases to a runner unless the
  plan and spec are merged to `origin/HEAD` (the runner works from its own
  checkout of main). See
  `docs/superpowers/implemented/specs/2026-05-17-dispatch-reachability-gate-design.md`.
- `docs/superpowers/implemented/{specs,plans,audits}/` is a real archive, not
  a dead folder — grep it before assuming there's no prior art for a design
  question; specs in particular tend to record the *rationale* a diff alone
  won't show.

## Known gaps

No repo-maintainer known gaps are currently tracked here. Add new gaps when a
constraint is real but not yet enforceable, and remove them as soon as CI or
tooling closes the loop.
