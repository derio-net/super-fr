# Hermes Agent compatibility — design

**Date:** 2026-07-23
**Slug:** `2026-07-23-hermes-agent-compat`
**Status:** design (fr-goal, autonomous)
**Repo:** `derio-net/super-fr` (single-repo change)

## 1. Goal

Make super-fr a first-class citizen of a **third agent harness** — **Hermes
Agent** by Nous Research (`NousResearch/hermes-agent`) — parallel to the
existing Claude Code and OpenCode support. A Hermes user who installs super-fr
gets: the `fr-*` skills as slash commands, super-fr's standing rules, the
fr-isolation enforcement gate (edits **and** bash/push), the session-start
acceptance nag, and the ability to run a full autonomous `fr-goal` inside
Hermes via its native subagent delegation.

### Non-goals

- No general "harness registry" refactor. Like Claude Code and OpenCode,
  Hermes is added as a parallel, mostly-hardcoded delivery track. (The one
  pre-existing seam — `fr models`' `harness → tier → model` axis — is reused,
  not rebuilt.)
- No changes to the `fr`/`fr-dispatch`/`fr-vk`/`fr-cncd` engine semantics.
- No Hermes-model *inference* work (super-fr never calls models directly).

## 2. Background — how super-fr targets a harness today

super-fr ships to a harness over **three delivery channels**. There is no
abstraction layer; each harness is hand-wired. The OpenCode track is the
template this design parallels.

| Channel | Claude Code | OpenCode (the template) |
|---|---|---|
| **Skills** | marketplace plugin (`plugins/super-fr/skills/<n>/SKILL.md`) | `.opencode/skills/<n>/SKILL.md` (byte-copy) + generated `.opencode/commands/<n>.md`; installed to `~/.config/opencode/…` |
| **Rules** | `~/.claude/rules/*.md` (global, unconditional) | `.opencode/instructions/*.md` via `opencode.json`'s `instructions` array |
| **Enforcement** | `fr-isolation-required.sh` PreToolUse (Edit/Write/…) + Bash guards + `SessionStart` nag, registered in `hooks.json` | `packages/fr-opencode-plugin` TS `tool.execute.before` (edits only; **bash NOT gated**) |

Supporting machinery on the OpenCode track, all of which Hermes must parallel:

- **Generator:** `scripts/sync-opencode.py` (byte-copies skills; copies rule
  `.md`; *generates* command wrappers). `--check` fails on drift.
- **Install/uninstall:** `scripts/install.sh` — OpenCode delivery is **opt-in
  gated** (`OPENCODE_SKILLS_INSTALL=1` **or** `~/.config/opencode` exists).
  Uninstall removes **only** super-fr's own files (iterates canonical skill
  names, never wipes the dir).
- **Tests:** `tests/unit/test_tripwire_opencode_*_sync.py` (mirror drift),
  `tests/unit/test_install_copies_opencode_skills.py` /
  `test_install_copies_rules.py` (install wiring), plus a dedicated
  `opencode-plugin-test` CI job (`bun test`).
- **Pre-existing seam:** `fr models` config is `harness → tier → model`
  (`packages/fr/src/fr/models.py`); `models_cmd.py` already lists `hermes` as
  an example `--harness`. `fr models resolve --harness hermes --tier <t>`
  works today (returns nothing until bound).

## 3. Background — the Hermes Agent extension model (verified against source)

Read end-to-end from `NousResearch/hermes-agent@main`:

### 3.1 Skills — same SKILL.md format super-fr already writes
- Live in **`~/.hermes/skills/<category>/<name>/SKILL.md`** (directory-per-skill;
  optional `references/`, `templates/`, `scripts/`). Source of truth is
  `~/.hermes/skills/`; extra dirs via `external_dirs` in `config.yaml`.
- Frontmatter: **`name`, `description` required**; optional `version`,
  `author`, `platforms` (OS gate), `metadata.hermes.{tags, related_skills,
  config}`, `required_environment_variables`. Unknown fields are ignored
  (permissive) — **super-fr's existing SKILL.md loads as-is**.
- Invoked via **`/skill-name`** slash commands (same UX as Claude/OpenCode) and
  natural language. Progressive disclosure: `skills_list()` → `skill_view()`.
