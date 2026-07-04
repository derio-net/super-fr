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
- `packages/*/src/**` — any Python source
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

## Conventions (enforce, don't prose) — #328

Two standing conventions ship as rules **and** as enforcement (the umbrella
principle of #328 is "invariants get a hook / CI gate, not prose"):

- **`no-claude-p-batch`** — never use `claude -p` for batch / per-element LLM
  work (each call cold-starts a full session: ~22k tokens, ~$0.37, ~5s). Use a
  persistent agent session → subagent fan-out → batched prompts. Rule:
  `plugins/super-fr/rules/no-claude-p-batch.md`; CI tripwire:
  `tests/unit/test_tripwire_claude_p.py` (fails if `packages/*/src/**` shells
  out to `claude -p`).
- **`fr-isolation-required`** — edits to tracked source in an fr-enabled repo
  must happen inside an fr-isolation workspace. Enforced by the PreToolUse hook
  `plugins/super-fr/hooks/fr-isolation-required.sh` (registered in `hooks.json`,
  gates Edit/Write/MultiEdit/NotebookEdit), keyed on the `.fr-isolation` marker
  `fr isolation up`/`down` write/remove. Rule:
  `plugins/super-fr/rules/fr-isolation-required.md` (operator) +
  `.claude/rules/fr-isolation-required.md` (repo mirror). A `.fr-isolation`
  tracking tripwire is `tests/unit/test_tripwire_isolation_marker.py`.

Both operator rules install to `~/.claude/rules/` via `install.sh` (a drift
test, `tests/unit/test_install_copies_rules.py`, fails if a shipped rule isn't
wired). When either rule's content changes, flag the operator-side
`~/.claude/rules/` update in the PR description so the two stay in sync.

A third standing convention (2026-07-04, #352): **the acceptance matrix** —
business-level acceptance tests live in `docs/acceptance/matrix.yaml` and are
updated in the SAME PR that changes a Test Plan, adds tests, or ships a
surface. Gate: `fr acceptance check` via
`.github/workflows/acceptance-report.yml` (staleness guard fails a Test-Plan
spec no row cites); repo rule: `.claude/rules/acceptance-matrix.md`; agent
driver: the `fr-acceptance` skill.

## PR workflow expectations

- Feature branch → PR → review → merge. Direct commits to `main` are not
  allowed; branch-protection hooks enforce it.
- Housekeeping commits (archiving a completed plan, updating the spec index)
  also go through a PR — same hook, no exception.
- Pre-commit isn't run locally in this repo; `.github/workflows/ci.yml` is the
  single source of truth for the gate (read it if the commands below ever
  disagree). Currently it runs `ruff check packages/ tests/`, `ruff format
  --check packages/ tests/`, `mypy packages/fr/src packages/fr-dispatch/src
  packages/fr-vk/src`, `pytest`, and `bump-version.py --check`. Before
  pushing, run `uv run ruff format packages/ tests/` and
  `uv run pytest -q --no-cov` yourself — CI is slow to fail-loud.
- `fr apply --yes` enforces the "plan and spec must be on
  `origin/HEAD`" contract before dispatching a GitHub Issue.
  See `docs/superpowers/specs/2026-05-17-dispatch-reachability-gate-design.md`
  for the rationale and `plugins/super-fr-dispatch/skills/fr-dispatch/SKILL.md`
  (Pre-flight) for the operator workflow.

## Follow-up candidates (not urgent)

- Add a CI guard that fails PRs touching `skills/`, `packages/*/src/`, `rules/`, or
  installer scripts without a version bump on `main`. Would make this rule
  load-bearing instead of voluntary. (Drift detection is done — see
  `version-sync` job — but the "did you remember to bump?" guard isn't.)
