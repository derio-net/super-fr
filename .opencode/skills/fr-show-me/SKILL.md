---
name: fr-show-me
description: >
  Use when the operator says "show me", "draw it", "visualize it" or "what does this look
  like", when a spec needs its `## Design shape`, or when a run needs its shape file for
  the PR's `## Shape of the change`. Picks the smallest text view (pseudocode, a tree, a
  structure-diff, mermaid) that makes the point.
---

# fr-show-me

**Announce at start:** "I'm using fr-show-me to draw <what> as <view>."

Prose describes a change; a picture shows which boundaries move. This skill is a menu of
text views, ranked from cheapest, and the rules for choosing among them. Every view is
Markdown, so it renders in a chat, a spec, a journal and a PR body alike.

## The rule

**Pick the smallest view that makes the point clear.** Use one view or several, never all.
Keep only what the current question needs: leave out files, calls and steps that do not
move. Place each visual next to the short text it supports, not in a gallery at the end.

**A visual is a claim about the code.** Every file, function, module and step it names
must exist, or be one the change creates, and what it draws must match the text beside
it. A reviewer checks it like any other claim.

**Use this repo's own names**, and redact any third-party host, org, repo or person
exactly as the third-party privacy rule says: keep the shape, drop the identity.

## The views, cheapest first

1. **Pseudocode** — five to ten lines of the logic that matters, no syntax noise.
   ```text
   resolve(step):  refuse if a gate fails  →  write the record  →  commit once
   ```
2. **Call tree** — who calls whom, indented, for one path through the code.
   ```text
   fr run resolve --step deliver
     _deliver_pr_gate
       deliver_shape_refusal   # fr/shape.py
       render_pr_body          # fr/record/pr_body.py
   ```
3. **Annotated file tree** — the files a change touches, one responsibility comment each.
   ```text
   packages/fr/src/fr/
     shape.py          # shape-block grammar, the spec section reader
     record/pr_body.py # renders the PR body from journals and records
     run/              # the durable cursor: model, adopt, liveness
   ```
4. **Component tree** — the parts of a system and what each contains, when the unit is a
   service, a package or a page section rather than a file.
5. **Structure-diff** — a `diff` fenced block over a tree, a call stack, a step list or a
   state flow. It shows what a change adds and removes. For example, fr-goal-light against
   fr-goal:
   ```diff
     brainstorm
   - spec-review
     plan
   + spec-plan-review
     plan-review
     implement
   ```
6. **Whole target shape** — the complete tree or flow after the change, when the reader
   needs the end state more than the delta.
7. **Mermaid** — a sequence, state or flow diagram, for an order of events across actors.
   ```mermaid
   sequenceDiagram
     participant A as agent
     participant fr
     A->>fr: fr run resolve <run> --step plan
     fr-->>A: cursor moves, one commit
     A->>fr: fr run advance <run>
     fr-->>A: dispatch brief for the next agent step
   ```

Stop at the first view that answers the question. A file tree with comments usually
beats a diagram; a structure-diff usually beats two whole trees.

## A shape block

Where fr requires a picture it requires a **shape block**: Markdown holding at least one
fenced code block (any of the views above), or exactly one line `none — <reason>` (a
hyphen is accepted for the dash) when no picture helps, for example
`none — a one-line wording fix in one help string`. fr checks this grammar; a reason is
required, and an empty section or prose alone is refused.

## Where fr asks for one

- **A spec's `## Design shape`.** fr-brainstorming writes it; the `brainstorm` resolve and
  every spec-reviewing resolve refuse a spec without a valid one. Draw the change the
  Design section describes: usually an annotated file tree as a structure-diff, plus a
  mermaid sequence when the order of events is the point. The spec reviewer checks every
  name in it against the codebase and the Design text.
- **A run's shape file, `<run-id>.shape.md`**, beside the run's cursor. Write it after
  implementation and commit it before the lens reviewers are dispatched: each lens
  reviewer reads it and reports where it contradicts the diff. Draw what was delivered,
  not what was planned. `deliver` renders it as the PR's `## Shape of the change` and
  refuses while it is missing or not a shape block.
- **On demand.** When the operator asks to see the current topic, answer with the
  smallest view, then one or two sentences on what it shows.

## Writing it well

- Name real paths from the repo root, real functions and real step ids.
- Mark new entries with `+` and removed ones with `-` in a structure-diff; leave the rest
  unmarked context, and only as much of it as places the change.
- One comment per tree entry, saying what it is responsible for, not what changed in it.
- Keep each block under about twenty lines; split by question, not by file count.
- After writing, reread the block against the code. A name that does not exist is a
  finding against you.

## Credit

Adapted from HumanLayer's `show-me` skill (MIT licence): the ranked menu of views and the
smallest-view rule are theirs. This port drops its last-resort browser page, so every view
stays text that every harness renders, and adds fr's shape-block grammar and its two uses.