- Third-party install: `hermes skills install <repo/url>`, `external_dirs`, or
  direct copy. Categories inferred from the directory (`fr/fr-goal/` → `/fr-goal`).

### 3.2 Context files & SOUL.md — where rules go (no instructions-array)
- Project context is **first-match-wins, only one loads**:
  `.hermes.md`→`AGENTS.md`→`CLAUDE.md`→`.cursorrules`.
- **Global `SOUL.md`** (`~/.hermes/SOUL.md`) is **always loaded** independently
  as the agent identity, regardless of which project file wins.
- All context files are prompt-injection-scanned before inclusion.
- **Consequence:** Hermes has no per-file "instructions array." The only
  always-on, machine-wide surface is `SOUL.md` — the analog to Claude's global
  `~/.claude/rules/`.

### 3.3 Shell-hooks bridge — Claude-compatible tool gating (`agent/shell_hooks.py`)
- Reads a `hooks:` block from **`cli-config.yaml`**; registers shell scripts on
  Hermes's plugin hook manager. Every `invoke_hook()` site dispatches to them.
- **Events include `pre_tool_call`, `post_tool_call`, `on_session_start`,
  `on_session_end`, `subagent_stop`, `pre_llm_call`.**
- **Wire protocol** — stdin JSON: `{hook_event_name, tool_name, tool_input,
  session_id, cwd, extra}`. stdout JSON, **both shapes accepted**:
  `{"decision":"block","reason":"…"}` *(documented in-source as
  "Claude-Code-style")* or `{"action":"block","message":"…"}` *(Hermes-native)*.
- Each `hooks:` entry (`ShellHookSpec`) = `{event, command, matcher?(regex on
  tool_name), timeout?}`.
- **Mutating tools it fires on** include `write_file`, `patch` (edit-equiv) and
  **`terminal`, `execute_code` (bash-equiv)** — `terminal`'s `tool_input` is
  `{"command": "…"}` (same shape the Claude Bash guards already parse).
- **Consent:** first use of an `(event, command)` pair is gated by
  `~/.hermes/shell-hooks-allowlist.json`. Non-TTY registration needs
  `accept_hooks` via `--accept-hooks`, `HERMES_ACCEPT_HOOKS=1`, or
  `hooks_auto_accept: true` in config. `HERMES_SAFE_MODE=1` skips all hooks.

### 3.4 Subagent delegation — `delegate_task` (`tools/delegate_tool.py`, docs)
- `delegate_task(goal, context)` (or `tasks=[…]` for ≤3 parallel) spawns a
  fresh child agent with isolated context and inherited tools/skills. **Only its
  final summary re-enters the parent.**
- **"Subagents Know Nothing"** — a child starts with zero parent history; the
  parent must pass *everything* via `goal`+`context`. The child gets a focused
  system prompt instructing it to "complete the task and provide a **structured
  summary of what it did, what it found, files modified, and issues
  encountered**."
- Nested delegation is unlocked by `role='orchestrator'`.
- **This is precisely fr-goal's contract** ("the journal IS the handoff; the
  subagent inherits no history; returns a structured result").

## 4. Design

Seven work-streams (A–G). No new package: because Hermes's shell-hook bridge
speaks the Claude block protocol, enforcement **reuses the existing shell
script** — a materially smaller, DRYer design than OpenCode's TS plugin.

### A. Skills delivery → `~/.hermes/skills/fr/`
- **New generator `scripts/sync-hermes.py`** (mirrors `sync-opencode.py`;
  imports `yaml`, runs under the workspace venv; `--check` fails on drift).
  Produces repo-local mirrors under **`.hermes/`** so super-fr can dogfood
  under Hermes and the mirror is CI-testable:
  - `.hermes/skills/fr/<name>/SKILL.md` — byte-copy of each canonical
    `plugins/super-fr/skills/<name>/SKILL.md` under a `fr` **category**
    directory. (`name`/`description` already present; no transform needed.
    Optional, deferred: enrich `metadata.hermes.tags`.)
    A sibling `.source` breadcrumb, matching the OpenCode generator.
