# Codex harness adapter — design

**Date:** 2026-09-16
**Slug:** `2026-09-16-codex-harness-adapter`
**Status:** design (fr-goal, autonomous — batched Q&A self-answered, see journal `d11`)
**Repo:** `derio-net/super-fr` (single-repo change)

## 1. Goal

Make super-fr a first-class citizen of a **fourth agent harness** — **Codex
CLI** (OpenAI, `codex-cli` 0.153.4 verified locally) — parallel to the existing
Claude Code, OpenCode and Hermes Agent support. A Codex user who installs
super-fr gets: the `fr-*` skills discoverable in Codex, super-fr's standing
rules delivered as Codex-readable instructions, and the fr-isolation
enforcement gate (edits **and** bash) wired as Codex hooks — plus a repair path
for the stale-skill-link failure that motivated this work.

### Non-goals

- No "harness registry" refactor. Like the other three, Codex is added as a
  parallel, mostly hand-wired delivery track.
- No changes to `fr` / `fr-dispatch` / `fr-vk` / `fr-cncd` engine semantics.
- No Codex phase-execution branch in `fr-goal` (journal `d10`).
- No merged-PR push guard, no SessionStart acceptance nag (journal `d4`).
- No modification of the operator's `~/.codex` or `~/.claude` config by this
  PR. The installer is *shipped*; running it stays the operator's call.

## 2. Motivation — the failure this closes

Two concrete, observed failures:

1. **super-fr has no Codex support at all.** `git grep -i codex origin/main`
   returns nothing; no issue mentions Codex. A Codex session working in an
   fr-enabled repo is ungoverned: it does not know about fr-isolation, fr
   plan folders, or the journal.
