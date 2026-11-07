#!/usr/bin/env bash
# Row repo-settings-git-policy: under `git: {history: squash-unpushed, push: auto}` and
# custom commit templates, two code commits and `fr push` leave ONE commit on origin's
# branch, with the templated subject and the same tree; a commit whose subject does not
# match the template is refused by name, and nothing is pushed. The fixture is a fresh
# `git init` with a local bare origin; nothing reaches a forge.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

origin="$(mktemp -d)/origin.git"
git init -q --bare -b main "$origin" || fail "bare origin"
git symbolic-ref HEAD refs/heads/main || fail "branch main"
git remote add origin "$origin"
echo seed > README.md
mkdir -p .fr
cat > .fr/settings.yaml <<'YAML'
git:
  push: auto
  history: squash-unpushed
  commit:
    with_issue: "[{scope}] {summary} #{issue}"
    without_issue: "[{scope}] {summary}"
YAML
git add -A && git commit -qm seed || fail "seed commit"
git push -q -u origin main || fail "seed push"
git remote set-head origin main >/dev/null

git switch -q -c feat/x || fail "feature branch"
echo a > a.txt && git add -A && git commit -qm "[api] add a" || fail "commit a"
echo b > b.txt && git add -A && git commit -qm "[api] add b" || fail "commit b"
tree="$(git rev-parse 'HEAD^{tree}')"

run_fr out push
require_exit 0 "$out"
count="$(git --git-dir="$origin" rev-list --count main..feat/x)"
[ "$count" = 1 ] || fail "origin's branch has $count commits, expected 1 squashed commit"
subject="$(git --git-dir="$origin" log -1 --format=%s feat/x)"
[ "$subject" = "[api] add a" ] || fail "squashed subject is '$subject', not the templated '[api] add a'"
[ "$(git --git-dir="$origin" rev-parse 'feat/x^{tree}')" = "$tree" ] || fail "the squash changed the tree"
[ "$(git rev-parse HEAD)" = "$(git --git-dir="$origin" rev-parse feat/x)" ] || fail "local and origin differ"

echo c > c.txt && git add -A && git commit -qm "wip" || fail "commit wip"
before="$(git --git-dir="$origin" rev-parse feat/x)"
run_fr out push
require_exit 2 "$out"
expect_grep 'wip' "$out" "the refusal names the commit whose subject does not match"
expect_grep 'commit template' "$out" "the refusal names the template"
[ "$(git --git-dir="$origin" rev-parse feat/x)" = "$before" ] || fail "a refused push moved origin"
echo "ok: repo-settings-git-policy"
