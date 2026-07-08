# Adapting super-fr's skills/rules/hooks for OpenCode

**Date:** 2026-07-08
**Status:** Draft — brainstormed with operator (batched Q&A, 2026-07-08).
**Target repo:** derio-net/super-fr.

## Problem

super-fr ships all of its operator-facing behavior (skills, rules, isolation
enforcement) through the **Claude Code plugin system**: `plugin.json` +
`marketplace.json` + `enabledPlugins` in `~/.claude/settings.json`, with
skills nested at `plugins/<plugin>/skills/<name>/SKILL.md`, rules installed to
`~/.claude/rules/`, and a PreToolUse shell-script hook
(`plugins/super-fr/hooks/fr-isolation-required.sh`) wired via
`plugins/super-fr/.claude-plugin/hooks.json`.

OpenCode (github.com/anomalyco/opencode, formerly sst/opencode) is a separate
agent runtime. Verified against its docs (2026-07-08):

- **Skills:** natively discovers plain `SKILL.md` files (no plugin/marketplace
  wrapper) from `.opencode/skills/<name>/SKILL.md`, `.claude/skills/<name>/SKILL.md`,
  or `.agents/skills/<name>/SKILL.md`, both project-local (walked up to the git
  worktree root) and global (`~/.config/opencode/skills/`, `~/.claude/skills/`,
  `~/.agents/skills/`). Frontmatter only recognizes `name`, `description`,
  `license`, `compatibility`, `metadata` — extra keys are ignored (harmless for
  our existing frontmatter, which is just `name` + `description`).
- **Critically:** OpenCode's `~/.claude/skills/` fallback is for bare,
  directly-placed skills — it does **not** understand Claude Code's plugin
  cache (`~/.claude/plugins/cache/<marketplace>/<plugin>/skills/...`). So
  super-fr's skills are invisible to OpenCode today, on both project and
  global paths, regardless of whether the operator has the Claude plugin
  installed.
- **Rules:** OpenCode has no direct equivalent of a `~/.claude/rules/`
  directory. Its instruction surfaces are `AGENTS.md` (project/global,
  falls back to `CLAUDE.md` if no `AGENTS.md`) plus an `instructions` array in
  `opencode.json` that can point at arbitrary markdown files (local or remote
  URL).
- **Hook enforcement:** OpenCode plugins are JS/TS modules (loaded from
  `.opencode/plugins/` or npm, run under Bun) exporting hook functions like
  `tool.execute.before` / `tool.execute.after` — not shell scripts keyed off a
  `hooks.json` PreToolUse registration. Porting `fr-isolation-required.sh`
  means writing a new OpenCode plugin package, not reusing the shell script.

## Decisions (operator, 2026-07-08 batched Q&A)

| Question | Answer |
|---|---|
| Scope | **Full parity** — skills + rules + an OpenCode plugin package reimplementing `fr-isolation-required` enforcement |
| Delivery | **Both** — an in-repo `.opencode/skills/` (and `.opencode/plugins/`) for anyone using super-fr's own worktree in OpenCode, *and* installer support so consumer repos/operators get it too |
| Skill sets adapted now | **core only** (`fr-goal`, `fr-plan`, `fr-execute`, `fr-brainstorming`, `fr-init`, `fr-isolation`, `fr-progress`, `fr-debugging`, `fr-acceptance` from `super-fr`). `super-fr-dispatch` (`fr-dispatch`, `fr-runner`) is **out of scope** for this pass. |
| Version bump | **Minor** — new user-visible capability (OpenCode support), not just internal plumbing |

## Design

### 1. Single source of truth stays `plugins/super-fr/skills/`

Skill content is not duplicated. `plugins/super-fr/skills/<name>/SKILL.md`
remains canonical (Claude Code plugin still reads it from there). OpenCode
delivery is **generated**, not hand-maintained:

- New script `scripts/sync-opencode-skills.py`: for every
  `plugins/super-fr/skills/*/SKILL.md`, copy (not symlink — symlinks break
  cross-repo distribution and any `.opencode/` bundling/zip step) into
  `.opencode/skills/<name>/SKILL.md` at the repo root. A comment header is
  NOT injected (would break the "must start with YAML frontmatter" rule) —
  instead the script writes a sibling `.opencode/skills/<name>/.source` file
  pointing back at the canonical path, for drift-detection only.
- CI gate (new `tests/unit/test_tripwire_opencode_skills_sync.py`): fails if
  `.opencode/skills/<name>/SKILL.md` differs from
  `plugins/super-fr/skills/<name>/SKILL.md` (byte-for-byte) or if the set of
  names differs — catches "edited one copy, forgot the other."
- `.opencode/skills/` is committed (not gitignored) so a bare `git clone` of
  super-fr is immediately usable from OpenCode with zero install step.

### 2. Installer support for consumer repos/operators

`scripts/install.sh` gains an additional, independent step (does not touch
existing Claude-plugin logic):

