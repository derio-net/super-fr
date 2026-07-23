# Hermes Agent — working on super-fr

You are Hermes Agent working in the **super-fr** repo.

> **Read `AGENTS.md` now, before your first edit.** It is this repo's canonical
> agent guide (repo shape, dev commands, release rules, conventions). Hermes
> loads **only one** project context file — `.hermes.md`/`HERMES.md` outranks
> `AGENTS.md` — so this file being present means `AGENTS.md` is **not**
> auto-injected. Nothing here replaces it; the rules below are the subset that
> is unsafe to discover late.

## Non-negotiables

**1. Never edit the base clone — work inside an fr-isolation workspace.**
This repo dogfoods its own isolation gate. A `pre_tool_call` hook denies
`write_file`/`patch` outside a valid `.fr-isolation` worktree, and denies
git/gh mutations and merged-PR pushes from the base clone.

```bash
fr isolation up --branch feat/<slug>     # then edit inside the worktree it prints
```

Escapes, in preference order: enter isolation; add an operator-managed path to
`.fr-isolation-allow`; `FR_BASE_OK=1` for one deliberate base-clone edit.

**2. Never commit to `main`.** Branch → PR → review → merge. Branch protection
blocks direct pushes, including housekeeping.

**3. Bump the version when plugin behavior changes.** Any PR touching
`plugins/*/skills/**`, `packages/*/src/**`, `plugins/super-fr/rules/**`, or
`scripts/install.sh` must bump before merge — the installer caches by version.

```bash
uv run --no-project python scripts/bump-version.py {patch|minor|major}
```

Do **not** hand-edit version-bearing manifests. Docs/tests-only PRs don't bump.

**4. Never hand-edit a generated mirror.** `.hermes/`, `.opencode/skills/`,
`.opencode/instructions/`, `.opencode/commands/` are generated. Edit the
canonical source under `plugins/super-fr/{skills,rules}/`, then regenerate —
CI tripwires fail on drift:

```bash
uv run python scripts/sync-hermes.py      # .hermes/ mirrors
uv run python scripts/sync-opencode.py    # .opencode/ mirrors
```

**5. Never shell out to `claude -p` per element in batch work.** Each call
cold-starts a whole session (~22k tokens, ~$0.37, ~5s). A CI tripwire enforces
this. Use one warm session, subagent fan-out, or batch K items per prompt.

## The gate before you push

`.github/workflows/ci.yml` is the source of truth; run it locally first:

```bash
uv run pytest -q --no-cov                     # full suite (~6 min on macOS)
uv run ruff check packages/ tests/ scripts/
uv run ruff format packages/ tests/ scripts/
uv run mypy packages/fr/src packages/fr-dispatch/src packages/fr-vk/src packages/fr-cncd/src
uv run --no-project python scripts/bump-version.py --check
```

The suite is subprocess-heavy (real `git`/`install.sh` runs), so it is slow
locally but ~1m on CI. During the edit loop run scoped files
(`uv run pytest tests/unit/test_<x>.py -q --no-cov`); run the full suite before
pushing.

## Hermes specifics

- **Skills** live at `~/.hermes/skills/fr/<name>/SKILL.md` — invoke them as
  slash commands (`/fr-goal`, `/fr-plan`, `/fr-debugging`, …).
- **Phase execution**: `fr-goal` dispatches each plan phase with
  `delegate_task(goal, context)`. Hermes subagents start with a **fresh
  conversation and know nothing**, so the brief must be self-contained — pass
  `fr pickup` output, the spec, and `fr journal render --scope plan` in
  `context`.
- **Models**: super-fr ships **no** `hermes:` model bindings on purpose.
  `fr models resolve --harness hermes --tier <t>` is unbound so `fr-goal` asks
  you for a model per tier on the first run and persists it with
  `fr models set`. Do not invent model ids.
- **Rules** reach you through a managed block in `~/.hermes/SOUL.md`
  (delimited by `<!-- super-fr:rules START/END -->`) — never hand-edit it;
  re-run `fr hermes install`.

## Where things are

`packages/fr` is the CLI/engine (plans, journals, isolation, acceptance);
`packages/fr-dispatch` + `fr-vk`/`fr-cncd` are the runner protocol and adapters;
`plugins/super-fr*` are the shipped skills/rules/hooks. `AGENTS.md` has the full
map, the bridge-audit rule, and the marketplace-naming invariants — read it.
