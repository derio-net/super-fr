---
title: "fr-debugging: Root Cause First, Then a Fix You Can Review"
date: 2026-11-11
draft: false
tldr: |
  When something is broken, an agent's instinct is to try a fix. fr-debugging makes it
  find the cause first, inside an isolated workspace, and write down every hypothesis it
  rejected. It delivers the fix as a reviewed pull request that pins the bug with a
  failing test.
standalone: true
standalone_style: broadsheet
covers:
  - plugins/super-fr/skills/fr-debugging/SKILL.md
  - packages/fr/src/fr/journal/**
  - packages/fr/src/fr/commands/journal_cmd.py
reviewed: 2026-11-12 placement-resolver phase 4, mode=stealth passes --stealth/--target to fr isolation up
---

## Why is "just try something" the expensive path?

A fix applied without understanding the cause is a guess that happens to pass. The next
guess lands on top of it. fr-debugging wraps the `superpowers:systematic-debugging`
method, whose rule is: no fixes without a root cause. It adds the two things that make
that rule survive a real session. The work happens **in isolation**, and the agent
**writes the reasoning down as it goes**.

You reach for it whenever debugging starts: a bug, a failing test, behaviour you did not
expect, "why is X happening". It also fires when [fr-goal](01-fr-goal.md) hits a bug in
the middle of building something.

The skill owns *where* the debugging happens, and the autonomy contract. It deliberately
does not restate *how*. It delegates the four phases (root cause, pattern, hypothesis,
implementation), the red flags and the supporting techniques unchanged, because that
skill evolves on its own.

## A worked example

A test fails now and then, and you do not know why. Start in isolation, with a branch
named for the bug:

```bash
fr isolation up --branch fix/flaky-limiter-test
```

fr cuts a cold-start `fix/<slug>` from the freshly fetched default branch. So the fix is
clean of whatever your checkout holds. Pass `--base HEAD` to debug on your current
branch on purpose.

If you are already inside an active workspace (for example, for a bug found mid-feature),
**reuse it**. Then the failing test and the fix join that feature's branch and PR, and
the skill does not open a second, competing PR. `fr isolation status` confirms where you
are.

From here every command runs through `fr isolation exec -- ...`. The agent reproduces the
failure, and records it the moment it has:

```bash
fr journal add --scope debug --slug flaky-limiter --kind repro \
    --title "limiter test fails 1 in 5" --body "pytest tests/test_limiter.py -k burst, ..."
fr journal add --scope debug --slug flaky-limiter --kind ruled-out \
    --title "Clock skew" --body "Frozen the clock; still fails, so not the clock."
fr journal add --scope debug --slug flaky-limiter --kind root-cause \
    --title "Bucket refill races the assertion" --body "..."
```

Then, test first, it writes a failing test that pins the cause and makes it pass. It
records that with `--kind finding --state fixed`. The skill opens the PR from there.

## Why must isolation come before anything?

The workspace exists before any command, reads included. In devcontainer mode, a cold
start with no devcontainer profile is a hard stop. There is no unisolated fallback, so the
skill offers the [fr-init](fr-init.md) interview.

To repair a broken container, use `fr isolation restart`, then `fr isolation rebuild`.
Both keep the worktree, the cursor and uncommitted work. Never use `down --force`: it
keeps the run record but destroys the workspace and the fix inside it. See
[fr-isolation](fr-isolation.md).

When you ask for `mode=stealth <tracking-repo>@<branch>` (or, from the tracking
repository, `mode=stealth target=<path>`), the skill adds `--stealth` (or `--target`) to
that `fr isolation up`. The debug journal and every other fr record then live in the tracking
repository. The target receives only the fix and one draft pull request with a plain
summary.

## When does it stop and ask you?

Like fr-goal, it runs to a reviewed PR with no approval gates on the way. The exceptions
are the two checkpoints the method reserves for a human. At each one it stops, says what
it found and tried, and asks. A wrong guess shipped in a PR costs more than a paused run.

- **"I don't understand X."** The investigation cannot form one confident hypothesis:
  the bug does not reproduce, or the evidence is genuinely ambiguous.
- **Three fixes have failed.** That is not a failed hypothesis. It is a signal that the
  architecture is wrong. After the third, it presents the pattern (each fix exposes a new
  coupling) and asks before it tries a fourth.

Everything else runs unattended: reading errors, reproducing, instrumenting, pattern
analysis, testing one hypothesis at a time, writing the failing test, the fix, the
milestone review.

## What goes in the debug journal?

The agent records the investigation in a `debug`-scope journal,
`docs/superpowers/journals/debug/<slug>.md`. (Date the slug yourself if you want a date
in the name.) It appends to the journal **as it goes**, and does not write it up at the
end.

That continuous flush is the point. The trail of rejected hypotheses is the artifact
most at risk from compaction in the whole session. So the agent saves each verdict the
moment it reaches it. Each `fr journal add` is one validated step, one commit, one line
back.

| `--kind` | What it holds |
|---|---|
| `repro` | the failing behaviour and the exact repro steps |
| `hypothesis`, `ruled-out` | each hypothesis and its verdict as tested: the trail future debuggers would otherwise re-walk |
| `root-cause` | the single confirmed cause, in the form "X because Y" |
| `finding --state fixed` | the source change and the failing test that pins it |
| `review` | the review of the fix, naming the findings raised or that there were none |

A bug fix does not enter the spec-then-plan pipeline, but the journal is durable and
searchable. `fr journal render --scope debug --slug <slug>` prints it as Markdown.

## How does it deliver the fix?

1. **Verify first.** The new test passes, and nothing else broke.
2. **Docs check.** In a repo with `.fr/docs.yaml`, run `fr docs check` before you open
   the PR. A page that covers a path the fix changed needs an edit. If the page is still
   true, update its `reviewed` stamp instead. See
   [the docs-currency guide](../docs-currency.md).
3. **One PR, through fr.** The skill pushes with `fr push` and opens the draft with
   `fr pr create`, never `git push` or the forge's CLI. Both commands apply the repo's
   git policy (`git.*` in `fr settings show`). Under `push: ask` or `pr: ask`, each one
   refuses once and prints a request id. The agent asks you, records your approval in the
   debug journal, and runs the command again. `fr push` also checks commit subjects
   against the repo's templates. fr derives the body from the debug journal: root cause,
   fix, and the failing-test-first story.
4. **Record the review.** Add a `review` entry. There is no run cursor here to enforce
   it, so nothing fails if you skip it. That is exactly why the skill writes it down
   rather than assume it.
5. **Push on the host**, and confirm that `git rev-list --count @{u}..HEAD` prints `0`.
   Every journal entry is a local commit that nothing pushes. Left unpushed, the PR merges
   without its review record.
6. **Hand off.** The skill ends by relaying the close-out command,
   `fr pickup --branch <branch>`, as the last line of its message. After the merge, a new
   session runs it from the base clone.

The PR stays a draft: review approval and the ready transition are yours.

## What can it not do?

- It is a discipline, not a debugger. It cannot make a bug that does not reproduce
  reproducible; it stops and asks.
- A fix found inside a feature's workspace rides that feature's PR, by design.
- Journals written before the move to `journals/debug/` stay where they are. There is no
  migration for them.

## Where do you go next?

- [fr-isolation](fr-isolation.md) explains the workspace the whole investigation runs in.
- [fr-goal](01-fr-goal.md) is where the same journal discipline covers a feature.
- [fr-triage](fr-triage.md) is how a pile of reported bugs becomes batches worth fixing.
