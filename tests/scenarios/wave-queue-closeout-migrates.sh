#!/usr/bin/env bash
# Row wave-queue-closeout-migrates: `fr migrate artifacts --yes --path <file>` (spec
# 2026-11-19-wave-merge-queue R16), the migration a wave's close-out runs over exactly the
# artifacts it archives. It migrates only the named file and leaves a second stale file as it
# was, refuses a file that is no live artifact, and refuses a migration that retires a kind
# (it is not per file) before it writes anything. The fixture is a fresh `git init` of two stale
# journals and a stale matrix (whose hop retires it); no forge.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

git init -q -b main . || fail "git init"
journals=docs/superpowers/journals/plans
mkdir -p "$journals" docs/acceptance
entry='# Journal: p

<!-- fr:journal kind=discovery scope=plan id=d1 created=2026-01-01T00:00:00 -->
### d1 · discovery · t

body
'
printf '<!-- fr:journal-schema=3 -->\n%s' "$entry" > "$journals/one.md"
printf '<!-- fr:journal-schema=3 -->\n%s' "$entry" > "$journals/two.md"
two_before="$(cksum < "$journals/two.md")"

run_fr out migrate artifacts --yes --path "$journals/one.md"
require_exit 0 "$out"
expect_grep 'migrated: .*one\.md' "$out" "the named file is migrated"
refuse_grep 'two\.md' "$out" "the second is not named"
expect_grep '^<!-- fr:journal-schema=4 -->' "$(head -1 "$journals/one.md")" "its stamp moved to 4"
[ "$(cksum < "$journals/two.md")" = "$two_before" ] || fail "the second stale file was touched"
refuse_grep 'in-flight plan' "$out" "a per-file run offers no adoption"

# a file that is no live artifact is refused, nothing written
printf 'x\n' > notes.txt
run_fr out migrate artifacts --yes --path notes.txt
require_exit 2 "$out"
expect_grep 'not a live artifact' "$out" "a stray file is refused"
[ "$(cksum < "$journals/two.md")" = "$two_before" ] || fail "a refusal wrote the checkout"

# a retiring hop is not per file: refused before any byte moves
printf 'schema_version: 5\norg: example-org\nrepo: demo\nrows: []\n' > docs/acceptance/matrix.yaml
matrix_before="$(cksum < docs/acceptance/matrix.yaml)"
run_fr out migrate artifacts --yes --path docs/acceptance/matrix.yaml --path "$journals/two.md"
require_exit 2 "$out"
expect_grep 'not per file' "$out" "a retiring migration is refused"
[ "$(cksum < docs/acceptance/matrix.yaml)" = "$matrix_before" ] || fail "the matrix was touched"
[ "$(cksum < "$journals/two.md")" = "$two_before" ] || fail "the retiring refusal left a partial run"
echo "ok: wave-queue-closeout-migrates"
