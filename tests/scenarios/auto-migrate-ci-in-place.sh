#!/usr/bin/env bash
# Row auto-migrate-ci-in-place (spec 2026-11-01-auto-migrate-own-commit §F, R5
# R10): in CI, on the default branch, a stale plan no longer turns `fr
# acceptance check` red. The gate migrates the working tree in place, never
# commits, and warns on STDERR (plus a `::warning::` annotation under GitHub
# Actions); stdout carries neither. The fixture is a fresh `git init` on `main`
# with a minimal current-schema matrix and its committed reports — no forge.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
# Every context marker goes, then this scenario sets exactly what it tests.
unset CI GITHUB_ACTIONS GITLAB_CI BUILDKITE JENKINS_URL TF_BUILD TEAMCITY_VERSION CIRCLECI
unset FR_NON_INTERACTIVE FR_SKIP_MIGRATION

world="$(mktemp -d)"
trap 'rm -rf "$world"' EXIT
plan=2026-11-01-widget
meta="docs/superpowers/plans/$plan/_meta.yaml"

git init -q -b main . 2>/dev/null || fail "git init"
git symbolic-ref HEAD refs/heads/main || fail "HEAD to main"
git config commit.gpgsign false
mkdir -p docs/acceptance
cat > docs/acceptance/matrix.yaml <<'YAML'
schema_version: 5
org: example-org
repo: widgets
rows: []
YAML
# The reports are generated while nothing is stale, as a real repo's would be.
run_fr out acceptance report --deterministic
require_exit 0 "$out"
mkdir -p "docs/superpowers/plans/$plan"
cat > "$meta" <<YAML
schema_version: 2
plan: $plan
target_repo: example-org/widgets
created: '2026-11-01'
fr_version: '>=3.0.0,<4.0.0'
YAML
printf '# Widget plan\n' > "docs/superpowers/plans/$plan/_prose.md"
git add -A && git commit -qm seed || fail "seed commit"
head="$(git rev-parse HEAD)"

export CI=true GITHUB_ACTIONS=true
fr acceptance check </dev/null >"$world/out" 2>"$world/err"; RC=$?
out="$(cat "$world/out")"
err="$(cat "$world/err")"
require_exit 0 "$out $err"
[ "$(git rev-parse HEAD)" = "$head" ] || fail "CI committed: $(git log -1 --format=%s)"
refuse_grep '<4\.0\.0' "$(cat "$meta")" "the plan is migrated in the working tree"
expect_grep 'migrated in place for this run \(NOT committed\)' "$err" "stderr carries the warning"
expect_grep 'Do not commit these files with other work' "$err" "and the ride-along caveat"
expect_grep '^::warning title=fr artifacts stale::1 artifact\(s\) migrated in place' "$err" \
  "stderr carries the annotation"
refuse_grep 'NOT committed|::warning' "$out" "stdout carries neither"
echo "ok: auto-migrate-ci-in-place"
