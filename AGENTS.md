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
- `fr-dispatch` — runner-agnostic protocol/tick framework. Runners register
  via the `fr.runners` entry-point group, not by editing this package.
- `fr-vk`, `fr-cncd` — runner adapters (`vk`, `cncd`) implementing that
  protocol. `fr-cncd` is real but predates its own README/CLAUDE mentions —
  don't assume tables in `README.md` are exhaustive; check `packages/*/pyproject.toml`
  and `plugins/super-fr/skills/` against prose before trusting a list.
- `fr-opencode-plugin` — **the one non-Python package**: TypeScript/Bun,
  ports the `fr-isolation-required` Claude Code hook to an OpenCode
  `tool.execute.before` plugin. Excluded from the uv workspace
  (`pyproject.toml`'s `[tool.uv.workspace].exclude`); has its own
  `package.json`/version; **not wired into CI** — if you touch it, run
  `bun test` inside `packages/fr-opencode-plugin/` yourself.

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
`test`, `version-sync` jobs) is the single source of truth for the gate; if
this file and `ci.yml` ever disagree, trust `ci.yml` and fix this file. Run
`ruff format` then `pytest` yourself before pushing — CI is slow to fail-loud.

## Skills/rules: canonical source vs. generated mirrors

Never hand-edit a generated file — `scripts/sync-opencode.py` overwrites it
and a CI tripwire will catch drift anyway:

- Canonical: `plugins/super-fr/skills/<name>/SKILL.md`,
  `plugins/super-fr/rules/*.md` (currently `fr-isolation-required.md`,
  `fr-plan-override.md`, `no-claude-p-batch.md`), plus
  `.claude/rules/acceptance-matrix.md` (repo-local-only, no plugin
  equivalent — still a *source*, edit it directly).
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

## This repo dogfoods fr-isolation on itself

super-fr is itself fr-enabled (`.devcontainer/dev` + `.devcontainer/admin`
profiles exist, even with no live `docs/superpowers/plans/` right now — the
devcontainer alone qualifies it). Both the Claude Code PreToolUse hook and
the OpenCode plugin (`.opencode/plugins/fr-isolation-required.ts`, thin
re-export of `packages/fr-opencode-plugin`) block Edit/Write/MultiEdit
outside a valid `.fr-isolation` workspace — editing this repo's own source is
not exempt. Escapes, in preference order: enter isolation (`fr isolation up`),
add an operator-managed path to `.fr-isolation-allow`, or set `FR_BASE_OK=1`
for one deliberate base-clone edit. Full decision tree in
`plugins/super-fr/rules/fr-isolation-required.md`. (The OpenCode port only
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
the three version-bearing surfaces (member `pyproject.toml`s, per-plugin
`plugin.json`, root `marketplace.json`). It also runs `uv sync` and verifies
`uv run fr --version`; commit the changed manifests + `uv.lock` together.
**Gap:** `packages/fr-opencode-plugin/package.json` has its own `version`
field that `bump-version.py` does **not** touch or check — keep it in sync by
hand if you bump while touching that package.

Patch = default (skill copy, CLI fixes, refactors). Minor = user-visible
workflow additions (new subcommand/skill/mandatory behavior) — e.g. the
OpenCode-support release. Major = breaking CLI/plan-schema changes (e.g.
2.0.0's plan-folder rewrite) — rare but not unprecedented, don't assume it
can't happen. If in doubt, patch.

On merge to `main`, `.github/workflows/auto-tag.yml` tags `vX.Y.Z` and
publishes a release automatically from the `pyproject.toml` change — no
human action needed.

## Bridge audit rule

Any brainstorm, spec, or plan touching dispatch / sync / cron / VK card /
workspace / GitHub Issue label-lifecycle surfaces **MUST start by reading
`fr_dispatch.*` + `fr_vk.*`** (`packages/fr-dispatch/src/`,
`packages/fr-vk/src/`) end-to-end first. Confabulating what the bridge does
without reading it is the root cause documented in #147. These two packages
are the canonical read-target for any bridge-behavior investigation (they
replaced a pre-rebuild single script, `agent-images/kali/scripts/vk-issue-bridge.py`).

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

## Known gaps (don't assume these are handled)

- No CI guard fails a PR that touches `skills/`/`packages/*/src/`/`rules/`
  without a version bump — the version-*sync* check (drift between the
  version-bearing files) exists; the version-*bump-forgotten* check doesn't.
- `packages/fr-opencode-plugin`'s `bun test` suite isn't in any CI workflow.
