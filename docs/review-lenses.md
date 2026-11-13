---
title: "Review lenses: examining the whole feature from one angle at a time"
tldr: |
  A phase review reads one phase. A lens reads the whole feature under one concern:
  security, tests, errors, simplicity, or one your repo defines. Any agent can add a
  lens when the work gives it a reason, a path rule can require one, and a lens review
  before delivery dispatches one reviewer per lens and refuses to continue until each
  has reported. This guide covers what a lens is, the four shipped texts, how one gets
  added, the review, the table in the pull request, and `.fr/lenses.yaml`.
standalone_style: broadsheet
covers:
  - packages/fr/src/fr/lenses/**
  - plugins/super-fr/lenses/**
  - packages/fr/src/fr/commands/lenses_cmd.py
reviewed: 2026-11-13 new page
---

## What a lens is

Phase reviews are good at what a phase got wrong. They are poor at what only shows when
you stand back: a token that one phase logs and another phase sends to the forge, a
helper two phases each wrote, a failure path nobody tested because each phase thought
it was the other's. A **lens** is an instruction text for a reviewer who reads the whole
diff from one angle. It is not a checklist the code must pass; it is a question put to
a fresh context that has not seen the implementation being argued for.

A feature has a **lens set**. It starts empty. Lenses get into it for a reason, and the
reason is kept, so the pull request can say why a reviewer was asked to look.

## The four texts fr ships

Each one ends the same way: a problem a reviewer sees outside its lens is still
reported, as an ordinary finding.

- **security**: input that reaches a shell, a query, a path, a template or a
  deserialiser without validation; secrets or tokens written to logs, errors,
  artifacts or the forge; authorisation checks that are missing, or made after the act
  they guard; new dependencies, and what they can reach; permissions wider than the
  change needs.
- **tests**: whether the new tests would fail if the behaviour were wrong. A test that
  restates the code under test, one that covers only the easy input or one kind of
  user, a failure path with no test, a mock standing in for the thing the test is meant
  to exercise. Not coverage numbers.
- **simplicity**: a helper, layer, option or abstraction the change does not need; code
  that duplicates something the repo already has, or that two phases each wrote; names
  that do not say what the thing is; a function a reader cannot follow in one pass. Not
  style a formatter or linter owns.
- **errors**: a failure that is swallowed, turned into a default, or reported without
  what a person needs to act on it; a new failure path with no log or signal; a retry or
  fallback that hides the cause.

`fr lenses list` prints the set your repo has, and `fr lenses show <id>` prints one
text in full.

## How a lens gets added

There are two ways in, and neither is the operator's job.

**An agent asks for one.** Any step that writes a journal can carry a lens in its step
record:

```yaml
journal:
  - {kind: lens, lens: security, title: "the retry path builds a shell command"}
```

The title is the reason, one line. fr assigns the entry's id and stamps the step that
added it, so two agents adding the same lens never collide and the pull request can say
who wanted it. The brainstorm, the spec review, the plan, an implementer and a phase
reviewer can all do this; a read-only reviewer suggests one in its return and the
orchestrator records it. Outside a run, `fr journal add --kind lens --lens <id> --title
"<why>"` does the same with no step. A lens is never removed: nothing closes or
withdraws it, because the point is that a concern once raised stays raised.

**A path rule requires one.** A repo can say that a change touching certain files always
gets a lens, whatever any agent thought (see the config below). The rules in force are
the union of the default branch's and the branch's own, so one pull request can add a
repo's first rule and be held to it, but no pull request can remove a rule from under
itself.

## The lens review

Between the per-phase reviews and delivery there is one step, `lens-review`. fr computes
the set again at that point from the journals and the branch's diff, and the step's
brief carries it: per lens its text, why it is there, the diff's merge-base and the
rule its reviewer must return by.

With an empty set there is nothing to do and the step closes at once. Otherwise the
orchestrator dispatches **one reviewer per lens**, each in its own context and given only
its own lens, never one of the phase reviewers and never the implementer. Each ends its
return with a `review-lens` block naming the lens and the changed files it examined, and
its findings carry the lens in their id (`l-security-r1`). Findings are handled as a
phase review's are: fixed with a test, refuted with reasoning, or filed as out of scope.

The step refuses to close when:

- a lens in the set has no reviewer, or one id is named for two lenses, or an id was
  never dispatched in this session;
- a return names another lens, or a file the feature did not change;
- a lens finding is still open;
- a lens was added during the review, or a fix newly matched a path rule. The set is
  computed again at the close, and the refusal prints that lens's text so it can be sent
  to a reviewer.

A run started before this existed is not lost: `fr run reshape` inserts the step into a
run that has not reached delivery, and `fr run adopt --supersede` carries one that has.

## What the pull request shows

The pull request body gets a **Review lenses** section after the findings sections:

| Lens | Why | Files examined | Findings |
|---|---|---|---|
| security | rule `src/auth/**` (src/auth/session.py) | 2 | l-security-r1 fixed, l-security-r2 out of scope (#1432) |
| tests | implement-phase phase 2: "the retry path is only tested with a mock" | 5 | none |

With an empty set the section says that no lens was requested for this change. If the
branch changed `.fr/lenses.yaml` the section says so, because a branch can alter what a
lens asks. Where fr could not read a reviewer's return the count reads "not observable".
A run that began before lenses existed says so. Under `forge.pr_body: minimal` the
section is in the full render that is kept beside the run, not on the pull request.

## `.fr/lenses.yaml`

Every key is optional and an unknown key is refused:

```yaml
disable: [errors]            # a lens this repo does not use
lenses:
  accessibility:             # a lens of your own
    title: Accessibility
    brief: |
      Review the whole change for ...
  security:                  # the same id replaces the shipped text
    title: Security
    brief: |
      ...
require:                     # path rules
  - paths: ["src/auth/**", "**/migrations/*.sql"]
    lenses: [security]
```

A lens id is lowercase letters, digits and hyphens, starting with a letter, because it
travels inside journal headers and finding ids. A path rule cannot require a lens the
repo has disabled; `fr lenses check` fails a config that does.

## The commands

All read-only:

- `fr lenses list`: the effective lenses and where each comes from.
- `fr lenses show <id>`: one lens's instruction text.
- `fr lenses check`: exit 1 when `.fr/lenses.yaml` has a problem.
- `fr lenses status`: the feature's lens set, each lens with every reason and the step
  that added it, or the rule that requires it and one matching file.

## What it does not prove

A lens review is a reviewer's reading, not a measurement. fr verifies that a reviewer
for each lens was dispatched, that its return names real changed files, and that its
findings were closed; it cannot verify that the reviewer looked hard, or that an empty
findings list means the angle is clean. The count of files examined is what the reviewer
says it read, checked against the diff, not a record of what it understood. And an empty
set means nobody had a reason to ask, not that the change is safe on every axis.
