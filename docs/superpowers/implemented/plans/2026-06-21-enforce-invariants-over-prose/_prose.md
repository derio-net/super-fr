# Enforce invariants over prose — Tasks 2 & 3 (super-fr#328)

Spec: `docs/superpowers/specs/2026-06-21-enforce-invariants-over-prose-design.md`.

Task 1 (merge-race) already shipped in v3.4.x; this plan delivers the two
remaining tasks as one PR.

## Why this shape

The umbrella principle is "enforce, don't prose." So every deliverable here is
either executable enforcement (a PreToolUse hook, a CI tripwire) or the marker
state that enforcement reads — and each guard's *logic* is unit-tested against
synthetic violations, not just asserted on the clean tree.

## Phases

1. **Marker lifecycle.** `fr isolation up` writes `.fr-isolation` (JSON
   identity: toplevel, branch, mode, created_at) at the worktree root and
   appends it to the shared `info/exclude`; `down` removes it. This is the
   state the Task 3 hook reads. TDD over `FakeRunner` in `test_isolation.py`.

2. **Edit/Write enforcement hook.** `fr-isolation-required.sh`
   (PreToolUse, `Edit|Write|MultiEdit|NotebookEdit`), plugin-registered in
   `hooks.json`. Blocks edits to tracked source in an fr-enabled repo unless
   the edit is inside a valid isolation workspace (marker present + recorded
   toplevel == current toplevel + a real linked worktree). Escapes:
   `.fr-isolation-allow` globlist, `FR_BASE_OK=1`. Complementary to the
   existing session-sentinel Bash guard — different tool, session-independent.
   TDD shells out to the script over real git repos/worktrees.

3. **Leak prevention + tripwires.** `.fr-isolation` in `.gitignore`; a pytest
   tripwire failing if `.fr-isolation` is ever tracked; and the Task 2 tripwire
   failing if any `packages/*/src/**` file shells out to `claude -p`. Each
   tripwire's scan function is unit-tested with a planted violation and a clean
   input, then run against the real tree.

4. **Rules, docs, install.** Shipped operator rule
   `plugins/super-fr/rules/fr-isolation-required.md` + repo-level mirror
   `.claude/rules/fr-isolation-required.md`; the Task 2 convention rule
   `plugins/super-fr/rules/no-claude-p-batch.md`; `install.sh` cp lines for
   both shipped rules; a `CLAUDE.md` conventions pointer; a concise marker/hook
   mention in the `fr-isolation` SKILL.md (within the 120-line cap). Guarded by
   a drift test asserting every shipped rule is installed by `install.sh`.

5. **Version bump.** `scripts/bump-version.py minor` → 3.5.0 (a new mandatory
   enforcement hook is a user-visible workflow addition). Commit the four
   version files together; `--check` and `fr --version` confirm.
