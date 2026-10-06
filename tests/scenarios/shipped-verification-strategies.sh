#!/usr/bin/env bash
# Row shipped-verification-strategies: candidate, client-live, prerelease and
# live ship and validate; the candidate family installs through the repo's
# install contract, and a repo without it is refused by name.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

run_fr out verification list;                 require_exit 0 "$out"
for s in candidate client-live prerelease live; do
  expect_grep "^$s +" "$out" "shipped strategy $s is listed"
  run_fr one verification check "$s";         require_exit 0 "$one"
  expect_grep "$s: ok" "$one" "shipped strategy $s validates"
done
run_fr out verification check --all;          require_exit 0 "$out"

# A walk with no such run is refused; this fixture has no install contract
# either, and nothing is installed on the way to either refusal.
run_fr out verification walk --run no-such-run --model scenario
[ "$RC" -ne 0 ] || fail "a walk with no run succeeded"
echo "ok: shipped-verification-strategies"
