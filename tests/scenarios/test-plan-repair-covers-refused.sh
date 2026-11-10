#!/usr/bin/env bash
# Row test-plan-repair-covers-refused (spec 2026-11-08 R8, R9): every Test Plan heading fr refuses
# as a near-miss (`#`, `##`, `###`) is repaired by `fr migrate artifacts --yes`, and the repaired
# specs validate clean with the steps the writer meant. Driven through the installed fr, in a
# fresh `git init` fixture, no forge.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

git init -q -b main . 2>/dev/null || fail "git init"
git config commit.gpgsign false
specs=docs/superpowers/specs
mkdir -p "$specs"

# mkspec <name> <heading> <sibling>: one spec, two steps under the heading, a sibling after it.
mkspec() {
  printf '# Widget\n\n## Requirements\n\nR1.\n\n%s\n\n1. Run it.\n2. Watch it.\n\n%s\n\n- not a step\n\n## Plans\n' \
    "$2" "$3" > "$specs/2026-11-08-$1-design.md"
}
mkspec h1 '# 6. Test Plan' '## Notes'
mkspec h2 '## 6) Test Plan (post-merge)' '### Notes'
mkspec h3 '### §6.1 Test Plan' '### Notes'
git add -A && git commit -qm seed || fail "seed commit"

run_fr out validate artifacts
[ "$RC" -ne 0 ] || fail "validate should refuse the near-miss headings: $out"
expect_grep 'Test Plan' "$out" "validate names the heading"

run_fr out migrate artifacts --yes
require_exit 0 "$out"
run_fr out validate artifacts
require_exit 0 "$out"
for s in h1 h2 h3; do
  f="$specs/2026-11-08-$s-design.md"
  grep -qx '## Test Plan' "$f" || fail "$s: heading not renamed"
  steps="$(awk '/^## Test Plan$/{on=1;next} /^#{1,2} /{on=0} on && /^[0-9]+\. /{n++} END{print n+0}' "$f")"
  [ "$steps" = 2 ] || fail "$s: $steps steps, wanted 2"
  refuse_grep '^#{1,3} .*6' "$(cat "$f")" "$s: no numbered heading left"
done
grep -qx '## Notes' "$specs/2026-11-08-h1-design.md" && fail "h1: Notes should be demoted"
grep -qx '## Notes' "$specs/2026-11-08-h3-design.md" || fail "h3: Notes should be promoted"
echo "ok: test-plan-repair-covers-refused"
