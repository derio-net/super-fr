# Design: checkout-free install bootstrap + multi-repo instrument command

- **Status:** Reviewed (against Q&A answers + codebase reality, 2026-06-16)
- **Date:** 2026-06-16
- **Slug:** install-bootstrap-and-repo-instrument
- **Author:** fr-goal (operator: derio)

## Problem

Two friction points around adopting super-fr:

1. **The full install needs a manual checkout.** Today the only way to get the
   complete user-level setup (marketplace registration, rules, MCP config, the
   `fr` CLI *with* the VK adapter, validator-wrapper hint) is:

   ```bash
   git clone https://github.com/derio-net/super-fr && cd super-fr && ./scripts/install.sh
   ```

   `scripts/install.sh` hard-requires `PLUGIN_ROOT` to be a clean checkout of
   `main` in sync with `origin` (it rsyncs the checkout into the marketplace
   cache). The two checkout-free paths are partial: the native Claude Code
   marketplace delivers *skills only*, and
   `uv tool install 'git+https://…#subdirectory=packages/fr'` delivers the
   *CLI only*. There is no one-shot, checkout-free path to the full setup.

2. **No way to instrument a set of repos at once.** Each repo the operator runs
   fr against benefits from a `docs/superpowers/plan-config.yaml` (the per-repo
   validation profile). Adding it by hand to every repo is tedious.

## What "a repo needs to work" actually is (investigation result)

The operator asked whether each repo *needs* `docs/superpowers/plan-config.yaml`.
Reading the code end-to-end:

- **`plan-config.yaml` is OPTIONAL.** The only consumer is
  `scripts/validate-plans.sh`, which parses it with `sed` and **falls back to
  built-in defaults** when absent (`FILENAME_PATTERN=YYYY-MM-DD-{name}.md`,
  `REQUIRED_HEADERS=Status`). No Python code loads the file.
- **Its `dispatch:` keys are dead config.** `owner`, `default_repo`,
  `project_board`, `labels` in this repo's copy are **never read** by any code
  (`fr`, `fr_dispatch`, `fr_vk`). `labels.py:198` only name-drops the file in a
  comment. Dispatch resolves repo/owner from the plan's tracking-issue URL and
  the `~/repos/<name>` checkout convention, not from this file.
- **The real per-repo hard requirement is a devcontainer profile**
  (`.devcontainer/<profile>/` + `fr-profiles.yaml`), scaffolded by
  `fr init scaffold` via the `fr-init` skill. That needs an interview
  (credentials, tools) and so is out of scope for batch automation here.

**Consequence:** instrumenting repos with `plan-config.yaml` is still useful —
it gives each repo a real, working *validator profile* (filename pattern,
required headers, status values) and standardizes that across the operator's
repos. The command writes the live validator keys plus a clearly-labelled,
commented, optional `dispatch:` stub for documentation parity. It does **not**
pretend the dispatch keys are functional, and it is **not** a prerequisite for
a repo to "work".

## Goals

- A single remote one-liner that performs the full user-level install with no
  operator-visible checkout.
- A `fr repos` command that instruments **already-checked-out** repos by writing
  `docs/superpowers/plan-config.yaml` in place, driven by a manifest and/or
  positional args, warning (not failing) when a named repo is not checked out
  locally. **It never clones.**

## Non-goals

- Cloning repos. (Operator decision: instrument-only.)
- Scaffolding devcontainer profiles in batch (needs the `fr-init` interview).
- Wiring the `dispatch:` keys into code (separate, larger effort).
- Replacing `scripts/install.sh` — the bootstrap *delegates* to it.

## Design

### Part A — remote one-liner install (`scripts/bootstrap.sh`)

A new `scripts/bootstrap.sh`, hosted (after merge) at
`https://raw.githubusercontent.com/derio-net/super-fr/main/scripts/bootstrap.sh`.

```bash
curl -fsSL https://raw.githubusercontent.com/derio-net/super-fr/main/scripts/bootstrap.sh | bash
# pass-through flags:
curl -fsSL …/bootstrap.sh | bash -s -- --uninstall
```

Behavior (`set -euo pipefail`, idempotent, self-healing):

1. **Preflight deps:** `git`, `uv`, `jq` (the deps `install.sh` already
   requires). Fail loud with an install hint if any is missing.
2. **Managed source dir:** `SRC="${FR_SRC_DIR:-$HOME/.cache/fr/src/super-fr}"`.
3. **Fetch/refresh source:**
   - absent → `git clone https://github.com/derio-net/super-fr "$SRC"`
   - present → `git -C "$SRC" fetch --quiet origin main && git -C "$SRC" reset --hard origin/main`
     (guarantees the clean, in-sync `main` that `install.sh`'s preflight
     demands; makes re-running the one-liner an update).
4. **Delegate:** `exec "$SRC/scripts/install.sh" "$@"` — `install.sh` stays the
   single source of truth for the actual install steps. `bootstrap.sh` only
   manages the source checkout.

