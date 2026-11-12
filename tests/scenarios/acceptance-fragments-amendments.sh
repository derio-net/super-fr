#!/usr/bin/env bash
# Row acceptance-fragments-amendments (spec 2026-11-04-repo-feature-settings R16, R17):
# feature A merges row r; feature B amends r (set-status) and merges; feature C,
# branched before B merged, amends r at the stale base 0 and `fr acceptance check`
# (which fetches the default ref) refuses it, exit 2; re-based with
# `fr acceptance amend --rebase`, it passes. An abandoned feature D's amendment never
# shows on the default branch. The fixture is a fresh `git init` with a local bare
# `origin` (a directory, no forge).
# Portable: no GNU-only flags (BSD/macOS and GNU userlands alike).
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

bare="$(mktemp -d)/origin.git"
git init -q --bare -b main "$bare" 2>/dev/null || fail "git init --bare"
git init -q . 2>/dev/null || fail "git init"
git symbolic-ref HEAD refs/heads/main || fail "name the default branch main"   # a re-init ignores -b
git remote add origin "$bare" || fail "remote"
printf '# widget\n' > README.md
mkdir -p docs/acceptance/features
cat > docs/acceptance/features/2026-01-01-alpha.yaml <<'YAML'
schema_version: 1
feature: 2026-01-01-alpha
repo: acme/widget
rows:
  - id: r
    capability: Widget
    acceptance: r works
    origin:
    - widget:README.md
    levels: {}
    status: not-implemented
    notes: owed
YAML
git add -A && git commit -qm "feat: alpha" || fail "feature A commit"
git push -q -u origin main 2>/dev/null || fail "push feature A"

git checkout -qb feat/c || fail "branch C"   # C forks before B merges
git checkout -q main
git checkout -qb feat/b || fail "branch B"
run_fr out acceptance amend --id r --op set-status --status unwired \
  --notes "a test exists" --why "B wrote the test" --feature 2026-02-01-beta
require_exit 0 "$out"
b="$(cat docs/acceptance/features/2026-02-01-beta.yaml)"
expect_grep 'op: set-status' "$b" "B's fragment carries the amendment"
expect_grep 'base: 0' "$b" "B's amendment is based on revision 0"
git checkout -q main && git merge -q --no-ff -m "Merge feat/b" feat/b || fail "merge B"
git push -q origin main 2>/dev/null || fail "push B"

git checkout -q feat/c
git update-ref refs/remotes/origin/main "$(git rev-parse main~1)" \
  || fail "rewind the tracking ref so check must fetch"
run_fr out acceptance amend --id r --op set-status --status walk-owed \
  --notes "needs a live walk" --why "C needs a walk" --feature 2026-03-01-gamma --base 0
require_exit 0 "$out"
run_fr out acceptance check
require_exit 2 "$out"
expect_grep 'amendment set-status of row r is based on revision 0' "$out" "check names the stale base"
expect_grep 'at revision 1' "$out" "check names the current revision"
expect_grep 'fr acceptance amend --rebase' "$out" "check names the re-base"

run_fr out acceptance amend --rebase
require_exit 0 "$out"
expect_grep 're-based 0 → 1' "$out" "the amendment is re-based"
[ -z "$(git status --porcelain)" ] || fail "the re-base left uncommitted changes"
run_fr out acceptance check
require_exit 0 "$out"

git checkout -q main
git checkout -qb feat/d || fail "branch D"
run_fr out acceptance amend --id r --op reword --acceptance "r works, as D abandoned it" \
  --why "never merged" --feature 2026-04-01-delta
require_exit 0 "$out"
git checkout -q main
git checkout -qb feat/e origin/main 2>/dev/null || fail "branch E from the default ref"
run_fr out acceptance status
require_exit 0 "$out"
expect_grep 'r \[unwired\] r works' "$out" "B's merged amendment applies"
refuse_grep 'as D abandoned it' "$out" "an abandoned feature's amendment never applies"
echo "ok: acceptance-fragments-amendments"
