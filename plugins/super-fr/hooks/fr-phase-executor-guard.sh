#!/bin/bash
# PreToolUse(Agent) hook: refuse dispatching the fr-phase-executor subagent
# WITH `isolation: "worktree"`. fr's isolation worktree already IS the
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
subagent_type=$(printf '%s' "$input" | jq -r '.tool_input.subagent_type // empty')
case "$subagent_type" in
  super-fr:fr-phase-executor | fr-phase-executor) ;;
  *) exit 0 ;;
esac

# Only `worktree` is the poisoned value. Anything else — absent, empty, or a
# value this hook does not know — is not its business: fail open on shape,
# deny only on a positive match.
isolation=$(printf '%s' "$input" | jq -r '.tool_input.isolation // empty')
[ "$isolation" = "worktree" ] || exit 0

jq -n --arg reason "fr-phase-executor must be dispatched WITHOUT \`isolation: \"worktree\"\` — fr's isolation worktree already IS this agent's working copy, so the two mechanisms are mutually exclusive, not composable. With the flag the agent wakes in a separate locked worktree cut from \`main\`: the spec and plan live on the feature branch and are invisible (\`fr pickup\` has nothing to read), Bash is denied by fr-isolation-guard.sh, and Write/Edit by fr-isolation-required.sh. Re-dispatch the same prompt with no \`isolation\` argument. (fr-goal §3 DOES pass the flag, correctly — those agents each start a fresh pipeline in a different repo; §6's phase executors share this one. See super-fr#420.)" \
  '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $reason}}'
exit 0
