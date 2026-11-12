---
title: "fr-debugging: Root Cause First, Then a Fix You Can Review"
date: 2026-11-11
draft: false
tldr: |
  When something is broken, an agent's instinct is to try a fix. fr-debugging makes it
  find the cause first, inside an isolated workspace, write down every hypothesis it
  rejected, and deliver the fix as a reviewed pull request that pins the bug with a
  failing test.
standalone: true
standalone_style: broadsheet
covers:
  - plugins/super-fr/skills/fr-debugging/SKILL.md
  - packages/fr/src/fr/journal/**
  - packages/fr/src/fr/commands/journal_cmd.py
reviewed: 2026-11-12 skill wording only (fr-enabled, not vk-enabled); nothing this page describes changed
---

## Overview: why "just try something" is the expensive path

A fix applied without understanding the cause is a guess that happens to pass, and the next
guess lands on top of it. fr-debugging wraps the `superpowers:systematic-debugging` method,
whose rule is that there are no fixes without a root cause, and adds the two things that make
that rule survive a real session: the work happens **in isolation**, and the reasoning is
**written down as it goes**.

You reach for it whenever debugging starts: a bug, a failing test, behaviour you did not
expect, "why is X happening". It also fires when [fr-goal](01-fr-goal.md) hits a bug in the
middle of building something.

The skill owns *where* the debugging happens and the autonomy contract. It deliberately does
not restate *how*: the four phases (root cause, pattern, hypothesis, implementation), the red
flags and the supporting techniques are delegated unchanged, because that skill evolves on its
own.

## A worked example

A test fails intermittently and you do not know why. Start in isolation, with a branch named for
the bug:

```bash
fr isolation up --branch fix/flaky-limiter-test
```

A cold-start `fix/<slug>` is cut from the freshly fetched default branch, so the fix is clean of
whatever your checkout is parked on. Pass `--base HEAD` to debug on your current branch on
purpose. If you are already inside an active workspace, for example a bug found mid-feature,
**reuse it**: the failing test and the fix join that feature's branch and PR, and a second
competing PR is not opened. `fr isolation status` confirms where you are.

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

Then, test first, it writes a failing test that pins the cause, makes it pass, and records it
with `--kind finding --state fixed`. The PR is opened from there.

## The hard gate: isolation before anything

Before any command, reads included, the workspace exists. A cold start with no devcontainer
profile is a hard stop in devcontainer mode: there is no unisolated fallback, so the skill
offers the [fr-init](fr-init.md) interview. A broken container is repaired with
`fr isolation restart`, then `fr isolation rebuild`, both of which keep the worktree, the cursor
and uncommitted work. Never `down --force`: it keeps the run record but destroys the workspace
and the fix inside it. See [fr-isolation](fr-isolation.md).

## Autonomous, with two hard stops

Like fr-goal it runs to a reviewed PR with no intermediate approval gates, except at the two
checkpoints the method reserves for a human. At each it stops, says what it found and tried, and
asks, because a wrong guess shipped in a PR costs more than a paused run:

- **"I don't understand X."** Investigation cannot form one confident hypothesis: the bug is not
  reproducible, or the evidence is genuinely ambiguous.
- **Three fixes have failed.** That is not a failed hypothesis, it is a signal the architecture
  is wrong. After the third, it presents the pattern (each fix exposing a new coupling) and asks
  before a fourth attempt.

Everything else runs unattended: reading errors, reproducing, instrumenting, pattern analysis,
testing one hypothesis at a time, writing the failing test, the fix, the milestone review.

## The debug journal

The investigation is recorded in a `debug`-scope journal,
`docs/superpowers/journals/debug/<slug>.md` (date the slug yourself if you want one in
the name), appended **as you go** and not written up at
the end. That continuous flush is the point: the trail of rejected hypotheses is the most
compaction-vulnerable artifact in the whole session, so each verdict is persisted the moment you
reach it. Each `fr journal add` is one validated step, one commit, one line back.

| `--kind` | What it holds |
|---|---|
| `repro` | the failing behaviour and the exact repro steps |
| `hypothesis`, `ruled-out` | each hypothesis and its verdict as tested: the trail future debuggers would otherwise re-walk |
| `root-cause` | the single confirmed cause, in the form "X because Y" |
| `finding --state fixed` | the source change and the failing test that pins it |
| `review` | the review of the fix, naming the findings raised or that there were none |

A bug fix does not enter the spec-then-plan pipeline, but the journal is durable and searchable.
`fr journal render --scope debug --slug <slug>` prints it as Markdown.

## Delivering the fix

1. **Verify first.** The new test passes and nothing else broke.
2. **Docs check.** In a repo with `.fr/docs.yaml`, run `fr docs check` before opening the PR. A
   page covering a path the fix changed needs an edit, or its `reviewed` stamp updated when it is
   still true. See [the docs-currency guide](../docs-currency.md).
3. **One PR, through fr.** The skill pushes with `fr push` and opens the draft with
   `fr pr create`, never `git push` or the forge's CLI. Both commands apply the repo's git policy
   (`git.*` in `fr settings show`). Under `push: ask` or `pr: ask` each one refuses once and prints
   a request id. The agent asks you, records your approval in the debug journal, and runs the
   command again. `fr push` also checks commit subjects against the repo's templates. The body is
   derived from the debug journal: root cause, fix, and the failing-test-first story.
4. **Record the review.** Add a `review` entry. There is no run cursor here to enforce it, so
   nothing fails if you skip it; that is exactly why it is written down rather than assumed.
5. **Push on the host** and confirm `git rev-list --count @{u}..HEAD` prints `0`. Every journal
   entry is a local commit nothing pushes. Left unpushed, the PR merges without its review record.
6. **Hand off.** The skill ends by relaying the close-out command, `fr pickup --branch <branch>`,
   as the last line of its message. After the merge a new session runs it from the base clone.

The PR stays a draft: review approval and the ready transition are yours.

## Limits

- It is a discipline, not a debugger. It cannot make a non-reproducible bug reproducible; it
  stops and asks.
- A fix found inside a feature's workspace rides that feature's PR, by design.
- Journals written before the move to `journals/debug/` stay where they are. There is no
  migration for them.

## Where to go next

- [fr-isolation](fr-isolation.md) explains the workspace the whole investigation runs in.
- [fr-goal](01-fr-goal.md) is where the same journal discipline covers a feature.
- [fr-triage](fr-triage.md) is how a pile of reported bugs becomes batches worth fixing.