Rationale: keeping the real logic in `install.sh` means there is exactly one
install implementation; `bootstrap.sh` is a thin source-manager. The managed
checkout under `~/.cache/fr/src` is invisible to the operator (solves "needs to
checkout the repo") and re-used by future runs.

Security: the README documents the inspect-then-run alternative
(`curl -fsSL …/bootstrap.sh -o bootstrap.sh; less bootstrap.sh; bash bootstrap.sh`)
for operators who don't want to pipe curl into bash.

### Part B — `fr repos sync` (instrument command)

New typer command group `repos_app` in
`packages/fr/src/fr/commands/repos_cmd.py`, registered in `cli.py` via
`app.add_typer(repos_app, name="repos")` (mirrors `init_app`).

```
fr repos sync [OWNER/REPO …] [--manifest PATH] [--yes] [--force]
```

- **Collection = manifest ∪ positional args** (Q3 "Both").
  - Manifest default: `${FR_REPOS_MANIFEST:-$HOME/.config/fr/repos.yaml}`,
    override with `--manifest`.
  - Positional `owner/repo` args are processed **and appended to the manifest**
    (idempotently) so one-offs become durable — unless `--no-save`.
- **Checkout resolution** (no clone): per-entry `path:` if given, else
  `${FR_REPOS_DIR:-$HOME/repos}/<name>` — the same convention
  `fr_dispatch._repo_checkout_root` uses. A small resolver lives in the base
  `fr` package (`fr.repos.checkout_root`) to respect layering
  (`fr_dispatch → fr`, never the reverse); `fr_dispatch` may adopt it later.
- **Per repo:**
  - checkout dir missing / not a git repo → **WARN** (`repo not checked out at
    <path>; skipping`), continue. Never an error exit on its own.
  - `docs/superpowers/plan-config.yaml` already present and no `--force` →
    SKIP (don't clobber operator edits).
  - else → `mkdir -p docs/superpowers/` and write the template.
- **Dry-run by default** (house convention for mutating commands): print the
  planned actions; `--yes` to actually write. Writing into *other* repos makes
  dry-run-default the safe choice.
- **Output:** a per-repo summary line — `WROTE` / `SKIP (exists)` /
  `WARN (missing)` / `DRY-RUN (would write)`.
- **Exit code:** `0` even if some repos warned (warnings are expected, not
  failures); `2` for usage errors (bad manifest, no repos resolved).

#### Manifest format (`~/.config/fr/repos.yaml`)

```yaml
repos:
  - derio-net/super-fr                       # string: path = $FR_REPOS_DIR/super-fr
  - owner/other
  - repo: owner/custom                       # mapping: explicit path override
    path: /Users/derio/Docs/projects/custom
```

Both string and mapping entries accepted. Unknown keys ignored with a warning.

#### `plan-config.yaml` template

The live validator profile plus a commented, optional dispatch stub:

```yaml
# Generated by `fr repos sync`. The validator profile below is read by
# scripts/validate-plans.sh. The dispatch block is OPTIONAL and currently
# documentation-only (not read by code).
plan:
  filename: "YYYY-MM-DD-{name}.md"
  save_to: docs/superpowers/plans/

header:
  required:
    - Spec
    - Status
  status_values:
    - Not Started
    - In Progress
    - Complete

# dispatch:                       # optional, documentation-only
#   target: github-issues
#   owner: <owner>
#   default_repo: <owner>/<repo>
```

`<owner>`/`<owner>/<repo>` are filled from the entry for documentation value.

### Docs + version

- README: add the one-liner to the install section; note `fr repos sync` in the
  per-repo section; add `fr repos` to the CLI table.
- `fr skills` overview (`skills_cmd.py`): add the `fr repos` line.
- **Version bump: minor** (new subcommand + new install mechanism = user-visible
  workflow additions per CLAUDE.md). Bump from main's value at merge time via
  `scripts/bump-version.py minor`; reconcile if another version PR lands first.

## Affected files

- `scripts/bootstrap.sh` (new)
- `packages/fr/src/fr/commands/repos_cmd.py` (new)
- `packages/fr/src/fr/repos.py` (new — manifest model + checkout resolver + template)
- `packages/fr/src/fr/cli.py` (register `repos_app`)
- `packages/fr/src/fr/commands/skills_cmd.py` (mention `fr repos`)
- `README.md` (install one-liner + per-repo + CLI table)
- `tests/` (bootstrap shell test; `fr repos sync` unit tests)
- version-bump set (`pyproject.toml` ×N, plugin.json ×2, marketplace.json, uv.lock)

## Testing strategy

- **`fr repos sync` (Python, TDD):**
  - manifest-only, args-only, both (union + dedup)
  - missing checkout → WARN, exit 0, no write
  - existing `plan-config.yaml` → SKIP without `--force`; overwrite with `--force`
  - dry-run default writes nothing; `--yes` writes; template content matches
  - per-entry `path:` override honored; default `$FR_REPOS_DIR` convention
  - positional arg appended to manifest (and `--no-save` suppresses it)
- **`scripts/bootstrap.sh` (shell):** extend the existing
  `tests/integration/test_install_sh.py` pattern with a `test_bootstrap_sh.py`
  that runs `bootstrap.sh` against a local `file://` clone source (or a
  `FR_SRC_DIR` pointed at a fixture checkout with a stub `install.sh`) to assert
  it fetches/resets and execs `install.sh` with forwarded args. Network clone
  itself is not exercised in CI.

## Open questions

None blocking. Path-resolution default (`$FR_REPOS_DIR`/`~/repos`) follows the
existing dispatch convention; per-entry `path:` is the escape hatch.
