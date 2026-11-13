#!/usr/bin/env bash
# Row review-lenses-reviewer-return-checked: a run at `lens-review` with the lenses
# `security` and `tests` and an OpenCode session whose two `general` children are the
# reviewers (the committed store, moved into the step's window, returns rewritten).
# Complete returns resolve and record `lenses`; a lens with no reviewer, a return naming
# a file the feature did not change, and a reviewer id this session never dispatched
# each exit 2 with the cursor unchanged. A run whose set is empty resolves with no
# reviewer and `lenses=none`.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
. "$here/_lens_fixture.sh"
start="$PWD"
root="$(mktemp -d)"
trap 'rm -rf "$root"' EXIT
export HOME="$root/home" && mkdir -p "$HOME"
world="$root/one" && mkdir -p "$world"
# fr commits its own journal writes; commit whatever it left.
commit_docs() {
  git add -A docs
  git diff --cached --quiet || git_ci commit -qm "$1" || fail "commit $1"
}

# --- an empty set ----------------------------------------------------------------
lens_review_world "$world"
run_fr out run advance r1
require_exit 0 "$out"
expect_grep '"lens_review": \{"note": "no lens is in this feature' "$out" "the brief says the set is empty"
run_fr out run resolve r1 --step lens-review --state done
require_exit 0 "$out"
run_fr out run status r1
expect_grep 'lenses=none' "$out" "an empty set records lenses=none"

# --- two lenses ------------------------------------------------------------------
world="$root/two"
mkdir -p "$world/base" && cd "$world/base" && git init -q || fail "second world"
lens_review_world "$world"
add=(journal add --scope plan --slug "$LENS_PLAN" --global)
run_fr out "${add[@]}" --kind lens --lens security --title "the token is parsed here"
require_exit 0 "$out"
run_fr out "${add[@]}" --kind lens --lens tests --title "only the happy path"
require_exit 0 "$out"
commit_docs lenses
run_fr out run advance r1
require_exit 0 "$out"
expect_grep '"lens": "security"' "$out" "the brief lists security"
expect_grep '"lens": "tests"' "$out" "the brief lists tests"

run_fr out "${add[@]}" --kind review --id lens-rev --title "lens review"
require_exit 0 "$out"
run_fr out "${add[@]}" --kind finding --id l-security-r1 --state open --review-scope in \
  --title "a shell string"
require_exit 0 "$out"
run_fr out journal resolve --scope plan --slug "$LENS_PLAN" --id l-security-r1 --state fixed \
  --note "quoted, with a test"
require_exit 0 "$out"
commit_docs review

lens_return "$world/sec.txt" security "src/app.py, src/auth/token.py" "l-security-r1 | in | a shell string"
lens_return "$world/tests.txt" tests "src/app.py"
lens_return "$world/outside.txt" tests "seed.md"
cursor="docs/superpowers/runs/r1.yaml"
resolve=(run resolve r1 --step lens-review --state done --evidence review=lens-rev)

lens_session "ses_gen1=$world/sec.txt" "ses_gen2=$world/tests.txt"
before="$(cat "$cursor")"
run_fr out "${resolve[@]}" --evidence reviewer=security=ses_gen1
require_exit 2 "$out"
expect_grep 'lens tests has no reviewer named for it' "$out" "a lens with no reviewer is refused"
expect_grep 'l-tests-r<k>' "$out" "the refusal carries the lens's return rule"
[ "$(cat "$cursor")" = "$before" ] || fail "a refused resolve moved the cursor"

run_fr out "${resolve[@]}" --evidence reviewer=security=ses_gen1,tests=ses_nope
require_exit 2 "$out"
expect_grep 'ses_nope names no subagent' "$out" "an undispatched reviewer is refused"
[ "$(cat "$cursor")" = "$before" ] || fail "a refused resolve moved the cursor"

lens_session "ses_gen1=$world/sec.txt" "ses_gen2=$world/outside.txt"
run_fr out "${resolve[@]}" --evidence reviewer=security=ses_gen1,tests=ses_gen2
require_exit 2 "$out"
expect_grep 'examined seed.md, which the feature did not change' "$out" \
  "a file outside the diff is refused"
[ "$(cat "$cursor")" = "$before" ] || fail "a refused resolve moved the cursor"

lens_session "ses_gen1=$world/sec.txt" "ses_gen2=$world/tests.txt"
run_fr out "${resolve[@]}" --evidence reviewer=security=ses_gen1,tests=ses_gen2
require_exit 0 "$out"
run_fr out run status r1
expect_grep 'lenses=security=2:l-security-r1;tests=1:none' "$out" "the witness names files and findings"
cd "$start" || true
echo "ok: review-lenses-reviewer-return-checked"
