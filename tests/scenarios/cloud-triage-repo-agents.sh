#!/usr/bin/env bash
# Row cloud-triage-repo-agents: a repo carries fr's two dispatched agents itself, as the
# `agents` artifact kind, so a Claude Code cloud session can dispatch them from its first
# turn (spec 2026-10-07-cloud-triage R19, §H). In the fresh fixture: `fr init agents`
# writes both files stamped and commits them; `fr validate artifacts` passes; an agent
# whose stamp line is deleted fails it, naming the file; `fr migrate artifacts --yes`
# re-renders it from the installed fr and the repo validates again.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

run_fr out init agents
require_exit 0 "$out"
for name in fr-spec-reviewer fr-phase-executor; do
  f=".claude/agents/$name.md"
  [ -f "$f" ] || fail "$f was not written"
  grep -qx 'fr_artifact_version: 1' "$f" || fail "$f carries no stamp"
  grep -qx "name: $name" "$f" || fail "$f does not name $name"
  git ls-files --error-unmatch "$f" >/dev/null 2>&1 || fail "$f was not committed"
done

run_fr out validate artifacts
require_exit 0 "$out"

sed -i.bak '/^fr_artifact_version:/d' .claude/agents/fr-phase-executor.md
rm -f .claude/agents/fr-phase-executor.md.bak
git commit -qam "drop the stamp" || fail "commit the unstamped agent"
run_fr out validate artifacts
[ "$RC" -ne 0 ] || fail "validate passed an unstamped agent: $out"
expect_grep 'fr-phase-executor\.md' "$out" "the failure names the file"
expect_grep 'fr_artifact_version' "$out" "the failure names the stamp"

run_fr out migrate artifacts --yes
require_exit 0 "$out"
grep -qx 'fr_artifact_version: 1' .claude/agents/fr-phase-executor.md \
  || fail "migrate did not re-render the agent"
run_fr out validate artifacts
require_exit 0 "$out"

echo "ok: cloud-triage-repo-agents"
