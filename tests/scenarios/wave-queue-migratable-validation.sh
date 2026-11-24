#!/usr/bin/env bash
# Row wave-queue-migratable-validation: `fr validate artifacts --allow-migratable` (spec
# 2026-11-19-wave-merge-queue R21). A live artifact stamped for an older version that a
# registered migration moves fails the strict check, and passes with the flag, which lists it
# as `stale, migratable` and writes nothing (the migration is tried on a scratch copy). The
# flag still fails an artifact whose migration refuses it, one no migration reaches, and one
# newer than this fr. The fixture is a fresh `git init` of journals (a v3 journal moves to v4)
# and a v1 plan (no migration reaches it); no forge.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

git init -q -b main . || fail "git init"
journals=docs/superpowers/journals/plans
mkdir -p "$journals"
body='# Journal: p

<!-- fr:journal kind=discovery scope=plan id=d1 created=2026-01-01T00:00:00 -->
### d1 · discovery · t

body
'
printf '<!-- fr:journal-schema=3 -->\n%s' "$body" > "$journals/stale.md"
before="$(cksum < "$journals/stale.md")"

run_fr out validate artifacts --kind journal
require_exit 1 "$out"
expect_grep 'stale: written for journal artifact version 3' "$out" "the strict check fails a stale stamp"
expect_grep 'fr migrate artifacts --yes' "$out" "and names the migration"

run_fr out validate artifacts --kind journal --allow-migratable
require_exit 0 "$out"
expect_grep 'stale, migratable' "$out" "the flag lists the movable stamp"
[ "$(cksum < "$journals/stale.md")" = "$before" ] || fail "the check wrote the checkout"

# a migration that refuses the file: a v3 journal already holding a lens entry
printf '<!-- fr:journal-schema=3 -->\n# Journal: q\n\n<!-- fr:journal kind=lens scope=plan id=lens-security-1 created=2026-01-01T00:00:00 lens=security step=implement-phase -->\n### lens-security-1 · lens · why\n' > "$journals/refused.md"
run_fr out validate artifacts --kind journal --allow-migratable
require_exit 1 "$out"
expect_grep 'refused\.md: stale and its migration refuses it' "$out" "a refusing migration still fails"
refuse_grep 'stale\.md: stale and' "$out" "and does not fail the movable one"
rm "$journals/refused.md"

# a stamp newer than this fr
printf '<!-- fr:journal-schema=99 -->\n%s' "$body" > "$journals/future.md"
run_fr out validate artifacts --kind journal --allow-migratable
require_exit 1 "$out"
expect_grep 'future\.md: written for journal artifact version 99' "$out" "a newer stamp still fails"
rm "$journals/future.md"

# an older plan stamp that no registered migration reaches
mkdir -p docs/superpowers/plans/p
printf 'schema_version: 1\nplan: p\ntarget_repo: example-org/demo\n' > docs/superpowers/plans/p/_meta.yaml
run_fr out validate artifacts --kind plan --allow-migratable
require_exit 1 "$out"
expect_grep 'no registered migration reaches' "$out" "an unreachable stamp still fails"
echo "ok: wave-queue-migratable-validation"