2. **Consequence, observed in `derio-net/willikins` (PR #405).** A Codex
   session added "Codex compatibility" while knowing nothing about fr: it
   edited the base clone instead of an fr-isolation workspace, wrote a v1 flat
   plan instead of a v2 plan folder, and put review reports in an ad-hoc
   `docs/reviews/` instead of the fr journal. Every one of those is a rule
   super-fr already ships to three other harnesses.
3. **The operator's `~/.codex/skills/fr-*` links were all dangling**, pointing
   at a retired marketplace path. Crucially — verified this session, journal
   `v3` — Codex skips a dangling skill symlink **silently**: exit 0, empty
   stderr, the skill simply does not appear in the catalog. There is no error
   to notice. That is why they stayed broken.

## 3. Background — verified Codex facts

Everything in this section was checked this session. Each item is marked
**[verified]** (observed or read from official docs) or **[assumed]**.

### 3.1 Skills discovery — **[verified]**
- Documented scan list (learn.chatgpt.com/docs/build-skills): `$CWD/.agents/skills`,
  `$CWD/../.agents/skills`, `$REPO_ROOT/.agents/skills`, `$HOME/.agents/skills`,
  `/etc/codex/skills`, bundled.
- **The docs list is incomplete.** `$CODEX_HOME/skills` (default `~/.codex/skills`)
  IS scanned: `codex debug prompt-input` surfaces `fr-goal` / `fr-isolation`,
  which exist *only* there. OpenAI's own bundled `skill-installer` corroborates:
  "Installs into `$CODEX_HOME/skills/<skill-name>` (defaults to `~/.codex/skills`)".
- Repo-level `.agents/skills` works **without a git repo** (probe, journal `v2`).
- **Symlinks are followed**, including absolute ones.
- **A dangling symlink is skipped silently** (journal `v3`) — no error, no warning.
- Required frontmatter: `name`, `description`. super-fr's SKILL.md already
  satisfies this; no transform needed.
- `.codex/skills` is **not** a skills location.

### 3.2 Instructions / AGENTS.md — **[verified]**
- Global `~/.codex/AGENTS.md` (or `AGENTS.override.md`) loads, **then** the
  project chain from git root down to cwd. Files are **concatenated/merged**,
  not first-match-wins — closer files override earlier ones.
- `project_doc_max_bytes` defaults to **32 KiB** (32768 bytes), and discovery
  **stops** once the threshold is reached. An oversized global block therefore
  silently evicts a repo's own AGENTS.md — it is truncation, not an error.
- **Measured, this session** — the numbers that drive §4.B:

  | Artifact | Bytes |
  |---|---|
  | The 4 shipped rules, concatenated | 13,066 |
  | `.hermes/SOUL.d/super-fr-rules.md` (Hermes-style full inline) | 13,129 |
  | super-fr's own `AGENTS.md` | 16,365 |
  | **Full-inline block + super-fr's own AGENTS.md** | **29,494 (90% of the 32,768 cap)** |

  A Hermes-style full-inline block consumes 90% of the budget **in super-fr's
  own repo**. Any consuming repo with a larger AGENTS.md loses its own
  instructions silently. This is why §4.B does not inline.
- `project_doc_fallback_filenames` configures alternates.
- Contrast with Hermes, where exactly one project context file wins — Codex's
  merge semantics make a global managed block additive and safe.

### 3.3 Hooks — **[verified from docs + live schema]**
- Events include `SessionStart`, `SessionEnd`, `PreToolUse`, `PostToolUse`,
  `PermissionRequest`, `UserPromptSubmit`, `SubagentStart`, `SubagentStop`,
  `Stop`, `Interrupt`, `PreCompact`, `PostCompact`.
- PreToolUse stdin: `{session_id, transcript_path, cwd, hook_event_name,
  permission_mode, turn_id, tool_name, tool_use_id, tool_input}`.
- **"Bash and apply_patch use `tool_input.command`."** `tool_name` is
  `apply_patch` for file edits *even when the matcher is written as `Edit` or
  `Write`*; shell calls report `Bash`.
- Deny shapes accepted: `{"hookSpecificOutput":{"hookEventName":"PreToolUse",
  "permissionDecision":"deny","permissionDecisionReason":"…"}}`, legacy
  `{"decision":"block","reason":"…"}`, or **exit 2** with the reason on stderr.
  The first is byte-identical to what super-fr's Claude hook already emits.
- Matchers are **regex** (alternation, `.*`).
- Config locations: `~/.codex/hooks.json`, `~/.codex/config.toml` `[hooks]`,
  `<repo>/.codex/hooks.json`, `<repo>/.codex/config.toml`, plugin-bundled
  `hooks/hooks.json`. Live schema confirmed by reading the operator's existing
  `~/.codex/hooks.json`: identical in shape to Claude's.
- **[assumed]** the exact `tool_input.command` encoding for `apply_patch` (raw
  patch text vs. a shell wrapper around a heredoc). The parser is written
  defensively to handle either — see §4.C.

### 3.4 Trust — **[verified]**, and it is a first-class constraint
- "Before a non-managed hook can run, Codex requires you to review and trust
  the exact hook definition." `/hooks` is the review surface.
- Trust is recorded **against the hook's hash**, so a *changed* hook is
  re-marked for review and **skipped until re-trusted**.
- Plugin-bundled hooks are **not** exempt.
- `projects.<path>.trust_level`: "Untrusted projects skip project-scoped
  `.codex/` layers, including project-local config, hooks, and rules."

**Consequence the docs must state plainly: an installed hook is not a running
hook.** And every super-fr release that edits a hook script silently disarms
the Codex gate until the operator re-trusts it. This is a genuine limitation of
the Codex track that the Claude track does not have.

## 4. Design

Five work-streams (A–E), mirroring the Hermes track's shape.

### A. Skills → `$CODEX_HOME/skills/` + repo `.agents/skills/`
- **New generator `scripts/sync-codex.py`** (mirrors `sync-opencode.py` /
  `sync-hermes.py`; `--check` fails on drift). Produces repo-local mirrors:
  - `.agents/skills/<name>/SKILL.md` — byte-copy of each canonical
    `plugins/super-fr/skills/<name>/SKILL.md`, plus a `.source` breadcrumb.
- `fr codex install` links/copies the canonical skills into
  `$CODEX_HOME/skills/<name>` (journal `d2`) — the location the operator's
  existing links already use, so install repairs in place.

### B. Rules → managed block in `~/.codex/AGENTS.md`
- The **four** shipped plugin rules — `fr-isolation-required`,
  `fr-plan-override`, `fr-worktree-override`, `no-claude-p-batch` — selected via
  the same `SHIPPED_RULE_NAMES` allowlist `sync-hermes.py` already applies, so a
  maintainer-only rule dropped into `plugins/super-fr/rules/` can never leak into
  a consumer's global instructions. Assembled into a delimited block:
  ```
  <!-- super-fr:rules START -->
  … condensed rule text + pointers …
  <!-- super-fr:rules END -->
  ```
- `sync-codex.py` writes the assembled block to `.codex/AGENTS.snippet.md`
  (repo-local source of truth, tripwired) — the analog of
  `.hermes/SOUL.d/super-fr-rules.md`.
- **The block is a compact POINTER block, not the rule bodies** — revised at
  spec-review against the §3.2 measurements (journal `r1`). Full bodies are
  installed as *files* to `$CODEX_HOME/rules/super-fr/<rule>.md`, which costs
  the prompt budget nothing, and the block inlines only the invariants that are
  unsafe to discover late (the fr-isolation gate and its escapes; the
  no-`claude -p` convention) and names the files by absolute path for the rest.
  This is the HERMES.md "inline what's unsafe to discover late, point at the
  rest" tactic, adopted here for a different reason: the byte cap, not shadowing.
- **Size-budgeted and test-enforced: ≤ 2 KiB.** Achievable only because the block
  points rather than inlines (full inline measures 13,129 bytes). At 2 KiB the
  block costs ~6% of the 32 KiB budget, leaving a consuming repo its own
  instructions. The test asserts the *rendered* block size, so the budget cannot
  be blown by editing a rule.
- Idempotent apply / clean strip on uninstall; content outside the markers is
  never touched.

### C. Enforcement → Codex PreToolUse hooks (edits + bash)

The load-bearing channel. **Entrypoints stay thin; the decision is the existing
shared library** `plugins/super-fr/hooks/lib/fr-isolation-decision.sh` — the
same core the Claude hook, the Hermes hooks and the OpenCode plugin use. The
decision logic is **not** forked.

Genuinely new Codex-specific logic, factored into its own tested library
`plugins/super-fr/hooks/lib/fr-apply-patch-paths.sh`:

- **Extract every target path from an apply_patch payload.** The patch body
  carries `*** Add File: <p>`, `*** Update File: <p>`, `*** Delete File: <p>`
  and `*** Move to: <p>` lines — multiple files per call.
- **Resolve each path against the payload `cwd`** before calling the decision
  library. This is the correctness trap (journal `d7`):
  `fr_isolation_decide_edit()` returns **ALLOW** for any non-absolute path by
  design, so passing apply_patch's repo-relative paths through verbatim would
  allow every patch while appearing to work — a fully disarmed gate.
- **A patch is atomic** (journal `d8`): Codex cannot partially apply, so if
  **any** extracted path is blocked the whole call is denied, naming the
  offending path. A mixed patch (one allowlisted + one tracked path) denies.

Two entrypoints:

1. `plugins/super-fr/hooks/codex/fr-isolation-required.sh` — PreToolUse,
   matcher `apply_patch|Edit|Write`. Emits the
   `hookSpecificOutput.permissionDecision:"deny"` shape.
2. `plugins/super-fr/hooks/codex/fr-isolation-guard.sh` — PreToolUse, matcher
   `Bash`. Marker-based git/gh mutation gating (the Hermes guard's logic, since
   Codex has no pipeline sentinel). Also catches an apply_patch heredoc smuggled
   through a Bash call, reusing the same extractor.

**Parser posture (journal `d6`):** jq absent but python3 present → the gate stays
**fully armed**. No parser resolvable at all → an **explicit refusal**, not a
silent pass. This follows the Hermes hardening, where a PATH-missing jq once
aborted the hooks before they printed a decision and silently disarmed them.

Registration source of truth: `.codex/hooks.snippet.json` (tripwired), consumed
by the installer. **User-level only** (journal `d5`) — absolute command paths
into `$CODEX_HOME/super-fr-hooks/`, no project-level `.codex/hooks.json` with an
unverified relative-path base.

### D. Install / uninstall / doctor → `fr codex`
Invasive, reversible mutations as tested Python (`packages/fr/src/fr/codex.py`,
`commands/codex_cmd.py`), registered as `app.add_typer(codex_app, name="codex")`:

- `fr codex install --source <checkout> [--home ~/.codex]` — copy the hook tree
  to `$CODEX_HOME/super-fr-hooks/`, merge managed entries into
  `~/.codex/hooks.json` (idempotent, keyed by command), apply the AGENTS.md
  block, install rule bodies, and **link the skills, repairing stale/dangling
  links**.
- `fr codex uninstall` — reverse every one of the above; touch only super-fr's
  own files.
- `fr codex doctor` — report dangling/stale `$CODEX_HOME/skills/fr-*` links,
  missing hook registrations, and an untrusted-hooks reminder. Exists because
  the failure mode is **silent** (journal `v3`).

`scripts/install.sh` gains an opt-in Codex path, gated exactly like the others:
`CODEX_SKILLS_INSTALL=1` **or** `~/.codex` exists.

### E. Docs
- **README** — a `### Codex CLI` section (peer of Hermes/OpenCode): opt-in
  install, a table of exactly what lands where, `fr codex install|uninstall|doctor`,
  the enforcement surface (edits **and** bash), and — stated plainly — the trust
  caveat from §3.4 and the fact that nothing here proves a live Codex session
  loaded anything. Quickstart + Components table updated.
- **`fr-isolation` SKILL.md** — add Codex to the status-line/harness picture.
  The file is **exactly at the test-enforced 120-line cap**, so this requires
  compressing existing prose, not appending (journal `d10`).
- **AGENTS.md** — register the new generated mirror in the canonical-vs-generated
  section, so no one hand-edits `.agents/skills/`.

## 5. Risks & mitigations

- **Trust makes an installed hook inert until reviewed, and re-inert on every
  change** (§3.4). Mitigation: documented prominently; `fr codex doctor`
  reminds. Cannot be fixed from super-fr's side.
- **The relative-path trap (journal `d7`)** would silently disarm the gate.
  Mitigation: explicit RED-first test asserting a relative-path patch denies.
- **`tool_input.command` encoding for apply_patch is [assumed]** (§3.3).
  Mitigation: the extractor keys off the `*** … File:` markers wherever they
  appear, so a shell wrapper or a raw body both parse; a fixture test pins both.
- **Global AGENTS.md byte budget** (§3.2) — measured at 90% consumption if the
  block inlines rule bodies. Mitigation: pointer block, test-enforced ≤ 2 KiB.
  Residual risk accepted: a consuming repo whose own AGENTS.md already exceeds
  ~30 KiB is over the cap regardless of what super-fr adds; the README says so.
- **No live-session proof.** Skills discovery IS empirically verified via
  `codex debug prompt-input`; hook firing is **not** — it needs a real session
  plus a trust grant. Mitigation: §6 Test Plan, and honest README wording.
- **Four enforcement implementations** (Claude, Hermes, Codex shell; OpenCode TS).
  Mitigation: all three shell tracks share the decision library; only I/O differs.

## 6. Test Plan (post-merge, operator-driven)

Requires a real Codex install (the operator has one) and a trust grant:

1. **Install:** `CODEX_SKILLS_INSTALL=1 bash scripts/install.sh`. Verify
   `~/.codex/skills/fr-goal` resolves (not dangling) and that
   `codex debug prompt-input` lists the `fr-*` skills.
2. **Repair:** break a link deliberately (`ln -sfn /nonexistent ~/.codex/skills/fr-goal`),
   run `fr codex doctor` → it REPORTS the dangling link (Codex itself would not);
   `fr codex install` → repaired.
3. **Rules:** confirm the `<!-- super-fr:rules … -->` block is in
   `~/.codex/AGENTS.md` and that a Codex session honors it.
4. **Trust:** run `/hooks` in Codex, confirm the two super-fr entries appear as
   untrusted, and trust them. Confirm an un-trusted hook does NOT fire.
5. **Enforcement — edits:** in an fr-enabled repo *outside* an isolation
   workspace, ask Codex to edit a tracked file → `apply_patch` is **denied**
   with the fr-isolation reason. Inside a valid workspace → allowed.
   `FR_BASE_OK=1` allows a one-off. A multi-file patch touching one tracked
   file → denied as a whole.
6. **Enforcement — bash:** ask Codex to `git commit` outside isolation → blocked.
7. **Uninstall:** `fr codex uninstall` removes the hooks, the block and the
   links, leaving the operator's own Codex config intact.

## 7. Acceptance rows (born here; presented at spec review)

Added with `fr acceptance add --origin
super-fr:docs/superpowers/specs/2026-09-16-codex-harness-adapter-design.md`:

1. **`codex-skills-delivery`** — *Installing super-fr under Codex makes the
   `fr-*` skills discoverable in a Codex session.* unit (sync tripwire +
   install wiring) → post-merge manual (Test Plan 1).
2. **`codex-skills-link-repair`** — *A stale or dangling `~/.codex/skills/fr-*`
   link is detected and repaired, because Codex itself fails silently.* unit
   (doctor/install tests) → post-merge manual (Test Plan 2).
3. **`codex-rules-agents-block`** — *super-fr's rules reach a Codex user via a
   managed, reversible, size-budgeted `~/.codex/AGENTS.md` block.* unit.
4. **`codex-isolation-gate-edits`** — *Codex blocks an `apply_patch` touching a
   tracked file outside a valid fr-isolation workspace — multi-file and
   relative paths included — honoring FR_BASE_OK and `.fr-isolation-allow`.*
   unit → post-merge manual (Test Plan 5).
5. **`codex-isolation-gate-bash`** — *Codex blocks git/gh mutations outside
   isolation.* unit → post-merge manual (Test Plan 6).

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-09-16-codex-harness-adapter | `derio-net/super-fr` | `2026-09-16-codex-harness-adapter` | — |