- **Category `fr`** namespaces every super-fr skill under `~/.hermes/skills/fr/`
  → tidy uninstall targeting and no collision with the user's own skills.
- Skills keep their `fr-*` names → slash commands `/fr-goal`, `/fr-plan`, ….
- No command-wrapper generation (Hermes derives `/name` from the skill itself,
  unlike OpenCode's separate `/command` surface).

### B. Rules delivery → managed block in `~/.hermes/SOUL.md`
- **Only the three *shipped* plugin rules** — `fr-isolation-required`,
  `fr-plan-override`, `no-claude-p-batch` — go into the global SOUL.md block.
  This matches exactly what install.sh copies to `~/.claude/rules/` for Claude.
  The repo-local `acceptance-matrix` rule is a super-fr-repo-maintainer rule
  (no plugin equivalent, repo-local-only) and is **NOT** shipped to consumers;
  it belongs to super-fr's own dogfooding context (see §B-dogfood), never a
  consumer's global SOUL.md.
- The three rules are concatenated into a **delimited managed block**:
  ```
  <!-- super-fr:rules START -->
  … rule bodies …
  <!-- super-fr:rules END -->
  ```
- `sync-hermes.py` writes the assembled block to a repo-local
  **`.hermes/SOUL.d/super-fr-rules.md`** (source-of-truth mirror, tripwired).
- **§B-dogfood:** for super-fr running *itself* under Hermes, the repo-local
  `.hermes/` mirror also carries `acceptance-matrix` as project context (the
  Hermes analog of the repo-local `.claude/rules/`/`.opencode/instructions/`
  dogfooding config) — never installed globally.
- `install.sh` **appends/replaces** that block in `~/.hermes/SOUL.md`
  idempotently (create the file if absent; replace between the markers on
  re-install; strip the block on `--uninstall`). Content outside the markers is
  never touched — the user's own SOUL.md identity is preserved.
- Rationale (decision d2): SOUL.md is the only always-on global surface (analog
  to `~/.claude/rules/`). Per-repo context files risk first-match-wins
  shadowing of `AGENTS.md`/`CLAUDE.md`; skill-embedding makes rules non-global
  and duplicates text.

### C. Isolation enforcement → Hermes shell hooks (edits + bash/push)
The load-bearing channel. **Reuse the existing shell scripts** via a small
per-harness I/O adapter instead of a new language port.

- **Factor a shared decision core.** Extract the marker/allowlist decision that
  today lives inside `fr-isolation-required.sh` into a sourced shell library
  (`plugins/super-fr/hooks/lib/fr-isolation-decision.sh`) — pure: given a
  target path (or a git command) it returns allow / deny + reason. Both the
  Claude and Hermes entrypoints source it (parallels OpenCode's `marker.ts`
  pure core). This keeps three enforcement implementations but DRYs the two
  shell ones and makes the decision unit-testable.
- **Per-harness I/O differs and must be handled explicitly:**
  - *Input:* Claude PreToolUse gives `tool_name ∈ {Edit,Write,MultiEdit,
    NotebookEdit}` + `.tool_input.file_path`. Hermes `pre_tool_call` gives
    `tool_name ∈ {write_file,patch}` (edits) / `{terminal,execute_code}` (bash)
    + `.tool_input` (`path`/`file_path` for edits, `command` for bash). A
    tool-name normalization table maps both vocabularies to `edit`/`bash`.
  - *Output:* Claude wants `hookSpecificOutput.permissionDecision:"deny"`;
    Hermes wants `{"decision":"block","reason":…}`. The entrypoint emits its
    harness's deny shape.
- **Three Hermes `pre_tool_call` hooks** (each a `hooks:` entry with a `matcher`
  regex), porting the three Claude PreToolUse guards:
  1. **edits** — matcher `write_file|patch` → fr-isolation-required (deny edits
     outside a valid `.fr-isolation` worktree; honors `FR_BASE_OK=1` and
     `.fr-isolation-allow`).
  2. **bash/git** — matcher `terminal|execute_code` → fr-isolation-guard
     (gate git/gh mutations outside isolation; `.tool_input.command`).
  3. **merged-PR push** — matcher `terminal|execute_code` →
     fr-merged-pr-push-guard (block pushing to a merged PR branch).
- **`on_session_start` hook** → the fr-acceptance nag (Hermes analog of the
  Claude `SessionStart` hook; prints `fr acceptance status --brief`).
- **Registration** is done by the tested `fr hermes install` subcommand (§E),
  not raw bash: it merges these entries into the user's `cli-config.yaml`
  `hooks:` block idempotently (keyed by `(event, command)`) and pre-records them
  in `~/.hermes/shell-hooks-allowlist.json` so non-TTY runs register without a
  prompt (documented `HERMES_ACCEPT_HOOKS` fallback). Repo-local source mirror
  of the desired entries: `.hermes/cli-config.snippet.yaml` (tripwired).

### D. Autonomous `fr-goal` inside Hermes → `delegate_task` (decision d4)
- Make the delivered **`fr-goal` SKILL.md harness-aware** at step 6 (phase
  execution): under Claude Code it dispatches the `fr-phase-executor` Agent;
  under Hermes it calls **`delegate_task(goal=<phase goal>, context=<brief>)`**,
  serially, one call per phase (shared workspace — no parallel `tasks=[]`).
- **Brief = the same journal-fed handoff** super-fr already defines:
  `fr pickup` output + the spec + `fr journal render --scope plan`, passed
  entirely through `context` (Hermes subagents know nothing — this is already
  how fr-goal is written).
- The delegated child loads the delivered **`fr-execute`** skill and runs TDD,
  writes `fr journal add --scope plan` entries (durable handoff), ticks steps /
  completes the phase, and returns a structured summary — which Hermes surfaces
  to the orchestrator as the phase result.
- **Model resolution: ask, never guess.** super-fr ships NO `hermes:` bindings —
  `fr models resolve --harness hermes --tier <t>` stays unbound, which is
  precisely fr-goal's trigger to ask the operator for a model per tier on the
  first Hermes run and persist it via `fr models set`. See §G.
- Keep the change **additive and guarded** — a `## Harness: phase execution`
  subsection in `fr-goal` SKILL.md with a Claude branch and a Hermes branch, so
  neither harness regresses. (SKILL.md is at its 120-line cap — see Risks.)

### E. Install / uninstall wiring (`scripts/install.sh`)
- **Opt-in gated**, matching OpenCode: Hermes delivery runs only if
  `HERMES_SKILLS_INSTALL=1` **or** `~/.hermes` already exists. Path var
  `HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"`.
- **Install:** copy `.hermes/skills/fr/*` → `~/.hermes/skills/fr/`; apply the
  SOUL.md managed block; copy the hook scripts to a stable location and merge
  the `hooks:` entries + allowlist. Install writes **no** model bindings (§G).
- **Uninstall (`--uninstall`):** remove **only** super-fr's files — iterate
  canonical skill names to `rm -rf ~/.hermes/skills/fr/<name>`; strip the
  SOUL.md managed block; remove super-fr's `hooks:` entries + allowlist lines.
  Never wipe `~/.hermes` wholesale.
- **Invasive mutations live in a tested `fr` subcommand, not bash.** install.sh
  is currently **jq-only (no yq)**, and jq cannot merge into `cli-config.yaml`
  (YAML) — the single most error-prone install step (a shared, user-owned file).
  Rather than add a `yq` external dependency or hand-roll YAML in bash, add a
  minimal **`fr hermes install` / `fr hermes uninstall`** subcommand
  (`packages/fr`, using the `yaml` dep already vendored) that performs the
  idempotent, reversible mutations: merge/strip the `hooks:` entries in
  `cli-config.yaml`, add/remove the `~/.hermes/shell-hooks-allowlist.json`
  entries, and apply/strip the SOUL.md managed block. install.sh's Hermes path
  copies the skill files (pure bash) and then shells out to `fr hermes install`
  (the `fr` CLI is guaranteed present — install.sh just installed it). This
  keeps every risky mutation in unit-tested Python, consistent with the repo's
  "guards are tested code, not prose" convention, and adds no external dep.
  The bash byte-copy of skills stays in install.sh so the common path is simple.

### F. Sync + tripwire tests + CI
- **Tripwires** (`tests/unit/`, importing `scripts/sync-hermes.py` directly so
  `--check` and CI can't disagree):
  - `test_tripwire_hermes_skills_sync.py` — canonical skills non-empty; no
    drift between `plugins/super-fr/skills/` and `.hermes/skills/fr/`.
  - `test_tripwire_hermes_rules_sync.py` — the SOUL.d managed block matches the
    canonical rule sources.
  - `test_tripwire_hermes_hooks_sync.py` — the `cli-config.snippet.yaml`
    entries match the shipped hook scripts (event/matcher/command triples).
- **Install-copies guards** (static assertions on `install.sh`):
  - `test_install_copies_hermes_skills.py` — defines `HERMES_HOME`, copies from
    `.hermes/skills/fr`, gates on `HERMES_SKILLS_INSTALL`/`~/.hermes`, invokes
    `fr hermes install` on the Hermes path, and the uninstall block calls
    `fr hermes uninstall`.
  - Extend `test_install_copies_rules.py` for the SOUL.md block.
- **`fr hermes install/uninstall` subcommand tests** (`tests/unit/`, against a
  temp `HERMES_HOME`): idempotent `hooks:` merge into a `cli-config.yaml`
  (re-run adds nothing; preserves unrelated keys), allowlist entries
  added/removed, SOUL.md managed block applied then cleanly stripped leaving
  user content intact, and a malformed/absent `cli-config.yaml` handled
  fail-safe. This is where the invasive-mutation risk is pinned as tested code.
- **Enforcement decision tests** — unit-test `fr-isolation-decision.sh` and both
  harness entrypoints against recorded Claude/Hermes stdin payloads, asserting
  allow/deny + the correct per-harness deny JSON (deny-outside-worktree,
  allow-with-FR_BASE_OK, allow-via-`.fr-isolation-allow`, bash git-guard,
  merged-PR-push block). This closes the "guards must be tested code, not prose"
  requirement.
- **CI:** the shell/python tests run in the existing `test` job. No new bun job
  (no TS package). Add the enforcement shell tests to the pytest suite (driving
  the scripts as subprocesses) so one gate covers them.
- **`opencode.json` analog:** none needed — Hermes discovers `~/.hermes/skills/`
  and `cli-config.yaml` natively; the repo-local `.hermes/` mirror is for
  dogfooding + tests only.

### G. `fr models` under Hermes — ask on first run, ship NOTHING

**Revised after operator review (see journal `r2-no-guessed-models`).** An
earlier revision shipped a repo `models.yaml` with invented
`NousResearch/Hermes-4-*` ids. That is wrong on two counts: the ids were
fabricated (super-fr cannot know which model names a given Nous endpoint
serves), and — worse — *any* shipped binding resolves successfully, which
**suppresses fr-goal's first-run model question** and silently locks the
operator to a wrong model.

- **Ship no `hermes:` bindings.** `fr models resolve --harness hermes --tier <t>`
  stays unbound, which is exactly the trigger fr-goal already documents:
  "if `fr models resolve` is unbound, add a model-per-tier question" (SKILL.md
  step 1) and "Model = phase `tier` via `fr models resolve --harness <h>`
  (unbound → set step 1)" (step 6). The operator answers once; `fr models set`
  persists it to `~/.config/fr/models.yaml`.
- No code change to `models.py` (the harness axis already exists).
- Guarded by `tests/unit/test_models_hermes_first_run.py`, which fails if any
  `hermes:` binding is ever re-introduced into the repo override.

## 5. Risks & mitigations

- **`fr-goal` SKILL.md is at the 120-line hard cap** (test-enforced; see repo
  memory). Adding a harness branch requires *compressing* existing prose to make
  room. Mitigation: fold the Claude/Hermes split into a single terse
  subsection; move any overflow to a referenced file if the skill format allows.
  If it cannot fit, the plan must call it out — do not silently exceed the cap.
- **Mutating the user's `cli-config.yaml` / `SOUL.md`** is invasive. Mitigation:
  strictly delimited managed blocks + idempotent keyed merges + full uninstall
  strip; never touch content outside the markers.
- **Non-TTY hook registration** silently skips if not allowlisted. Mitigation:
  install pre-records the allowlist entries and documents `HERMES_ACCEPT_HOOKS`.
- **Hermes moves fast** (v0.19 with 2,200+ commits). Tool names / event names
  could drift. Mitigation: pin the verified facts in this spec; the enforcement
  decision tests fail loudly if the payload shape changes.
- **Three enforcement implementations** (Claude bash, Hermes bash, OpenCode TS).
  Mitigation: the shared shell decision core DRYs the two shell ones; OpenCode's
  `marker.ts` stays as-is (already tested). Full unification is a non-goal.

## 6. Test Plan (post-merge, operator-driven)

Requires a real Hermes Agent install (operator has one). Post-merge:

1. **Install:** run `scripts/install.sh` with `HERMES_SKILLS_INSTALL=1` (or with
   `~/.hermes` present). Verify `~/.hermes/skills/fr/fr-goal/SKILL.md` exists and
   `/fr-goal` appears in Hermes `skills_list()` / slash completion.
2. **Rules:** confirm the `<!-- super-fr:rules … -->` block is present in
   `~/.hermes/SOUL.md` and Hermes loads it (rules referenced in a session).
3. **Enforcement — edits:** in an fr-enabled repo *outside* an isolation
   worktree, ask Hermes to `write_file`/`patch` a tracked file → the
   `pre_tool_call` hook **blocks** it with the fr-isolation-required reason;
   inside a valid `.fr-isolation` worktree the same edit is **allowed**;
   `FR_BASE_OK=1` allows a one-off.
4. **Enforcement — bash/push:** ask Hermes to `git commit`/push outside
   isolation via `terminal` → blocked; pushing to a merged PR branch → blocked.
5. **Session nag:** start a Hermes session in a repo with acceptance debt →
   `on_session_start` prints `fr acceptance status --brief`.
6. **Autonomous run:** invoke `/fr-goal` for a toy feature inside Hermes → it
   delegates each phase via `delegate_task`, the child writes journal entries,
   and the run reaches a PR. Confirm `fr models resolve --harness hermes` binds.
7. **Uninstall:** `scripts/install.sh --uninstall` removes `~/.hermes/skills/fr`,
   strips the SOUL.md block, removes the `hooks:` entries — and leaves the
   user's own SOUL.md/skills/hooks intact.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|

## 7. Acceptance rows (born here; presented at spec review)

Proposed matrix rows (`fr acceptance add --origin
super-fr:docs/superpowers/specs/2026-07-23-hermes-agent-compat-design.md
--status not-implemented`):

1. **`hermes-skills-delivery`** — *Installing super-fr under Hermes makes the
   `fr-*` skills available as `/fr-*` slash commands.* Level: unit (sync tripwire
   + install-copies) → post-merge manual (Test Plan 1). Business-level: the
   whole point of "compatible" is the skills being usable in Hermes.
2. **`hermes-rules-soul-block`** — *super-fr's standing rules reach a Hermes user
   via a managed, reversible SOUL.md block.* Level: unit (rules-sync tripwire +
   install/uninstall block assertions). Business-level: rules govern behavior;
   reversibility protects the user's own SOUL.md.
3. **`hermes-isolation-gate-edits`** — *Hermes blocks tracked-file edits made
   outside a valid fr-isolation worktree (honoring FR_BASE_OK / allowlist).*
   Level: unit (decision + entrypoint tests) → post-merge manual (Test Plan 3).
   Business-level: the isolation guarantee must hold on Hermes, not just Claude.
4. **`hermes-isolation-gate-bash`** — *Hermes blocks git/gh mutations and
   merged-PR pushes outside isolation — closing the bash gap OpenCode has.*
   Level: unit (bash-guard tests) → post-merge manual (Test Plan 4).
   Business-level: bash is the escape hatch edits-only gating leaves open.
5. **`hermes-fr-goal-delegation`** — *A full `fr-goal` run executes inside Hermes,
   delegating each phase via `delegate_task` with a journal-fed brief.* Level:
   not-implemented → post-merge manual (Test Plan 6). Business-level: the
   headline capability of decision d4 — autonomy inside Hermes, not just
   plugin-surface delivery.
