# OpenCode slash-command support for the fr-* skills

**Date:** 2026-07-08
**Status:** Draft — brainstormed with operator (batched Q&A, 2026-07-08).
Intended to be one-shot with `/fr-goal`.
**Target repo:** derio-net/super-fr.
**Builds on:**
`docs/superpowers/implemented/specs/2026-07-08-opencode-adaptation-design.md`
(the spec that gave OpenCode skill/rule/isolation-enforcement parity earlier
today).

## Problem

OpenCode discovers `fr-*` skills fine (per the adaptation spec above), but it
has **no notion of invoking a skill via a literal `/name` slash command** —
that's a separate mechanism entirely (`commands/<name>.md` files, or the
`command` key in `opencode.json`; verified against
https://opencode.ai/docs/commands 2026-07-08). Skills are agent-invoked: the
agent matches the operator's natural-language request against each skill's
`description` and calls the `skill` tool itself.

Several `fr-*` skill descriptions explicitly reference "/fr-goal" as a trigger
phrase (e.g. `fr-goal`'s frontmatter: "ALWAYS use when the operator invokes
/fr-goal or /goal"), but since no OpenCode command named `fr-goal` is
registered anywhere, typing `/fr-goal` in the OpenCode TUI:

- shows nothing in the `/` command picker (no autocomplete, no
  discoverability), and
- only "works" today because the unrecognized `/fr-goal` text is sent to the
  agent verbatim as a normal chat message, which then happens to pattern-match
  the literal string against the skill's own description.

That's fragile and undiscoverable. This spec adds real, registered OpenCode
slash commands that wrap each already-mirrored `fr-*` skill.

## Decisions (operator, 2026-07-08 batched Q&A)

| Question | Answer |
|---|---|
| Delivery scope | **Both** — repo-local `.opencode/commands/` (dogfood, committed, zero install) *and* `scripts/install.sh` global delivery to `~/.config/opencode/commands/`, gated on the same existing opt-in (`OPENCODE_SKILLS_INSTALL=1` / `~/.config/opencode` present) the skills mirror already uses. Matches `2026-07-08-opencode-adaptation-design.md`'s delivery split exactly. |
| Which skills get commands | All 9 skills already OpenCode-mirrored (`fr-acceptance`, `fr-brainstorming`, `fr-debugging`, `fr-execute`, `fr-goal`, `fr-init`, `fr-isolation`, `fr-plan`, `fr-progress`). `super-fr-dispatch`'s skills (`fr-dispatch`, `fr-runner`) stay out of scope — inherited directly from the adaptation spec's own explicit decision ("core only... super-fr-dispatch is out of scope for this pass"); they have no OpenCode skill mirror to dispatch to in the first place, so a command wrapping them would call a skill name OpenCode can't resolve. |
| Command content | Fully mechanical — generated from each skill's own SKILL.md frontmatter (`name` + `description`), zero hand-authored per-command files, following the same single-canonical-source discipline as the skills/instructions mirrors. |
| Version bump | **Minor** — new user-visible capability (real slash-command invocation), the same classification the sibling OpenCode-adaptation spec used for "OpenCode support" broadly. |

## Design

### 1. Third generated mirror: `.opencode/commands/`

Extend `scripts/sync-opencode.py` (already generates `.opencode/skills/` and
`.opencode/instructions/` from `plugins/super-fr/skills/` and
`plugins/super-fr/rules/`) with a third canonical/mirror pair:

- `canonical_commands()` — for each `plugins/super-fr/skills/<name>/SKILL.md`,
  parse its YAML frontmatter (`text.split("---", 2)` +
  `yaml.safe_load(parts[1])`, the same idiom
  `tests/unit/test_skill_validation.py` already uses) and render:

  ```
  ---
  description: <verbatim skill description, re-emitted via yaml.safe_dump for correct escaping>
  ---
  Use the `<name>` skill to handle this request.

  $ARGUMENTS
  ```

  No `agent` / `subtask` / `model` frontmatter keys — the command must run in
  whatever agent/mode is already active, exactly like a natural-language
  skill trigger would, not force a subagent detour.
- `mirror_commands()` / `find_commands_drift()` / `sync_commands()` — same
  shape as the existing skill/instruction trio (missing / extra /
  content-diff detection; wired into the existing `--check` CLI path; default
  run writes/overwrites).
- `.opencode/commands/<name>.md` is committed (not gitignored), matching
  `.opencode/skills/`.
- New CI tripwire `tests/unit/test_tripwire_opencode_commands_sync.py`,
  structurally identical to `test_tripwire_opencode_skills_sync.py`
  (dynamically imports `sync-opencode.py`, asserts `find_commands_drift()`
  is empty, plus a non-empty floor assertion).

`scripts/sync-opencode.py` gains `import yaml` — already a first-class
workspace dependency (`packages/fr/pyproject.toml`); the script and its
tripwire tests only ever run under `uv run` (CI's `test` job does
`uv sync && uv run pytest`), so this doesn't add an unavailable-at-runtime
risk. Update the module docstring to describe the third mirror and note that
direct invocation should be `uv run scripts/sync-opencode.py`.

### 2. Installer delivery

`scripts/install.sh`'s existing "OpenCode skill delivery" step (7b) — same
`if` gate, same loop over `plugins/super-fr/skills/*/` — gains, per skill:

```bash
mkdir -p "$OPENCODE_COMMANDS_DIR"
cp "$PLUGIN_ROOT/.opencode/commands/$skill.md" "$OPENCODE_COMMANDS_DIR/$skill.md"
```

with `OPENCODE_COMMANDS_DIR="$HOME/.config/opencode/commands"` declared
alongside the existing `OPENCODE_SKILLS_DIR`. This copies from the repo's own
already-synced, CI-guarded `.opencode/commands/` mirror rather than
regenerating at install time — install.sh stays bash+jq only, no Python/yaml
dependency added to it.

`--uninstall` gains a matching removal loop (mirrors the existing
`$OPENCODE_SKILLS_DIR` cleanup loop).

### 3. Tests

- `tests/unit/test_tripwire_opencode_commands_sync.py` — new, per §1.
- `tests/unit/test_install_copies_opencode_commands.py` — new, structurally
  identical to `test_install_copies_opencode_skills.py`'s three tests
  (delivery wiring present, opt-in gate reused not reinvented, `--uninstall`
  cleanup present), adjusted for `OPENCODE_COMMANDS_DIR` / `.opencode/commands`.

### 4. Non-goals

- No change to how skills are invoked in natural language — description
  matching keeps working unchanged; commands are an additional, explicit
  invocation surface, not a replacement.
- No custom per-skill argument parsing (e.g. distinguishing `fr-isolation up`
  vs `status`) — `$ARGUMENTS` passes the operator's raw trailing text
  straight through; the agent, once it has loaded the skill's full
  instructions, interprets it.
- `super-fr-dispatch` skills (`fr-dispatch`, `fr-runner`) — unchanged, no
  commands added, consistent with their absence from the existing OpenCode
  skills mirror.
- `fr skills` CLI output — out of scope for this pass; it's a hand-maintained
  free-form summary already documented as such, not a generated surface this
  spec touches.

## Test Plan (post-merge, operator-driven)

Mirrors the sibling OpenCode-adaptation spec's approach — this needs a live
`opencode` binary, which CI can't run:

1. In a fresh clone/worktree of merged `main`, run `opencode` and confirm
   `/fr-goal`, `/fr-plan`, etc. appear in the TUI's `/` command picker
   (repo-local delivery, zero install).
2. Invoke `/fr-progress` (a low-stakes, read-only skill) with no arguments
   and confirm the agent picks up the fr-progress skill and responds
   accordingly (template dispatch works end to end, including the
   empty-`$ARGUMENTS` case).
3. Run `scripts/install.sh` with `OPENCODE_SKILLS_INSTALL=1` against a
   scratch `$HOME`, confirm `~/.config/opencode/commands/fr-goal.md` (and
   siblings) appear; run `--uninstall`, confirm they're removed.

## Acceptance rows (added at spec time, presented at spec review)

- "An operator can type `/fr-goal` (and the other 8 mirrored `fr-*` skills)
  as a real OpenCode slash command inside a super-fr clone, with no install
  step" — business-level, verified via Test Plan steps 1–2; capability:
  OpenCode adaptation (continues the existing group).
- "An operator can run `scripts/install.sh` and get `/fr-goal` etc. available
  as OpenCode slash commands globally, with clean `--uninstall` removal" —
  verified via Test Plan step 3.

## References

- `docs/superpowers/implemented/specs/2026-07-08-opencode-adaptation-design.md`
  — this spec's direct predecessor and template.
- `scripts/sync-opencode.py` — mirror generation to extend.
- `scripts/install.sh` — installer step 7b to extend.
- OpenCode docs: https://opencode.ai/docs/commands, https://opencode.ai/docs/skills
