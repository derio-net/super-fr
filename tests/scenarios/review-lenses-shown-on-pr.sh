#!/usr/bin/env bash
# Row review-lenses-shown-on-pr: the PR body fr renders for a run whose lens set holds a
# rule lens (`security`, required by a path rule the feature's diff matches) and an agent
# lens (`tests`, added with a reason) carries a `## Review lenses` table after the findings
# sections: each lens with why it is there, the files its reviewer examined and its
# findings with their folded states. A run whose set is empty renders the single line
# "No lens was requested for this change." instead.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
. "$here/_lens_fixture.sh"
start="$PWD"
root="$(mktemp -d)"
trap 'rm -rf "$root"' EXIT
export HOME="$root/home" && mkdir -p "$HOME"
commit_docs() {
  git add -A docs
  git diff --cached --quiet || git_ci commit -qm "$1" || fail "commit $1"
}
render_body() {
  "$(candidate_python)" -c '
from pathlib import Path
from fr.record.pr_body import render_pr_body
from fr.run.model import load_run_state
root = Path(".")
print(render_pr_body(root, load_run_state(root, "r1")))' || fail "cannot render the PR body"
}

# --- an empty set ----------------------------------------------------------------
world="$root/empty" && mkdir -p "$world"
lens_review_world "$world"
run_fr out run advance r1
require_exit 0 "$out"
run_fr out run resolve r1 --step lens-review --state done
require_exit 0 "$out"
body="$(render_body)"
expect_grep '^## Review lenses$' "$body" "the section is rendered"
expect_grep '^No lens was requested for this change\.$' "$body" "an empty set says so"

# --- a rule lens and an agent lens -----------------------------------------------
world="$root/two"
mkdir -p "$world/base" && cd "$world/base" && git init -q || fail "second world"
lens_review_world "$world" $'require:\n  - paths: [\'src/auth/**\']\n    lenses: [security]\n'
add=(journal add --scope plan --slug "$LENS_PLAN" --global)
run_fr out "${add[@]}" --kind lens --lens tests --title "only the happy path"
require_exit 0 "$out"
commit_docs lens
run_fr out run advance r1
require_exit 0 "$out"
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
lens_session "ses_gen1=$world/sec.txt" "ses_gen2=$world/tests.txt"
run_fr out run resolve r1 --step lens-review --state done --evidence review=lens-rev \
  --evidence reviewer=security=ses_gen1,tests=ses_gen2
require_exit 0 "$out"
body="$(render_body)"
expect_grep '^## Review lenses$' "$body" "the section is rendered"
expect_grep '^| Lens | Why | Files examined | Findings |$' "$body" "the table has its header"
expect_grep '^| security | rule `src/auth/\*\*` (src/auth/token.py) | 2 | l-security-r1 fixed |$' "$body" \
  "the rule lens shows its rule, file, count and folded finding state"
expect_grep '^| tests | command line: "only the happy path" | 1 | none |$' "$body" \
  "the agent lens shows its reason and no step"
findings_at="$(printf '%s\n' "$body" | grep -n '^## Out-of-scope findings$' | cut -d: -f1)"
lenses_at="$(printf '%s\n' "$body" | grep -n '^## Review lenses$' | cut -d: -f1)"
[ "$findings_at" -lt "$lenses_at" ] || fail "the section does not follow the findings sections"
cd "$start" || true
echo "ok: review-lenses-shown-on-pr"
