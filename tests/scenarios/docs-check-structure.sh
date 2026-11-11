#!/usr/bin/env bash
# Row docs-check-structure: a dead `covers` glob, a page with no `reviewed`
# stamp and a `must_cover` file no page covers each fail by name; a repo with
# no `.fr/docs.yaml` passes; `fr docs status` lists the pages (and `--json`).
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
. "$here/_docs_fixture.sh"

world="$(mktemp -d)"
trap 'rm -rf "$world"' EXIT
docs_world "$world"

run_fr out docs check
require_exit 0 "$out"

run_fr out docs status
require_exit 0 "$out"
expect_grep 'docs/a\.md' "$out" "status lists the page"
expect_grep 'src/\*\.py' "$out" "status lists what it covers"
expect_grep '2026-11-11 first' "$out" "status lists the stamp"
run_fr out docs status --json
require_exit 0 "$out"
expect_grep '"reviewed": "2026-11-11 first"' "$out" "status --json carries the stamp"

# A dead glob.
printf '%s' "$PAGE_BODY" | sed 's#- src/\*\.py#- src/*.py\n  - gone/**#' > docs/a.md
run_fr out docs check
require_exit 1 "$out"
expect_grep 'dead-glob' "$out" "a dead glob is flagged"
expect_grep 'gone/\*\*' "$out" "the dead glob is named"
printf '%s' "$PAGE_BODY" > docs/a.md

# A missing stamp.
printf '%s' "$PAGE_BODY" | grep -v '^reviewed:' > docs/a.md
run_fr out docs check
require_exit 1 "$out"
expect_grep 'bad-page' "$out" "a missing stamp is flagged"
expect_grep 'docs/a\.md' "$out" "the page is named"
expect_grep 'reviewed' "$out" "the missing key is named"
printf '%s' "$PAGE_BODY" > docs/a.md

# An uncovered must_cover file.
printf 'pages:\n  - docs/*.md\nmust_cover:\n  - lib/*.py\n' > .fr/docs.yaml
mkdir -p lib && printf 'y = 1\n' > lib/y.py
git add -A && git_ci commit -qm "lib" || fail "commit"
run_fr out docs check
require_exit 1 "$out"
expect_grep 'uncovered' "$out" "an uncovered file is flagged"
expect_grep 'lib/y\.py' "$out" "the uncovered file is named"

# No config at all.
git rm -q -f .fr/docs.yaml
run_fr out docs check
require_exit 0 "$out"
expect_grep 'nothing to check' "$out" "no config is nothing to check"
echo "ok: docs-check-structure"
