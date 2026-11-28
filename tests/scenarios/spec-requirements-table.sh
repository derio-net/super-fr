#!/usr/bin/env bash
# Row spec-requirements-table-migrate: the INSTALLED fr's `fr migrate artifacts --yes`
# rewrites a live spec's `R<n>.` list (with a wrapped requirement and a literal `|`)
# into the `| ID | Requirement |` table and stamps it `fr_schema: 2`; the installed
# `fr.requirements` reads the table to the same ids and joined text as the list, and
# `fr validate artifacts` passes on it (spec 2026-11-26-spec-requirements-table R4, R5).
# The fixture is a fresh `git init` with a local bare origin.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
scenario_require_fresh_repo

world="$(mktemp -d)"
trap 'rm -rf "$world"' EXIT
origin="$world/origin.git"
git init -q --bare -b main "$origin" || fail "bare origin"
git symbolic-ref HEAD refs/heads/main || fail "branch main"
git remote add origin "$origin"
git commit -q --allow-empty -m seed || fail "seed commit"
git push -q -u origin main || fail "seed push"
git remote set-head origin main >/dev/null
git checkout -q -b feat/widget || fail "feature branch"

mkdir -p docs/superpowers/plans docs/superpowers/specs
touch docs/superpowers/plans/.keep
spec=docs/superpowers/specs/2026-01-01-widget-design.md
cat > "$spec" <<'SPEC'
# Widget

## Requirements

R1. The widget counts every turn
and reports the total.
R2. The mode is `on | off`.

## Design

Prose.
SPEC
git add -A && git commit -qm "widget spec" || fail "spec commit"

py="$(candidate_python)"
read_reqs() {
  "$py" -P -c 'import sys
from fr.requirements import parse_requirements
for r in parse_requirements(open(sys.argv[1], encoding="utf-8").read()).items:
    print(f"{r.id}\t{r.text}")' "$spec"
}
before="$(read_reqs)" || fail "read the list spec"
expect_grep '^R1	The widget counts every turn and reports the total\.$' "$before" \
  "the installed reader joins the continuation line"

run_fr out migrate artifacts --yes
require_exit 0 "$out"

body="$(cat "$spec")"
expect_grep '^fr_schema: 2$' "$body" "the spec is stamped 2"
expect_grep '^\| ID \| Requirement \|$' "$body" "the list became the table"
expect_grep '^\| R2 \| The mode is `on \\\| off`\. \|$' "$body" "a literal | is escaped"
refuse_grep '^R[0-9]+\. ' "$body" "no list line is left"
after="$(read_reqs)" || fail "read the table spec"
[ "$after" = "$before" ] || fail "the table reads to other requirements: $after"

run_fr out validate artifacts
require_exit 0 "$out"
echo "ok: spec-requirements-table"
