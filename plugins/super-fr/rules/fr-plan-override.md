## Plan Skill Override

When the brainstorming skill says to invoke `writing-plans`, invoke `fr-plan` instead.
When any skill references `superpowers:writing-plans`, use `fr-plan`.

## Autonomous Goal Override

When the operator asks for a feature to be built autonomously — /fr-goal,
/goal, "build this autonomously", "ask your questions once then build it",
"take this to a PR", "no approval gates", "auto mode" — invoke `fr-goal`
FIRST, before brainstorming. fr-goal wraps and sequences brainstorming,
fr-plan, and fr-execute with the operator's gate-waiving contract; starting
with plain brainstorming loses that contract and reintroduces the approval
pauses the operator explicitly waived.

## Brainstorming Override

In a repo with fr plans (`docs/superpowers/plans/`) or devcontainer profiles
(`.devcontainer/<profile>/`), feature brainstorms use `fr-brainstorming`
instead of plain brainstorming — it enters fr-isolation first, so the base
repo is never touched. Plain brainstorming remains for non-fr repos and
non-feature ideation.

## Debugging Override

In a repo with fr plans (`docs/superpowers/plans/`) or devcontainer profiles
(`.devcontainer/<profile>/`), debugging a bug, test failure, or unexpected
behavior uses `fr-debugging` instead of plain
`superpowers:systematic-debugging` — it enters fr-isolation first (reusing an
active workspace, else a fresh `fix/<slug>` branch), so the base repo is never
touched, and delivers the fix as a reviewed PR. Plain systematic-debugging
remains for non-fr repos and quick non-isolated checks.

## fr-* Skill Overview

For a condensed overview of the fr-* skills and their CLI subcommands, run `fr skills`.
