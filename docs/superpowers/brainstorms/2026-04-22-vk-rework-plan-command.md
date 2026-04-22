# Brainstorm prompt: a `vk` command for "rework plans"

> **Audience:** the `superpowers-for-vk` repo agent (or whoever maintains
> the `vk` CLI). This document is meant to seed a brainstorm session, not
> prescribe a design.

## TL;DR for the brainstorm partner

Across two real projects (kid-laptops Plans 1–7) we keep hitting the same
recurring pattern: **a plan ships, the parent PR merges, the parent plan is
archived — and then code reviews + demo smoke-tests surface non-blocking
items that nevertheless need to land somewhere and eventually be done.**

We tried three storage strategies before landing on one that works:

1. **GitHub Issues.** Rejected explicitly by the operator
   (`feedback_plan_not_issues` memory rule: "follow-ups go in the plan
   file, not `gh issue create`"). Reason: the plan files are the
   canonical record; Issues drift out of sync with the spec.

2. **`Phase N follow-ups` appendix sections in the parent plan.** Worked
   for in-plan items but had three failure modes:
   - Cross-cutting items end up in whichever plan happened to be open
     when the discovery happened (e.g., a parental-controls bug found
     during a vscode demo got parked in the vscode plan).
   - Items dismissed in PR comments never make it to the appendix —
     they're effectively lost when the PR closes.
   - Once a plan is archived, the appendix items become invisible to
     workflows that only scan `docs/superpowers/plans/`.

3. **Reopening the closed parent plan.** Rejected on instinct — rewrites
   history (the ticked checkboxes become an inconsistent record of what
   was actually delivered when), and `vk plan format` / `vk execute
   check-deps` get confused by a plan that's "Complete" but has new
   unticked items.

The pattern that landed: **a separate, lean "Rework" plan** named after
the parent. First instance was ad-hoc — the
`2026-04-18-kid-laptops-retroactive-sprint-1-5-fixes.md` plan, which
captured eight defects from a sprint-acceptance demo without reopening
the five plans they came from. Codified today (2026-04-22) into a
convention with two more rework plans:

- `2026-04-08-kid-laptops-5-parental-controls-rework-1.md`
- `2026-04-08-kid-laptops-7-vscode-dev-env-rework-1.md`

The convention is documented in
`docs/superpowers/specs/2026-04-07-kid-laptops-design.md` under
"Rework plan convention" — see that section for the canonical form
fields (Origin table, tags, Definition of Done shape, etc.).

## What I want from you

Help me design a `vk` subcommand that operationalises this convention.
Below are the things I think the command should do, the open questions
I haven't decided, and the constraints I do know.

### Constraints (non-negotiable)

- **No GitHub Issues.** Plan files are the source of truth.
- **Original date in filename, not creation date.** Sort order matters
  more than provenance — `2026-04-08-...-5-parental-controls.md` and
  `2026-04-08-...-5-parental-controls-rework-1.md` need to be adjacent
  when the operator lists `docs/superpowers/plans/`.
- **Rework plans must be vk-execute compatible.** Same phase/task/step
  shape so `vk execute check-deps`, `vk execute scope`,
  `vk execute check-step` all work.
- **The parent plan does not get reopened.** Status stays Complete,
  archive location stays canonical.
- **Items are tagged.** `[development]`, `[operations]`, `[decision]`.
  Operations items are manual smoke tests with no commit; decision
  items lay out options before any code lands.

### What I think the command should do

**`vk plan rework <parent-plan-path>`** — scaffolds a rework plan.

Behaviour proposal:

1. Parse the parent plan filename to extract the date prefix and slug.
2. Compute the next rework number (`-rework-1.md` if none exists,
   `-rework-2.md` if `-rework-1.md` is already there, etc.).
3. Render a stub from a template that includes:
   - `Spec` field auto-derived from parent's `Spec:` line.
   - `Parent plan` pointed at parent (move to `archived-plans/` if
     parent is currently in `plans/` — depends on whether parent has
     been archived yet).
   - `Prior rework` if any (chain them).
   - Empty Origin table.
   - Empty Phase 1 with one Task 1 placeholder.
   - Definition of Done block with TODO stubs.
4. Write to `docs/superpowers/plans/<derived-filename>.md`.
5. Print the path so the operator can `$EDITOR` it.

**`vk plan rework-add <rework-plan> --source <PR#> --tag <dev|ops|dec> --item "<text>"`** —
appends a row to the Origin table and creates a placeholder phase for it.

Behaviour proposal:

- Auto-numbers the new origin item.
- Creates a `## Phase N: <derived from item> [agentic]` section.
- Echoes the appended-to file path.

**`vk plan rework-list [--status <not-started|in-progress|done>]`** —
lists open reworks across the repo.

Behaviour proposal:

- Scans `docs/superpowers/plans/` AND `docs/superpowers/archived-plans/`
  for files matching `*-rework-*.md`.
- Shows a table: parent plan, rework number, status, count of unticked
  steps.

### Open design questions

- **Where should the operator declare an "I dismissed this in a PR
  comment" item?** Options: (a) `vk plan rework-add` from the PR thread
  (manual paste of the text), (b) a `gh pr review` integration that
  scrapes "noted, not acting on" comments, (c) trust the operator to
  remember. I lean (a) — keeps the human in the loop without requiring
  PR-API plumbing.

- **What about cross-cutting reworks?** The `2026-04-18-...-retroactive-
  sprint-1-5-fixes.md` precedent is "ad-hoc plan, name it after the
  triggering event." Should `vk` support `vk plan rework-cross-cutting
  <slug>` that creates a cross-plan rework? Or is the convention
  "create a regular plan, reference multiple parents in the header"
  enough?

- **Pre-deploy smoke tests** are a special case of `[operations]` items.
  They eventually want to live in a single, lasting checklist
  (`docs/superpowers/PRE_DEPLOY_CHECKLIST.md` was suggested). Should
  `vk plan rework` know about the checklist file and copy operations
  items there on closeout? Or is duplication acceptable
  (rework plan = "what to do once," checklist = "what to do every
  time")?

- **When does a rework plan get archived?** Same lifecycle as a normal
  plan (move to `archived-plans/` when status is Complete)? Or do
  rework plans stay in `plans/` longer because their items are
  future-triggered?

- **`vk plan list-incomplete` interaction.** Does that command currently
  surface rework plans? Should it filter them by tag (so an operator
  can ask "show me development reworks" vs "show me decision reworks")?

- **Naming: "Rework 1" vs "Round 2" vs "Wave 1".** I picked "Rework"
  for the kid-laptops convention because it's neutral. Open to a better
  word if the brainstorm surfaces one.

- **Templates:** the rework plan body has a recognisable shape (Origin
  table → tag-grouped phases → DoD that echoes the table). Worth a
  template file in `vk`'s package, or rendered from a Python literal?
  Templates would let teams override the shape per-repo.

- **Linkage back to the parent.** Should the parent's "Phase N
  follow-ups" appendix gain a back-pointer block when a rework lands
  ("→ resolved in `2026-04-08-...-rework-1.md` Phase N")? Two paths:
  manual edit, or `vk plan rework-close` that walks the rework's DoD
  back to the parent's appendix and inserts the back-pointer.

### Sample plans to study

If you want to study the convention in the wild before designing:

- `docs/superpowers/archived-plans/2026-04-18-kid-laptops-retroactive-sprint-1-5-fixes.md`
  — the ad-hoc precedent. Cross-plan, defects-driven.
- `docs/superpowers/plans/2026-04-08-kid-laptops-5-parental-controls-rework-1.md`
  — codified single-parent rework. Three items, three phases by tag.
- `docs/superpowers/plans/2026-04-08-kid-laptops-7-vscode-dev-env-rework-1.md`
  — codified single-parent rework. Eight items, five phases (one is
  decision-only). Larger; tests whether the convention scales.

The spec section that codifies the convention:
`docs/superpowers/specs/2026-04-07-kid-laptops-design.md` →
"Rework plan convention".

## Initial brainstorm prompt for the agent

> Read `docs/superpowers/specs/2026-04-07-kid-laptops-design.md`'s
> "Rework plan convention" section and the two sample reworks listed
> above. Then design a `vk plan rework <parent>` subcommand that
> scaffolds a rework plan according to this convention, with attention
> to the open design questions in
> `docs/superpowers/brainstorms/2026-04-22-vk-rework-plan-command.md`.
> Don't write code yet — first walk me through your proposed surface
> (subcommand names, flags, behaviour) and answer each open design
> question with your recommendation + the trade-off. We'll iterate
> on the surface before any implementation lands.
