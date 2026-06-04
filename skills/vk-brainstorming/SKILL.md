---
name: vk-brainstorming
description: >
  Brainstorm a feature INSIDE an isolated workspace: invokes vk-isolation
  first, then runs superpowers brainstorming in the worktree/devcontainer —
  the base repo is never touched from the first command on. Use for any
  feature brainstorm in a vk-enabled repo (vk plans or devcontainer profiles
  present), when vk-goal starts its pipeline, or when the operator says
  "brainstorm this feature", "let's design X", or starts creative work that
  will become a spec. Requires a devcontainer profile — hard stop without one.
---

# vk-brainstorming

`superpowers:brainstorming`, wrapped in isolation. Exploration commands,
spec drafts, and everything downstream happen in the isolation workspace,
so a brainstorm that becomes a build never has to relocate, and a brainstorm
that dies leaves the base repo pristine.

**Announce at start:** "I'm using vk-brainstorming to design this in isolation."

## 0. Isolation first — hard gate

Before ANY exploration command:

```bash
vk isolation up --branch <feature-branch> [--profile <name>]
```

- Name the branch for the feature now (`feat/<slug>`); the worktree, the
  eventual PR, and cleanup all key off it.
- **No devcontainer profile → HARD STOP.** Offer to run the vk-init
  interview immediately; if the operator declines, the brainstorm does not
  proceed — there is no unisolated fallback. (Under vk-goal, treat it as a
  blocker: pause, vk-init, resume.)
- From here on, follow the vk-isolation skill's exec-bridge discipline:
  read/edit files in the worktree, run every command through
  `vk isolation exec -- ...`.

## 1. Brainstorm

Run `superpowers:brainstorming` as usual — understand the context and goal,
explore the codebase (in the worktree), propose approaches, refine into a
design.

- **Standalone invocation:** fully interactive — ask questions as they
  arise, section-by-section validation, the normal brainstorming flow.
- **Under vk-goal:** the batched-Q&A contract applies instead — collect
  every operator-owned decision and ask ONCE (vk-goal's rules win while it
  drives).

## 2. Hand off

The brainstorm's design document becomes the spec
(`docs/superpowers/specs/<YYYY-MM-DD-slug>-design.md`, committed in the
worktree). Hand off to `vk-plan` (the vk-plan-override rule already routes
`writing-plans` there). The isolation workspace stays up — planning and
implementation continue in it; cleanup belongs to whoever finishes the run
(`vk isolation down` after the PR merges).

## Scope notes

- This skill owns WHERE brainstorming happens, not HOW — brainstorming's
  own craft (questions, alternatives, YAGNI) is unchanged.
- Multi-repo features: brainstorm in the repo that owns the spec; other
  repos get their own isolation workspaces when their plans dispatch
  (one workspace, one branch, one PR per repo).
