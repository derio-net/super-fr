#!/usr/bin/env bash
# Row auto-migrate-workspace-commits-alone (spec 2026-11-01-auto-migrate-own-commit
# §F, R1 R3 R7 R8): in a valid fr-isolation workspace, with no TTY, the first
# gated fr command migrates a stale plan and commits that migration ALONE, on
# top of the branch's work commit, widening the plan's fr_version ceiling. The
# same command in the primary checkout, on a branch with no marker, refuses with
# the `carry it:` line and leaves the tree as it was. The fixture is a fresh
# `git init` with a bare local origin (`main` its default) and a linked worktree
# carrying a hand-written marker — no forge, no network.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
# _common.sh exports CI=true and FR_SKIP_MIGRATION=1; this scenario is about
# the gate in a NON-CI context, so every context marker goes.
unset CI GITHUB_ACTIONS GITLAB_CI BUILDKITE JENKINS_URL TF_BUILD TEAMCITY_VERSION CIRCLECI
unset FR_NON_INTERACTIVE FR_SKIP_MIGRATION

world="$(mktemp -d)"
trap 'rm -rf "$world"' EXIT
plan=2026-11-01-widget
meta="docs/superpowers/plans/$plan/_meta.yaml"

git init -q -b main . 2>/dev/null || fail "git init"
git symbolic-ref HEAD refs/heads/main || fail "HEAD to main"
git config commit.gpgsign false
printf '.fr-isolation\n' >> .git/info/exclude
git init -q --bare -b main "$world/origin.git" || fail "bare origin"
git remote add origin "$world/origin.git"
mkdir -p "docs/superpowers/plans/$plan"
cat > "$meta" <<YAML
schema_version: 2
plan: $plan
target_repo: example-org/widgets
created: '2026-11-01'
fr_version: '>=3.0.0,<4.0.0'
YAML
printf '# Widget plan\n' > "docs/superpowers/plans/$plan/_prose.md"
cat > "docs/superpowers/plans/$plan/01.yaml" <<'YAML'
schema_version: 2
phase:
  number: 1
  title: Build it
  tag: agentic
  depends_on: []
  tier: mechanical
  tracking_issue: null
tasks:
  - number: 1
    title: Build
    steps:
      - id: P1.T1.S1
        text: Build the widget
state:
  steps:
    P1.T1.S1:
      state: ' '
      ticked_at: null
      note: null
  completion:
    at: null
    note: null
    observed_prs: []
YAML
git add -A && git commit -qm seed || fail "seed commit"
git push -q origin main || fail "push"
git remote set-head origin main || fail "set-head"
primary="$(pwd -P)"

# The workspace: a linked worktree on feat/x, a valid marker, one work commit.
git worktree add -q -b feat/x "$world/wt" || fail "worktree add"
wt="$(cd "$world/wt" && pwd -P)"
printf '{"toplevel": "%s", "branch": "feat/x", "mode": "worktree"}\n' "$wt" > "$wt/.fr-isolation"
printf 'work\n' > "$wt/work.md"
git -C "$wt" add work.md && git -C "$wt" commit -qm "work commit" || fail "work commit"
work_sha="$(git -C "$wt" rev-parse HEAD)"

# 1. In the workspace, no TTY: migrate, commit alone, run the command.
cd "$wt" || fail "cd worktree"
out="$(fr plan self-review "docs/superpowers/plans/$plan" </dev/null 2>&1)"; RC=$?
require_exit 0 "$out"
expect_grep '^fr: migrated and committed 1 artifact\(s\): chore\(fr\): migrate' "$out" \
  "the gate names the commit it made"
subject="$(git log -1 --format=%s)"
expect_grep '^chore\(fr\): migrate ' "$subject" "HEAD is fr's migration commit"
[ "$(git rev-parse HEAD~1)" = "$work_sha" ] || fail "the migration is not on top of the work commit"
touched="$(git show --name-only --format= HEAD)"
[ "$touched" = "$meta" ] || fail "the migration commit touched more than the plan: $touched"
refuse_grep '<4\.0\.0' "$(cat "$meta")" "the ceiling is widened"
[ -z "$(git status --porcelain)" ] || fail "the workspace is left dirty: $(git status --porcelain)"

# 2. The primary checkout, on a branch with no marker: refuse, write nothing.
cd "$primary" || fail "cd primary"
git checkout -q -b feat/y || fail "branch in primary"
head="$(git rev-parse HEAD)"
before="$(cat "$meta")"
out="$(fr plan self-review "docs/superpowers/plans/$plan" </dev/null 2>&1)"; RC=$?
require_exit 2 "$out"
flat="$(printf '%s' "$out" | tr -s '[:space:]' ' ')"
expect_grep 'carry it: fr isolation up --branch' "$flat" "the refusal names the way to carry it"
expect_grep 'not an fr-isolation workspace \(no \.fr-isolation marker' "$flat" "and why"
[ "$(git rev-parse HEAD)" = "$head" ] || fail "the primary checkout gained a commit"
[ "$(cat "$meta")" = "$before" ] || fail "the primary checkout's plan was rewritten"
[ -z "$(git status --porcelain)" ] || fail "the primary checkout is dirty"
echo "ok: auto-migrate-workspace"
