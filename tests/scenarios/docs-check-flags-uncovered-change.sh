#!/usr/bin/env bash
# Row docs-check-flags-uncovered-change: `fr docs check` fails a branch that
# changed a path a page covers without touching the page, naming the page, the
# changed path and both fixes; it passes once the page body changes, and once
# only the `reviewed` stamp changes. Fresh `git init` fixture, bare local origin.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
. "$here/_docs_fixture.sh"

world="$(mktemp -d)"
trap 'rm -rf "$world"' EXIT
docs_world "$world"

printf 'x = 2\n' > src/x.py
git add -A && git_ci commit -qm "change covered file" || fail "commit"

run_fr out docs check
require_exit 1 "$out"
expect_grep 'docs/a\.md' "$out" "the stale page is named"
expect_grep 'src/x\.py' "$out" "the changed path is named"
expect_grep 'edit the page' "$out" "the first fix is printed"
expect_grep 'reviewed' "$out" "the stamp fix is printed"

# Fix one: the page body changes.
printf '%s\nMore.\n' "$PAGE_BODY" > docs/a.md
git add -A && git_ci commit -qm "edit page" || fail "commit"
run_fr out docs check
require_exit 0 "$out"

# Fix two: only the stamp changes (reset the page first, then re-stamp).
git reset -q --hard HEAD~1
sed -i.bak 's/^reviewed: .*/reviewed: 2026-11-12 still true/' docs/a.md && rm -f docs/a.md.bak
git add -A && git_ci commit -qm "restamp" || fail "commit"
run_fr out docs check
require_exit 0 "$out"
echo "ok: docs-check-flags-uncovered-change"
