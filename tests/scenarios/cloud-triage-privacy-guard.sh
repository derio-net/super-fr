#!/usr/bin/env bash
# Row cloud-triage-privacy-guard: with a public state repo, `fr triage batch create` of a
# private repo's issue exits 2 naming the issue, its repo and the state repo, and
# judgements.yaml is byte-identical afterwards (spec 2026-10-07-cloud-triage R8). The
# scope is a group of a public and a private repo; fixtures/cloud-triage-privacy-facts.json
# is fr's own facts file (fictional example-org repos), whose visibility map answers the
# guard, so nothing here reaches a forge. Then the scope's state repo is switched to the
# PRIVATE repo, and the very same create of the private issue lands. (Test Plan 7's
# lease-push half is phase 4's, with the lease.)
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
export FR_HOST_ID=0123456789abcdef
group=example-org/gadgets,example-org/widgets

state="$(mktemp -d)"
trap 'rm -rf "$state"' EXIT
export HOME="$state/home"
mkdir -p "$HOME"
cp "$here/fixtures/cloud-triage-privacy-facts.json" "$state/facts.json"
cat > "$state/judgements.yaml" <<'YAML'
schema: 6
tiers: [{n: 1, title: Now}]
issues:
  "gadgets#1": {tier: 1}
  "widgets#7": {tier: 1}
YAML
printf 'state_repo: example-org/gadgets\n' > "$state/scope-durable.yaml"

before="$(cat "$state/judgements.yaml")"
run_fr out triage batch create b1 --title t --issue widgets#7 --repo "$group" --dir "$state"
require_exit 2 "$out"
flat="$(printf '%s' "$out" | tr -s '[:space:]' ' ')"
expect_grep 'widgets#7' "$flat" "the refusal names the issue"
expect_grep 'example-org/widgets' "$flat" "the refusal names the issue's repo"
expect_grep 'example-org/gadgets' "$flat" "the refusal names the state repo"
[ "$(cat "$state/judgements.yaml")" = "$before" ] || fail "a refused create wrote judgements.yaml"

printf 'state_repo: example-org/widgets\n' > "$state/scope-durable.yaml"
run_fr out triage batch create b1 --title t --issue widgets#7 --repo "$group" --dir "$state"
require_exit 0 "$out"
grep -q 'widgets#7' "$state/judgements.yaml" || fail "the create into a private state repo wrote nothing"
[ "$(cat "$state/judgements.yaml")" != "$before" ] || fail "the create into a private state repo wrote nothing"
echo "ok: cloud-triage-privacy-guard"
