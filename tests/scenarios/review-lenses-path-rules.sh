#!/usr/bin/env bash
# Row review-lenses-path-rules: the default branch holds a rule requiring `security` for
# `src/auth/**`; a branch that changes `src/auth/x.py` with no agent addition shows
# `security` in `fr lenses status` with the rule and the file; a branch that deletes the
# rule from its `.fr/lenses.yaml` still shows it; `fr lenses check` exits 1 on a branch
# config that disables `security`; and at `lens-review`, a feature that changes a ruled
# path owes that lens: the resolve refuses while it has no reviewer, naming the rule and
# the matching file.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
. "$here/_lens_fixture.sh"
world="$(mktemp -d)"
top="$world"
trap 'rm -rf "$top"' EXIT
lens_world "$world" "require:
  - paths: ['src/auth/**']
    lenses: [security]
"

run_fr out lenses status
require_exit 0 "$out"
expect_grep '^no lens requested$' "$out" "nothing changed yet, nothing required"

mkdir -p src/auth && printf 'x = 1\n' > src/auth/x.py
git add -A src && git_ci commit -qm auth || fail "auth commit"
run_fr out lenses status
require_exit 0 "$out"
expect_grep '^security: rule src/auth/\*\* matches src/auth/x.py$' "$out" \
  "the rule and the matching file are shown"

printf 'disable: []\n' > .fr/lenses.yaml
git add -A .fr && git_ci commit -qm "drop the rule" || fail "drop commit"
run_fr out lenses status
require_exit 0 "$out"
expect_grep '^security: rule src/auth/\*\* matches src/auth/x.py$' "$out" \
  "a rule the base holds stays in force"
run_fr out lenses check
require_exit 0 "$out"

printf 'disable: [security]\n' > .fr/lenses.yaml
git add -A .fr && git_ci commit -qm "disable security" || fail "disable commit"
run_fr out lenses check
require_exit 1 "$out"
expect_grep 'disables security' "$out" "disabling a required lens is refused"

# --- the lens review owes the rule's lens ------------------------------------------
start="$PWD"
world="$world/review" && mkdir -p "$world"
mkdir -p "$world/base" && cd "$world/base" && git init -q || fail "review world"
lens_review_world "$world" "require:
  - paths: ['src/auth/**']
    lenses: [security]
"
run_fr out run advance r1
require_exit 0 "$out"
expect_grep '"file": "src/auth/token.py"' "$out" "the brief names the matching file"
run_fr out journal add --scope plan --slug "$LENS_PLAN" --global --kind review --id lens-rev \
  --title "lens review"
require_exit 0 "$out"
cursor="$(cat docs/superpowers/runs/r1.yaml)"
run_fr out run resolve r1 --step lens-review --state done --evidence review=lens-rev \
  --evidence reviewer=tests=ses_gen2
require_exit 2 "$out"
expect_grep 'lens security has no reviewer named for it' "$out" "the rule lens is owed a reviewer"
expect_grep 'path rule src/auth/\*\* \(matches src/auth/token.py\)' "$out" \
  "the refusal names the rule and the file"
[ "$(cat docs/superpowers/runs/r1.yaml)" = "$cursor" ] || fail "a refused resolve moved the cursor"
cd "$start" || fail "back"
echo "ok: review-lenses-path-rules"
