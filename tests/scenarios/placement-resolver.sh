#!/usr/bin/env bash
# Row placement-resolver: one path resolver answers every artifact path (spec
# 2026-11-04-repo-feature-settings R1, R3). In a fresh repo with a local bare origin,
# `fr settings paths --shell` prints FR_PLACEMENT=repo and the plans dir below the
# toplevel, `eval` of it sets those variables, and `--json` is one JSON object with the
# same answer. Nothing reaches a forge.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
scenario_require_fresh_repo

origin="$(mktemp -d)/origin.git"
git init -q --bare -b main "$origin" || fail "bare origin"
git symbolic-ref HEAD refs/heads/main || fail "branch main"
git remote add origin "$origin"
echo seed > README.md
git add -A && git commit -qm seed || fail "seed commit"
git push -q -u origin main || fail "seed push"
git remote set-head origin main >/dev/null
top="$(git rev-parse --show-toplevel)"

run_fr out settings paths --shell
require_exit 0 "$out"
expect_grep '^FR_PLACEMENT=repo$' "$out" "the placement is repo"
expect_grep "^FR_PLANS_DIR=.*docs/superpowers/plans'?$" "$out" "the plans dir is printed"
eval "$out" || fail "the --shell output does not eval"
[ "$FR_PLACEMENT" = repo ] || fail "eval set FR_PLACEMENT=$FR_PLACEMENT"
[ "$FR_ARTIFACT_ROOT" = "$top" ] || fail "FR_ARTIFACT_ROOT=$FR_ARTIFACT_ROOT, not $top"
[ "$FR_PLANS_DIR" = "$top/docs/superpowers/plans" ] || fail "FR_PLANS_DIR=$FR_PLANS_DIR"
[ -z "$FR_FEATURE" ] || fail "FR_FEATURE=$FR_FEATURE under repo"

run_fr json settings paths --json
require_exit 0 "$json"
py="$(candidate_python)"
plans="$(printf '%s' "$json" | "$py" -c 'import json,sys; print(json.load(sys.stdin)["FR_PLANS_DIR"])')" \
  || fail "--json does not parse: $json"
[ "$plans" = "$top/docs/superpowers/plans" ] || fail "--json FR_PLANS_DIR=$plans"
echo "ok: placement-resolver"
