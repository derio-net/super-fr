---
title: "fr-show-me: A Picture of Every Change"
date: 2026-11-24
draft: false
tldr: |
  Prose says what a change does; a picture shows which parts move. fr-show-me is a short
  menu of text views, from pseudocode to mermaid, and one rule: draw the smallest view that
  makes the point. Every spec carries one as its design shape, and every PR shows one as the
  shape of the change.
standalone: true
standalone_style: broadsheet
covers:
  - plugins/super-fr/skills/fr-show-me/SKILL.md
  - packages/fr/src/fr/shape.py
reviewed: 2026-11-24 new page for fr-show-me, the spec's design shape and the PR's shape of the change (#1641)
---

## Why a picture?

A spec is mostly prose and lists. A pull request body is findings, rows and tables. The
diff shows lines, never which boundaries moved. A reader who wants to know "what does this
change look like?" has to build the picture in their head, and two readers build two
different pictures.

A small drawing settles that. A file tree with one comment per file says where the change
lives. A diff over a step list says which steps came and went. A sequence diagram says who
calls whom, in what order. Each one takes less time to read than the paragraph it replaces.

## The views, and the one rule

The skill lists seven views, cheapest first:

1. pseudocode, a few lines of the logic that matters;
2. a call tree, who calls whom along one path;
3. an annotated file tree, one comment per file;
4. a component tree, for parts bigger than a file;
5. a structure-diff, a `diff` block over a tree, a step list or a state flow;
6. the whole target shape, when the end state matters more than the delta;
7. mermaid, for an order of events across several actors.

The rule is to **pick the smallest view that makes the point clear**. Use one view or a few,
never all of them. Keep only what the question needs, and put each drawing next to the
short text it supports.

Every view is plain Markdown, so it shows up the same in a chat, a spec, a journal and a PR
on every harness. The skill has no browser page and names no harness tool.

A drawing is a claim about the code. Every file, function and step it names must exist, or
be one the change creates. It also uses the repo's own names and keeps third parties out,
as the third-party privacy rule says.

## Where fr asks for one

fr asks for a **shape block** in two places. A shape block is Markdown that holds at least
one fenced code block, or exactly one line `none — <reason>` when no picture would help (a
one-word fix, say). `packages/fr/src/fr/shape.py` holds this grammar, and every check uses
it.

**The spec's `## Design shape`.** fr-brainstorming writes it with fr-show-me's views. The
`brainstorm` step, and every step that reviews a spec, refuse a spec without a valid one.
The spec reviewer then checks the drawing against the code and against the spec's own
Design section: a name that does not exist, or a drawing that the text contradicts, is a
finding.

**The run's shape file, `<run-id>.shape.md`.** It sits beside the run's cursor and shows
what the run delivered, not what the plan said. fr-goal writes and commits it before it
sends out the lens reviewers. Each lens reviewer gets the file's path in its brief, reads it, and
reports any place where it contradicts the diff. At `deliver`, fr renders the file into the
PR body as `## Shape of the change`, and refuses to deliver while the file is missing or is
not a shape block. A run that started before design shapes existed shows "This run predates
design shapes." instead.

`fr archive` moves the shape file to the archive with the run's PR body, so the picture
stays with the record of the change.

## On demand

You can also ask for it directly: "show me how this works", "draw it". The agent answers
with the smallest view and a sentence or two on what it shows.

## Credit

The menu of views and the smallest-view rule come from HumanLayer's `show-me` skill, under
the Massachusetts Institute of Technology (MIT) licence. fr's version drops its last-resort
browser page. It adds the shape-block grammar and the two places fr asks for one.
