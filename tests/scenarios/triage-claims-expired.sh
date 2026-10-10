#!/usr/bin/env bash
# Row triage-claims-expiry: an issue under another scope's EXPIRED claim is reported by
# `fr triage check`, and `fr triage batch create` admits it without claiming it, naming the
# `fr triage claim take` that takes it over (gh#1120: create used to refuse it, while take
# needs it in a batch, so the takeover was unreachable). The facts are fixtures/claims-expired-facts.json, written by
# fixtures/make_claims_facts.py through the model's own serializer; FR_HOST_ID is fixed
# so this scope's id is known and the holder is foreign. Nothing here reaches a forge.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
export FR_HOST_ID=0123456789abcdef

state="$(mktemp -d)"
trap 'rm -rf "$state"' EXIT
cp "$here/fixtures/claims-expired-facts.json" "$state/facts.json"
cat > "$state/judgements.yaml" <<'YAML'
schema: 6
tiers: [{n: 1, title: Now}]
issues:
  "widgets#1": {tier: 1}
  "widgets#2": {tier: 1}
YAML

run_fr out triage check --repo example-org/widgets --dir "$state" --json
require_exit 0 "$out"
json="$(printf '%s' "$out" | tr -d '[:space:]')"
expect_grep '"expired_claims":\[\{[^]]*"key":"widgets#1"' "$json" "the claimed issue is in expired_claims"
expect_grep '"expired_claims":\[\{[^]]*"s-aaaaaaaa"' "$json" "the set names the holder"
refuse_grep '"expired_claims":\[[^]]*widgets#2' "$json" "an unclaimed issue is not in the set"

run_fr out triage check --repo example-org/widgets --dir "$state"
require_exit 0 "$out"
expect_grep 'expired claims' "$out" "the text report names the set"

run_fr out triage batch create b1 --title t --issue widgets#1 --issue widgets#2 --wave 1 \
  --repo example-org/widgets --dir "$state"
require_exit 0 "$out"
flat="$(printf '%s' "$out" | tr -s '[:space:]' ' ')"
expect_grep 's-aaaaaaaa' "$flat" "the take hint names the holder"
expect_grep "fr triage claim take widgets#1 --batch b1 --yes" "$flat" "create names the take that completes it"
expect_grep "claim widgets#2 for b1" "$flat" "the free member's claim is owed"
refuse_grep "claim widgets#1 for b1" "$flat" "the expired-held member is never claimed by create"
grep -q 'id: b1' "$state/judgements.yaml" || fail "create did not write the batch"
echo "ok: triage-claims-expired"
