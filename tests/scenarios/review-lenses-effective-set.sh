#!/usr/bin/env bash
# Row review-lenses-effective-set: a repo with no `.fr/lenses.yaml` has the four shipped
# lenses; a config that disables one, replaces one and adds one changes `list`, `show` and
# `check` accordingly; a broken config fails `check`; nothing is ever written.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

git_ci() { git -c user.name=scenario -c user.email=scenario@example.org "$@"; }
git symbolic-ref HEAD refs/heads/main || fail "HEAD to main"
printf 'x\n' > README.md
git add -A && git_ci commit -qm base || fail "base commit"
clean() { [ -z "$(git status --porcelain)" ] || fail "fr lenses wrote something: $(git status --porcelain)"; }

run_fr out lenses list
require_exit 0 "$out"
for id in security tests simplicity errors; do
  expect_grep "^$id " "$out" "shipped lens $id is listed"
done
expect_grep 'security .*\[shipped\]' "$out" "the source is shown"
clean
run_fr out lenses check
require_exit 0 "$out"

mkdir -p .fr
cat > .fr/lenses.yaml <<'Y'
disable: [errors]
lenses:
  security:
    title: Security (house)
    brief: |
      House security text.
  accessibility:
    title: Accessibility
    brief: |
      Look for missing labels.
Y
git add -A && git_ci commit -qm cfg || fail "config commit"

run_fr out lenses list
require_exit 0 "$out"
refuse_grep '^errors ' "$out" "the disabled lens is gone"
expect_grep 'security .*Security \(house\) .*\[repo \(replaces shipped\)\]' "$out" "replaced"
expect_grep 'accessibility .*\[repo\]' "$out" "added"
expect_grep '^tests .*\[shipped\]' "$out" "the rest stay shipped"
run_fr out lenses show security
require_exit 0 "$out"
expect_grep 'House security text' "$out" "show prints the replacement text"
run_fr out lenses show errors
require_exit 2 "$out"
expect_grep 'accessibility' "$out" "show names the effective ids"
run_fr out lenses check
require_exit 0 "$out"
clean

printf 'disable: [nope]\nbogus: 1\n' > .fr/lenses.yaml
git add -A && git_ci commit -qm broken || fail "broken commit"
run_fr out lenses check
require_exit 1 "$out"
expect_grep 'bogus' "$out" "the unknown key is named"
clean
echo "ok: review-lenses-effective-set"
