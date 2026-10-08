#!/usr/bin/env bash
# Row cloud-triage-ci-evidence: a step's test evidence may be the forge's CI on the
# pushed head (`evidence: {tests: ci}`, spec 2026-10-07-cloud-triage R22). A fresh
# fixture repo with a bare `origin` and a run on a one-step workflow; a fake `gh`
# (fixtures/ci-evidence/bin/gh) answers the github-rest routes with captured stdout.
#   gate `ci-ok` not yet reported, shards running  -> exit 75, cursor byte-identical
#   HEAD committed but not pushed                  -> exit 2, naming the commit
#   HEAD pushed and the gate green                 -> exit 0, witness `ci:<head>+unknown;tree=`
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
export PATH="$here/fixtures/ci-evidence/bin:$PATH" FR_FORGE_API=rest
branch=feat/cloud-triage

world="$(mktemp -d)"
trap 'rm -rf "$world"' EXIT
export FAKE_GH_LOG="$world/gh.log"

# The working directory (a fresh `git init`) is the base clone; the run lives in a
# linked worktree beside a bare origin at ../derio-net/super-fr.git, so `origin`'s
# slug reads derio-net/super-fr and `git ls-remote origin` really answers.
git init -q --bare -b main "$world/derio-net/super-fr.git" || fail "bare origin"
echo seed > seed.md && git add -A && git commit -qm seed || fail "seed commit"
git remote add origin ../derio-net/super-fr.git
git worktree add -q -b "$branch" "$world/ws" || fail "worktree"
cd "$world/ws" || fail "cd ws"
mkdir -p src .github/workflows .fr docs/superpowers/workflows
echo "x = 1" > src/x.py
echo "on: pull_request" > .github/workflows/ci.yml
echo "gate_checks: [ci-ok]" > .fr/ci.yaml
cat > docs/superpowers/workflows/ci-evidence.yaml <<'YAML'
workflow: ci-evidence
schema: 1
unit: run
steps:
  - id: verify
    kind: agent
    evidence: [tests]
YAML
printf '{"toplevel": "%s", "branch": "%s", "mode": "worktree", "created_at": "2026-10-08T00:00:00+00:00"}\n' \
  "$PWD" "$branch" > .fr-isolation
git add -A src .github .fr docs && git commit -qm code || fail "code commit"

run_fr out run start ci-evidence --branch "$branch" --run-id r1
require_exit 0 "$out"
run_fr out run advance r1
require_exit 0 "$out"

record=docs/superpowers/runs/r1.records/verify.yaml
mkdir -p "$(dirname "$record")"
printf 'schema_version: 8\nrun: r1\nstep: verify\noutcome: done\nevidence: {tests: ci}\n' > "$record"
git add "$record" && git commit -qm "record" || fail "record commit"
git push -q origin "$branch" || fail "push"
cursor=docs/superpowers/runs/r1.yaml

# 1. CI still running: the captured mid-run head, shards in progress, no ci-ok yet.
before="$(cat "$cursor")"
FAKE_GH_MOMENT=pending run_fr out run resolve r1 --step verify --record "$record" --no-advance
require_exit 75 "$out"
flat="$(printf '%s' "$out" | tr -s '[:space:]' ' ')"
expect_grep 'resolve again when CI finishes' "$flat" "a pending gate says to resolve again"
[ "$(cat "$cursor")" = "$before" ] || fail "a pending gate moved the cursor"
[ -f "$record" ] || fail "a pending gate consumed the record"
expect_grep 'commits/[0-9a-f]{40}/check-runs\?filter=latest' "$(cat "$FAKE_GH_LOG")" "the checks were read"

# 2. A code commit not pushed: refused naming it, before any check is read.
echo "x = 2" > src/x.py && git commit -qam "code 2" || fail "code 2 commit"
head="$(git rev-parse HEAD)"
: > "$FAKE_GH_LOG"
run_fr out run resolve r1 --step verify --record "$record" --no-advance
require_exit 2 "$out"
flat="$(printf '%s' "$out" | tr -s '[:space:]' ' ')"
expect_grep "${head:0:12}" "$flat" "the refusal names the unpushed commit"
expect_grep 'not pushed' "$flat" "the refusal says it is not pushed"
[ "$(cat "$cursor")" = "$before" ] || fail "an unpushed head moved the cursor"
[ ! -s "$FAKE_GH_LOG" ] || fail "an unpushed head still asked the forge: $(cat "$FAKE_GH_LOG")"

# 3. Pushed, and the gate green: accepted, the witness recorded. The captured
#    runs list PR 1088 with ITS head, not this fixture's commit, so the base CI
#    merged with is not this commit's: the witness says `unknown` (spec §I step
#    6, p2-r3), never PR 1088's base.
git push -q origin "$branch" || fail "push 2"
FAKE_GH_MOMENT=green-head run_fr out run resolve r1 --step verify --record "$record" --no-advance
require_exit 0 "$out"
expect_grep "ci:${head}\+unknown;tree=[0-9a-f]{64}" \
  "$(cat "$cursor")" "the cursor records the ci witness"
echo "ok: cloud-triage-ci-evidence"
