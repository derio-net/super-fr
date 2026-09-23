# Uninstall every installed Claude rule

- **Date:** 2026-09-23
- **Status:** designed
- **Origin:** gh#457
- **Goal:** `scripts/install.sh --uninstall` removes every Claude rule installed by `install.sh`.

## 1. Problem

The install path copies four rule files into `~/.claude/rules/`, but the
uninstall path removes only `fr-plan-override.md` and
`fr-worktree-override.md` (plus the retired `vk-plan-override.md`). The
installed `fr-isolation-required.md` and `no-claude-p-batch.md` are left behind.
The existing install drift guard derives shipped rules from `plugins/`, but
does not assert that uninstall removes them.

## 2. Design

Keep a single install-side list of Claude rule filenames and use it for both
copying and uninstall removal. Preserve removal of the retired
`vk-plan-override.md`, which is not part of the current install list.

Extend the installer integration test to derive the expected current filenames
from the install-side list, install into its fake home, uninstall, and assert
that every derived file is gone. Also assert removal of the retired filename.
This pins the relationship in both directions: the test follows changes to the
install-side list, and every rule the installer delivers is removed. Add the
test reference to the existing `invariants-tripwires` acceptance row.

## 3. Test Plan

**In this PR:**

1. Focused `tests/integration/test_install_sh.py` uninstall test proves all
   install-side-derived rules and the retired rule are removed after install.
2. `tests/unit/test_install_copies_rules.py` continues to prove each shipped
   source rule is wired into installation.
3. `fr acceptance check` passes with the integration test referenced by the
   existing `invariants-tripwires` row.

**Post-merge, operator-driven:**

4. Run the focused uninstall integration test from the merged checkout.

## 4. Scope

Patch version bump required by the repository's release convention because
`scripts/install.sh` changes user-observable installer behavior.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-09-23-uninstall-installed-rules | `derio-net/super-fr` | `2026-09-23-uninstall-installed-rules` | — |
