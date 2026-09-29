#!/bin/bash
# PreToolUse(Agent) hook: refuse dispatching the fr-phase-executor subagent —
# or the read-only fr-spec-reviewer (2026-09-24 spec §E, review p4-f6) — WITH
# `isolation: "worktree"`. fr's isolation worktree already IS the
# executor's working copy; the two mechanisms are mutually exclusive, not
# composable, and combining them deadlocks the agent (#420).
#
# Why a super-fr hook and not an edit to the org `agent-worktree-required.sh`:
# that hook allows on the flag BEFORE it consults its allowlist
# (`[ "$isolation" = "worktree" ] && exit 0`), so its allowlist can only ever
# mean "you needn't pass the flag" — never "you mustn't". It is also
# operator-owned and unversioned. Claude Code runs EVERY matching PreToolUse
# hook and a `deny` wins, so this shipped, versioned hook overrides that early
# allow without super-fr editing a file it does not own.
#
# What the poisoned dispatch does, all confirmed empirically (super-fr#420):
# the agent wakes in a separate locked worktree cut from `main`, where the
# feature branch's spec and plan are invisible (so `fr pickup` is
# unsatisfiable), every Bash command is denied by fr-isolation-guard.sh, and
# every Write/Edit is denied by fr-isolation-required.sh (a fresh checkout has
# no `.fr-isolation` marker and the hook is fail-closed). The dispatch SUCCEEDS,
# so fr-goal looks healthy — which is exactly why this must be a hard deny and
# not a warning.
#
# Deliberately UNCONDITIONAL — not gated on a live pipeline sentinel, as the
# issue's checklist first suggested. fr-pipeline-sentinel.sh writes no sentinel
# when the session cwd is a linked worktree ("this IS the isolation
# workspace"), which is precisely where an fr-goal session lives after step 1;
# a sentinel-gated refusal would stay silent in the shape it exists to catch.
# The combination is never valid, so no gate is needed.
#
# Companions: fr-isolation-guard.sh (Bash), fr-isolation-required.sh
# (Edit/Write). Hermes needs no sibling — its `delegate_task(goal, context)`
# has no isolation parameter, so the poisoned shape is unrepresentable there.

set -eu

input=$(cat)

# The subagent-dispatch tool is `Agent` on current Claude Code and was `Task`
# on older builds. Accept both: a host that still spells it `Task` would
# otherwise get an inert hook and the silent poisoning this exists to stop.
# Harmless either way — the subagent_type check below is what actually narrows.
tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty')
case "$tool_name" in
  Agent | Task) ;;
  *) exit 0 ;;
esac

# Claude Code dispatches a PLUGIN subagent by its plugin-qualified id, so the
# hook normally sees `super-fr:fr-phase-executor`. A locally-installed copy of
# the agent sends the bare directory name instead — the same duality
# ensure-phase-executor-allowlist.sh documents. Refuse both spellings.
#
# fr-spec-reviewer is refused for the same #420 reason seen from a reader: it
# is dispatched to review a spec that lives on the feature branch, and a
# worktree cut from `main` does not contain it. Read-only does not help — what
# it cannot see, it cannot review — so it gets its own reason text.
subagent_type=$(printf '%s' "$input" | jq -r '.tool_input.subagent_type // empty')
case "$subagent_type" in
  super-fr:fr-phase-executor | fr-phase-executor) agent=executor ;;
  super-fr:fr-spec-reviewer | fr-spec-reviewer) agent=spec-reviewer ;;
  *) exit 0 ;;
esac

# Only `worktree` is the poisoned value. Anything else — absent, empty, or a
# value this hook does not know — is not its business: fail open on shape,
# deny only on a positive match.
isolation=$(printf '%s' "$input" | jq -r '.tool_input.isolation // empty')
[ "$isolation" = "worktree" ] || exit 0

if [ "$agent" = spec-reviewer ]; then
  jq -n --arg reason "fr-spec-reviewer must be dispatched WITHOUT \`isolation: \"worktree\"\` — it reviews the spec in fr's isolation worktree, where the feature branch's spec and spec journal live. With the flag it wakes in a separate worktree cut from \`main\`, where that spec is invisible: there is nothing for it to review, and the review it returns is of nothing. Re-dispatch the same prompt with no \`isolation\` argument. (See super-fr#420.)" \
    '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $reason}}'
  exit 0
fi

jq -n --arg reason "fr-phase-executor must be dispatched WITHOUT \`isolation: \"worktree\"\` — fr's isolation worktree already IS this agent's working copy, so the two mechanisms are mutually exclusive, not composable. With the flag the agent wakes in a separate locked worktree cut from \`main\`: the spec and plan live on the feature branch and are invisible (\`fr pickup\` has nothing to read), Bash is denied by fr-isolation-guard.sh, and Write/Edit by fr-isolation-required.sh. Re-dispatch the same prompt with no \`isolation\` argument. (The executors fr-goal §5 dispatches share this one workspace. A cross-repo agent (fr-goal §2) enters isolation in its own repo with \`fr isolation up --repo\` — the flag cannot do that, it cuts a worktree of THIS repo. See super-fr#420.)" \
  '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $reason}}'
exit 0