- Copy each `plugins/super-fr/skills/<name>/SKILL.md` into
  `~/.config/opencode/skills/<name>/SKILL.md` (OpenCode's *native* global
  path — deliberately NOT `~/.claude/skills/`, to avoid a bare-skill copy
  shadowing/duplicating the Claude Code plugin-managed copy for people running
  both agents).
- Skip silently (log one line) if `~/.config/opencode` doesn't exist yet and
  the operator hasn't opted in — detect via `OPENCODE_SKILLS_INSTALL=1` env
  var or presence of an existing `~/.config/opencode/` dir (i.e. "the operator
  already uses OpenCode"). No hard dependency on OpenCode being installed.
- `--uninstall` path removes the same files.

### 3. Rules → `AGENTS.md` + `opencode.json` instructions

super-fr's operator rules — the canonical, installer-shipped set is
`plugins/super-fr/rules/*.md` (currently `fr-plan-override.md`,
`fr-isolation-required.md`, `no-claude-p-batch.md`; verified against
`tests/unit/test_install_copies_rules.py`, which fails if a shipped rule
isn't wired into `install.sh`) — get a **project-level** `AGENTS.md`
fragment, not a full merge into one giant file (kept separate so each rule
stays independently versioned/reviewable, matching the existing
`~/.claude/rules/` layout). `.claude/rules/acceptance-matrix.md` is a
**repo-local-only** rule (no plugin equivalent, not installer-shipped) and is
included in the project instructions set too, since it governs this repo
specifically and OpenCode sessions working in it should see it:

- New `.opencode/instructions/<rule-name>.md` per rule (content == the
  existing `plugins/super-fr/rules/<rule-name>.md`, same drift-check pattern
  as skills — same generation script, extended).
- Repo-root `opencode.json` (new file) lists them:
  `"instructions": [".opencode/instructions/*.md"]`.
- Global operator rules keep installing to `~/.claude/rules/` as today
  (OpenCode's Claude-compat CLAUDE.md fallback doesn't read a rules dir, but
  the project `opencode.json` instructions array is the OpenCode-native path
  and doesn't depend on that fallback) — `install.sh`'s existing
  `~/.claude/rules/` step is untouched; this adds a **project** delivery path
  only, since instructions in `opencode.json` are inherently repo-scoped.

### 4. OpenCode plugin: `fr-isolation-required` parity

New package `packages/fr-opencode-plugin/` (TypeScript, Bun-targeted — the
first non-Python package in this monorepo; isolated in its own directory with
its own `package.json`, does not touch the `uv` workspace):

- Exports a plugin function implementing `tool.execute.before`: on
  `edit`/`write`/`patch`-class tool calls, inspect the target path the same
  way `fr-isolation-required.sh` does — resolve nearest tracked ancestor,
  check for the `.fr-isolation` marker, honor `FR_BASE_OK=1` and
  `.fr-isolation-allow` globlist escapes.
- Ships as `.opencode/plugins/fr-isolation-required.ts` in this repo (project
  delivery) and is `npm`-publishable (`@derio-net/fr-opencode-plugin` or
  similar) so consumer `opencode.json` can reference it via
  `"plugin": ["@derio-net/fr-opencode-plugin"]` (installer delivery) — mirrors
  the skills split (project copy + installer/npm path).
- Test with an actual local OpenCode install (`npm i -g opencode-ai`, verified
  installable 2026-07-08) exercising `tool.execute.before` against a scratch
  repo with/without the `.fr-isolation` marker.

### 5. Version bump

Minor bump (`scripts/bump-version.py minor`) — this PR adds a new
user-visible capability (OpenCode as a first-class consumer surface), per the
agreed convention.

## Test Plan (post-merge, operator-driven)

1. `git clone` super-fr fresh, run `opencode` inside it, confirm the `skill`
   tool lists `fr-goal`, `fr-plan`, etc. (in-repo delivery, zero install).
2. Run `scripts/install.sh` on a machine with `~/.config/opencode/` present,
   confirm `~/.config/opencode/skills/fr-goal/SKILL.md` appears.
3. In a scratch repo with the OpenCode plugin loaded, attempt an `Edit` tool
   call outside any `.fr-isolation` marker — confirm it's blocked; touch the
   marker, confirm it's allowed.
4. `scripts/bump-version.py --check` passes; version is a minor bump over the
   prior release.

## Implementation Plans

| Plan | Repo | File | Depends on |
|---|---|---|---|
| opencode-adaptation | `derio-net/super-fr` | `opencode-adaptation` | — |

## Acceptance rows (added at spec time, presented at spec review)

- "An operator can `git clone` super-fr and use its `fr-*` skills directly
  from OpenCode with no install step" — business-level, verified via Test
  Plan step 1 (agent-observable, not an implementation detail: it's the
  headline capability this whole spec exists to deliver).
- "An operator can run `scripts/install.sh` and get super-fr's skills
  available globally in OpenCode" — verified via Test Plan step 2.
- "Edits to tracked source in an fr-isolation-enabled repo are blocked from
  OpenCode outside an isolation workspace, matching the Claude Code hook's
  guarantee" — verified via Test Plan step 3; this is the actual safety
  invariant fr-isolation-required protects, not a proxy for it.
