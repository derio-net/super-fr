# Agent instructions — super-fr

Working notes for agents maintaining this repo. User-facing rules that ship with
the plugin live in `rules/`; this file is *internal*.

## Release / version bumping

**Rule:** Any PR that changes user-observable plugin behavior MUST bump the
version before it merges. Forgetting this silently strands the change — the
installer caches by version, so clients stay on the old build until the number
moves.

### When a bump is required

Bump if the PR changes any of:

- `plugins/*/skills/**` — skill docs, including frontmatter metadata
- `src/**` — any Python source
- `plugins/super-fr/rules/**` — user-level rules installed by the plugin
- `scripts/install.sh`, `scripts/install-validator-wrapper.sh`,
  `scripts/validate-plans.sh`, `scripts/validate-skills.sh` — anything the
  installer or validator wrapper runs

Do **not** bump if the PR only touches:

- `docs/**` (plans, specs, archived-plans)
- `tests/**`
- `.github/**`
- `README.md`, `CLAUDE.md`, this rule file

Mixed PRs (some of each) bump, because at least one file that matters changed.

### How to bump

The workspace-root `pyproject.toml` `[project].version` is the **single
canonical source**. Every member package's `pyproject.toml`, the per-plugin
`plugins/*/.claude-plugin/plugin.json`, and the root
`.claude-plugin/marketplace.json` must match it byte-for-byte; the
Python code reads its version dynamically via `importlib.metadata`
(`packages/fr/src/fr/__init__.py`), so it follows pyproject automatically.

Use the helper, not a manual three-file edit:

```bash
scripts/bump-version.py patch       # 2.1.7 -> 2.1.8 (most common)
scripts/bump-version.py minor       # 2.1.7 -> 2.2.0
scripts/bump-version.py major       # 2.1.7 -> 3.0.0
scripts/bump-version.py 2.3.1       # set explicitly
scripts/bump-version.py --check     # verify all three agree (also runs in CI)
```

The script updates all three files, runs `uv sync` to refresh `uv.lock`,
and verifies `uv run fr --version` reports the new number. Commit the
four changed files (three sources + `uv.lock`) together in your PR.

CI runs `bump-version.py --check` on every PR (`version-sync` job in
`ci.yml`) — drift between the three files fails the build.

When the version-bump PR merges to `main`, `.github/workflows/auto-tag.yml`
fires on the `pyproject.toml` change, creates the `vX.Y.Z` tag, and
publishes a GitHub Release with auto-generated notes. No human action
needed once the PR is in.

### Versioning scheme

The project uses tight semver-ish iteration. In practice:

- **Patch** (`1.0.x → 1.0.x+1`): default for skill copy changes, CLI fixes,
  small refactors, added tests that exercise new guards
- **Minor** (`1.y.0 → 1.y+1.0`): reserved for user-visible workflow additions
  (new subcommand, new skill, new mandatory behavior)
- **Major**: not yet used on this plugin

If in doubt, patch.

### Why this matters

The installer (`scripts/install.sh`) reads each plugin's
`plugins/<name>/.claude-plugin/plugin.json::.version` to decide whether to
clear stale cache. If the version
hasn't moved, the cached install stays — even though main has newer commits.
Result: the behavior you just shipped is invisible to every consumer until the
next bump ships.

This has bitten us before — PR #21 (flat-plan deprecation) and #22 (archive
housekeeping) both merged without a bump. The 1.0.11 release (this PR) was
created specifically to propagate that work.

## Bridge audit rule

For any brainstorm, spec, or plan touching dispatch / sync / cron / VK card /
workspace / GitHub Issue label-lifecycle surfaces, the brainstorm MUST start
by reading `fr_dispatch.*` + `fr_vk.*` (rooted at `packages/fr-dispatch/src/` and `packages/fr-vk/src/`) end-to-end.
Confabulating what the bridge does without reading it is the root cause
documented in #147.

Before the v2 rebuild shipped this was
`agent-images/kali/scripts/vk-issue-bridge.py` (1089 LOC). The rebuild
consolidated it into `fr_dispatch.*` (framework) + `fr_vk.*` (adapter) — one repo's code, easier to enforce.
After this PR ships, `fr_dispatch.*` + `fr_vk.*` are the canonical read-target for any
agent investigating bridge behavior.

The user-level mirror of this rule lives in `~/.claude/rules/fr-plan-override.md`
(operator-owned, outside this repo). When this section changes, flag the
operator-side update in the PR description so the two stay in sync.

## PR workflow expectations

- Feature branch → PR → review → merge. Direct commits to `main` are not
  allowed; branch-protection hooks enforce it.
- Housekeeping commits (archiving a completed plan, updating the spec index)
  also go through a PR — same hook, no exception.
- Pre-commit isn't run locally in this repo; CI runs `ruff check`, `ruff format
  --check`, `mypy src/`, and `pytest`. Before pushing, run
  `uv run ruff format src/ tests/` and `uv run pytest -q --no-cov` yourself —
  CI is slow to fail-loud.
- `fr apply --yes` enforces the "plan and spec must be on
  `origin/HEAD`" contract before dispatching a GitHub Issue.
  See `docs/superpowers/specs/2026-05-17-dispatch-reachability-gate-design.md`
  for the rationale and `plugins/super-fr-dispatch/skills/fr-dispatch/SKILL.md`
  (Pre-flight) for the operator workflow.

## Follow-up candidates (not urgent)

- Add a CI guard that fails PRs touching `skills/`, `src/`, `rules/`, or
  installer scripts without a version bump on `main`. Would make this rule
  load-bearing instead of voluntary. (Drift detection is done — see
  `version-sync` job — but the "did you remember to bump?" guard isn't.)
