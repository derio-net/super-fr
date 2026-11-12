#!/usr/bin/env bash
# Row acceptance-effective-matrix-fold: the effective matrix is folded from merged
# features' fragments in the default ref's first-parent order, plus the branch's own
# pending amendment, and an abandoned branch's amendment never applies. Phase 1 has no
# CLI reader yet, so this drives the INSTALLED fr's library through its own interpreter
# (`python -P`); phase 2 swaps it for `fr acceptance status`. The fixture is a fresh
# `git init` with a local bare origin.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
py="$(candidate_python)"

world="$(mktemp -d)"
trap 'rm -rf "$world"' EXIT
origin="$world/origin.git"
git init -q --bare -b main "$origin" || fail "bare origin"
git symbolic-ref HEAD refs/heads/main || fail "branch main"
git remote add origin "$origin"
git commit -q --allow-empty -m seed || fail "seed commit"
git push -q -u origin main || fail "seed push"
git remote set-head origin main >/dev/null

mkdir -p docs/acceptance/features
fragment() { # fragment <feature> <rows yaml> <amendments yaml>
  printf 'schema_version: 1\nfeature: %s\nrepo: derio-net/widgets\nrows:%s\namendments:%s\n' \
    "$1" "$2" "$3" > "docs/acceptance/features/$1.yaml"
}
land() { # land <branch>: merge it into main --no-ff and push
  git checkout -q main && git merge -q --no-ff "$1" -m "merge $1" && git push -q origin main \
    || fail "land $1"
}
row() { printf '\n  - {id: %s, capability: %s, acceptance: holds, origin: [spec:%s#R1], status: ci}' "$1" "$2" "$3"; }
amend() { printf '\n  - {row: %s, op: set-status, base: %s, status: %s, notes: %s, why: %s}' "$1" "$2" "$3" "$4" "$4"; }

git checkout -q -b feat/alpha
fragment 2026-01-01-alpha "$(row alpha-spins widgets 2026-01-01-alpha)" " []"
git add -A && git commit -qm alpha || fail "alpha commit"
land feat/alpha

git checkout -q -b feat/zulu main
fragment 2026-01-03-zulu "$(row zulu-hums audio 2026-01-03-zulu)" "$(amend alpha-spins 0 unwired zulu)"
git add -A && git commit -qm zulu || fail "zulu commit"
git checkout -q -b feat/abandoned main
fragment 2026-01-05-abandoned " []" "$(amend alpha-spins 0 failing abandoned)"
git add -A && git commit -qm abandoned || fail "abandoned commit"
git checkout -q -b feat/mine main      # cut before zulu lands, never rebased
fragment 2026-01-04-mine " []" "$(amend alpha-spins 1 walk-owed mine)"
git add -A && git commit -qm mine || fail "mine commit"
land feat/zulu                         # zulu lands after mine was cut
git checkout -q feat/mine

out="$("$py" -P -c '
from pathlib import Path
from fr.acceptance.fold import fold
e = fold(Path("."))
for r in e.matrix.rows:
    print("row", r.id, r.status, e.revisions[r.id], e.owners[r.id])
print("pending", ",".join(a.why for a in e.pending))
print("contested", ",".join(sorted(e.contested)) or "-")
print("identity", e.matrix.org, e.matrix.repo)
' 2>&1)" || { printf '%s\n' "$out" >&2; fail "fold raised"; }

expect_grep '^row zulu-hums ci 0 2026-01-03-zulu$' "$out" "a merged feature's row is in the fold"
expect_grep '^row alpha-spins walk-owed 2 2026-01-01-alpha$' "$out" \
  "merged amendment, then the branch's pending one: revision 2, owner unchanged"
first="$(printf '%s\n' "$out" | grep '^row' | head -1)"
expect_grep 'zulu-hums' "$first" "rows order by capability (audio before widgets)"
expect_grep '^pending mine$' "$out" "the branch's own amendment is pending"
expect_grep '^contested -$' "$out" "a current base contests nothing"
expect_grep '^identity derio-net widgets$' "$out" "identity comes from the fragments' repo:"
refuse_grep 'failing|abandoned' "$out" "an abandoned branch's amendment never applies"
echo "ok: acceptance-effective-matrix-fold"
