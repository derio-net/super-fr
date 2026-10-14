#!/usr/bin/env bash
# Row triage-closed-issues-unclaimed (spec 2026-10-14-merge-truth R1-R3). `fr triage claim
# sync --yes` against a fake REST forge (fixtures/triage-closed-settle/bin/gh, its world in
# $FAKE_FORGE) settles every closed issue the facts list as stale or release-pending:
#   #101  closed member of a running batch, this scope's own claim stands -> the marker is
#         released, both labels come off, no refresh is planned, claims_released recorded;
#   #102  closed, `fr:claimed`, its only marker is by an untrusted author -> both labels
#         come off (it could never be cleaned before);
#   #103  closed and held by another scope's trusted claim -> left alone.
# The facts are fixtures/settle-facts.json, the output of the model's own serializer.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
export FR_HOST_ID=0123456789abcdef FR_FORGE_API=rest
export PATH="$here/fixtures/triage-closed-settle/bin:$PATH"
repo=derio-net/super-fr

world="$(mktemp -d)"
trap 'rm -rf "$world"' EXIT
export HOME="$world/home" FAKE_GH_LOG="$world/gh.log" FAKE_FORGE="$world/forge.json"
mkdir -p "$HOME"
: > "$FAKE_GH_LOG"
state="$world/state"
mkdir -p "$state"
cp "$here/fixtures/settle-facts.json" "$state/facts.json"
cat > "$state/judgements.yaml" <<'EOF2'
schema: 6
tiers: [{n: 1, title: Now}]
issues:
  super-fr#101: {tier: 1}
batches:
  - id: b1
    title: b1
    ids: ["super-fr#101"]
    wave: 1
EOF2

run_fr out triage scope show --repo "$repo" --dir "$state"
require_exit 0 "$out"
me="$(printf '%s\n' "$out" | sed -n 's/^id: //p')"
[ -n "$me" ] || fail "no scope id in: $out"

"$(candidate_python)" - "$FAKE_FORGE" "$me" <<'EOF2'
import json, sys
from datetime import datetime, timedelta, timezone
from fr.triage.claims import Marker, render_marker

path, me = sys.argv[1:3]
t = datetime(2026, 10, 14, tzinfo=timezone.utc)


def body(signer: str) -> str:
    return render_marker(Marker(signer=signer, batch="b1", claimed=t, heartbeat=t,
                                expires=t + timedelta(hours=24)))


def comment(cid: int, login: str, assoc: str, signer: str) -> dict:
    return {"id": cid, "login": login, "association": assoc,
            "created_at": "2026-10-14T00:00:00Z", "body": body(signer)}


both = ["fr:claimed", "fr:in-progress"]
world = {"viewer": "operator", "issues": {
    "101": {"state": "closed", "labels": both, "comments": [comment(1001, "operator", "OWNER", me)]},
    "102": {"state": "closed", "labels": ["fr:claimed"],
            "comments": [comment(1002, "stranger", "NONE", "s-99999999")]},
    "103": {"state": "closed", "labels": both,
            "comments": [comment(1003, "operator", "OWNER", "s-88888888")]},
}}
json.dump(world, open(path, "w"))
EOF2
forge() { python3 -c "import json,sys; w=json.load(open('$FAKE_FORGE')); $1"; }

run_fr out triage claim sync --repo "$repo" --dir "$state"
require_exit 0 "$out"
expect_grep "settle super-fr#101 \(b1\)" "$out" "the closed member is planned a settle"
expect_grep "settle super-fr#102" "$out" "the untrusted-only closed issue is planned a settle"
refuse_grep "settle super-fr#103" "$out" "the held one is never planned"
refuse_grep "refresh super-fr#101|claim super-fr#101" "$out" "a closed member is never refreshed or claimed"
[ ! -s "$FAKE_GH_LOG" ] || fail "a preview called the forge: $(cat "$FAKE_GH_LOG")"

run_fr out triage claim sync --yes --repo "$repo" --dir "$state"
require_exit 0 "$out"
expect_grep "settle super-fr#101 \(b1\): released" "$out" "the own marker is released"
expect_grep "settle super-fr#102: unlabelled" "$out" "the untrusted-only issue is unlabelled"
log="$(cat "$FAKE_GH_LOG")"
expect_grep "DELETE repos/$repo/issues/101/labels/fr%3Aclaimed" "$log" "#101 loses fr:claimed"
expect_grep "DELETE repos/$repo/issues/101/labels/fr%3Ain-progress" "$log" "#101 loses fr:in-progress"
expect_grep "DELETE repos/$repo/issues/102/labels/fr%3Aclaimed" "$log" "#102 loses fr:claimed"
refuse_grep "issues/103/labels" "$log" "the held issue's labels are never touched"
forge 'print(w["issues"]["101"]["labels"], w["issues"]["102"]["labels"], w["issues"]["103"]["labels"])' \
  > "$world/labels.txt"
expect_grep "^\[\] \[\] \['fr:claimed', 'fr:in-progress'\]$" "$(cat "$world/labels.txt")" \
  "both labels are off #101 and #102, #103 keeps its"
forge 'print("released" in w["issues"]["101"]["comments"][0]["body"].lower().split("-->")[0])' \
  > "$world/released.txt"
expect_grep "^True$" "$(cat "$world/released.txt")" "the own marker is in its released form"
expect_grep "claims_released" "$(cat "$state/judgements.yaml")" "the member's release is recorded"

run_fr out triage claim sync --yes --repo "$repo" --dir "$state"
require_exit 0 "$out"
echo "ok: triage-closed-settle"
