---
name: fr-brainstorming
description: >
  Brainstorm a feature INSIDE an isolated workspace: invokes fr-isolation
  first, then runs superpowers brainstorming in the worktree/devcontainer —
  the base repo is never touched from the first command on. Use for any
  feature brainstorm in a vk-enabled repo (vk plans or devcontainer profiles
  present), when fr-goal starts its pipeline, or when the operator says
  "brainstorm this feature", "let's design X", or starts creative work that
  will become a spec. devcontainer mode hard-stops without a profile;
  docker-less host/external modes isolate via the worktree instead.
---

# fr-brainstorming

`superpowers:brainstorming`, wrapped in isolation. Exploration commands,
spec drafts, and everything downstream happen in the isolation workspace,
so a brainstorm that becomes a build never has to relocate, and a brainstorm
that dies leaves the base repo pristine.

**Announce at start:** "I'm using fr-brainstorming to design this in isolation."

## 0. Isolation first — hard gate

Before ANY command — exploration, measurement, cluster reads included; an
operator "start with X" never reorders this:

```bash
fr isolation up --branch <feature-branch> [--profile <name>]
```

- Name the branch for the feature now (`feat/<slug>`); the worktree, the
  eventual PR, and cleanup all key off it. The new `feat/<slug>` is cut from
  freshly-fetched `origin/<default>` (#322) — pass `--base <ref>` only to
  stack on something else.
- **No devcontainer profile → HARD STOP — but only in devcontainer mode.**
  Offer to run the fr-init interview immediately; if the operator declines,
  the brainstorm does not proceed. (Under fr-goal, treat it as a blocker:
  pause, fr-init, resume.) On a docker-less host that declares
  `FR_ISOLATION_TARGET=worktree` (or in a prepared external container), `up`
  succeeds without a profile — no stop, the worktree is the isolation.
- From here on, follow the fr-isolation skill's exec-bridge discipline:
  read/edit files in the worktree, run every command through
  `fr isolation exec -- ...`.
- **Standalone invocation only:** also start the run cursor now —
  `fr run start fr-goal --branch <feature-branch>`, or `fr run adopt
  <plan-dir|spec>` when work already exists on disk — so `implement`'s
  `needs: [spec, plan]` later refuses to advance past a plan that was never
  written (#436 instance 1). **Under fr-goal, skip this entirely** — that
  pipeline already started the run, and a second `fr run start` exits 2. It
  also exits 2 (naming the run) if this branch already has one: resume with
  `fr run advance <id>`. Refused over stale artifacts? Run
  `fr migrate artifacts --yes` and retry — `fr run start` is not exempt.

## 1. Brainstorm

Run `superpowers:brainstorming` as usual — understand the context and goal,
explore the codebase (in the worktree), propose approaches, refine into a
design.

- **Standalone invocation:** fully interactive — ask questions as they
  arise, section-by-section validation, the normal brainstorming flow.
- **Under fr-goal:** the sized-round contract applies instead — collect every
  operator-owned decision into one round, rarely two (fr-goal's rules win
  while it drives).

## 2. Hand off

The brainstorm's design document becomes the spec
(`docs/superpowers/specs/<YYYY-MM-DD-slug>-design.md`, committed in the
worktree). **Standalone:** resolve the cursor §0 started with its step
record — the brief's `record` file, filled as you go: `emitted: {spec: <path>}`,
each operator answer as a `decision` in `journal:`, each §3 row in
`acceptance:` — in ONE `fr run resolve <run-id> --step brainstorm --record
<file>`, then drive everything after this through `fr run advance <run-id>`. That is what makes
the cursor a gate rather than a file on disk: `implement`'s
`needs: [spec, plan]` only refuses work that asks it to. Hand off to
`fr-plan` (the fr-plan-override rule already routes
`writing-plans` there). The isolation workspace stays up — planning and
implementation continue in it; cleanup belongs to whoever finishes the run
(`fr isolation down` after the PR merges).

## 3. Acceptance rows — born with the spec, presented at the close

Each key "operator can do X" claim in the design becomes a matrix row — an
`acceptance:` entry of the brainstorm record (`status: not-implemented`,
`origin: [<repo>:<new-spec-path>]`), or with no run `fr acceptance add`
(run `fr acceptance init` first if the repo has no matrix). **The brainstorm
ENDS by presenting the rows to the operator with a one-line defense each** —
the business claim it pins, the target verification level, why it is
business-level rather than an implementation detail. Silent row creation is
not acceptance-of-scope; the presentation is. Under fr-goal the presentation
rides the spec-review step. Hand-off checklist: rows added AND presented.

## Scope notes

- This skill owns WHERE brainstorming happens, not HOW — brainstorming's
  own craft (questions, alternatives, YAGNI) is unchanged.
- Multi-repo features: brainstorm in the repo that owns the spec; other
  repos get their own isolation workspaces when their plans dispatch
  (one workspace, one branch, one PR per repo).
