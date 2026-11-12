#!/usr/bin/env bash
# Row repo-settings-policy-off: a repo whose origin main carries
# `artifacts: {acceptance: off, test_plan: off, gates: off}` refuses `fr acceptance add`
# naming the setting, `fr acceptance status` says it is disabled, and `fr validate
# artifacts` refuses a spec carrying a `## Test Plan`. The fixture is a fresh `git init`
# with a local bare origin.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

origin="$(mktemp -d)/origin.git"
git init -q --bare -b main "$origin" || fail "bare origin"
git symbolic-ref HEAD refs/heads/main || fail "branch main"
git remote add origin "$origin"
echo seed > README.md
mkdir -p .fr docs/superpowers/specs
printf 'artifacts:\n  acceptance: off\n  test_plan: off\n  gates: off\n' > .fr/settings.yaml
git add -A && git commit -qm "seed with settings" || fail "seed commit"
git push -q -u origin main || fail "seed push"
git remote set-head origin main >/dev/null

run_fr out acceptance add --id a --capability c --acceptance "x" --status not-implemented
require_exit 2 "$out"
expect_grep 'disabled by repo setting' "$out" "add names the setting"
expect_grep 'artifacts\.acceptance' "$out" "add names the key"

run_fr out acceptance status
require_exit 0 "$out"
expect_grep 'disabled by repo setting' "$out" "status says acceptance is disabled"

git checkout -qb feat/plan
printf '# S\n\n## Test Plan\n\n1. do it\n' > docs/superpowers/specs/2026-11-07-x-design.md
run_fr out validate artifacts
require_exit 1 "$out"
expect_grep 'disabled by repo setting' "$out" "validate refuses the Test Plan"
expect_grep 'test_plan' "$out" "validate names the key"
echo "ok: repo-settings-policy-off"
