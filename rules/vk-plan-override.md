## Plan Skill Override

When the brainstorming skill says to invoke `writing-plans`, invoke `vk-plan` instead.
When any skill references `superpowers:writing-plans`, use `vk-plan`.

## Autonomous Goal Override

When the operator asks for a feature to be built autonomously — /vk-goal,
/goal, "build this autonomously", "ask your questions once then build it",
"take this to a PR", "no approval gates", "auto mode" — invoke `vk-goal`
FIRST, before brainstorming. vk-goal wraps and sequences brainstorming,
vk-plan, and vk-execute with the operator's gate-waiving contract; starting
with plain brainstorming loses that contract and reintroduces the approval
pauses the operator explicitly waived.

## vk-* Skill Overview

For a condensed overview of the vk-* skills and their CLI subcommands, run `vk skills`.
