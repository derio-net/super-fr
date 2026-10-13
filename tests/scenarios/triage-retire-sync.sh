#!/usr/bin/env bash
# Row triage-retire-then-sync (spec 2026-10-14-merge-truth R6). `fr triage scope retire
# --yes` releases a dead scope's claim and drops it from the stored facts, so with no collect
# in between `fr triage check` shows nothing held elsewhere and `fr triage claim sync --yes`
# claims the member the batch owes: the marker is posted and `fr:claimed` is added. Against
# a fake REST forge (fixtures/triage-closed-settle/bin/gh, its world in $FAKE_FORGE). The
# facts are fixtures/retire-sync-facts.json, the output of the model's own serializer.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
export FR_HOST_ID=0123456789abcdef FR_FORGE_API=rest
export PATH="$here/fixtures/triage-closed-settle/bin:$PATH"
repo=derio-net/super-fr
dead=s-dddddddd

world="$(mktemp -d)"
trap 'rm -rf "$world"' EXIT
export HOME="$world/home" FAKE_GH_LOG="$world/gh.log" FAKE_FORGE="$world/forge.json"
mkdir -p "$HOME"
: > "$FAKE_GH_LOG"
state="$world/state"
mkdir -p "$state"
cp "$here/fixtures/retire-sync-facts.json" "$state/facts.json"
cat > "$state/judgements.yaml" <<'EOF2'
schema: 6
tiers: [{n: 1, title: Now}]
issues:
  super-fr#201: {tier: 1}
batches:
  - id: b1
    title: b1
    ids: ["super-fr#201"]
    wave: 1
EOF2

run_fr out triage scope show --repo "$repo" --dir "$state"
require_exit 0 "$out"
me="$(printf '%s\n' "$out" | sed -n 's/^id: //p')"
[ -n "$me" ] || fail "no scope id in: $out"

"$(candidate_python)" - "$FAKE_FORGE" "$dead" <<'EOF2'
import json, sys
from datetime import datetime, timezone
from fr.triage.claims import Marker, render_marker

path, dead = sys.argv[1:3]
claimed = datetime(2026, 9, 1, tzinfo=timezone.utc)
expires = datetime(2026, 9, 2, tzinfo=timezone.utc)
body = render_marker(Marker(signer=dead, batch="their-batch", claimed=claimed,
                            heartbeat=claimed, expires=expires))
world = {"viewer": "operator", "issues": {"201": {
    "state": "open", "labels": ["fr:claimed"],
    "comments": [{"id": 2001, "login": "operator", "association": "OWNER",
                  "created_at": "2026-09-01T00:00:00Z", "body": body}]}}}
json.dump(world, open(path, "w"))
EOF2

run_fr out triage check --repo "$repo" --dir "$state"
require_exit 0 "$out"
expect_grep "held elsewhere \(1\)" "$out" "before the retire the dead scope's claim holds the member"
run_fr out triage claim sync --repo "$repo" --dir "$state"
expect_grep "held super-fr#201" "$out" "sync claims nothing while it is held"

run_fr out triage scope retire "$dead" --yes --repo "$repo" --dir "$state"
require_exit 0 "$out"
expect_grep "released super-fr#201" "$out" "the dead scope's claim is released"
refuse_grep "fr triage collect" "$out" "retire no longer asks for a collect"
expect_grep "claim sync --yes" "$out" "retire names the sync that claims the members"

run_fr out triage check --repo "$repo" --dir "$state"
require_exit 0 "$out"
expect_grep "held elsewhere \(0\)" "$out" "with no collect, nothing is held elsewhere"

run_fr out triage claim sync --yes --repo "$repo" --dir "$state"
require_exit 0 "$out"
expect_grep "claim super-fr#201 \(b1\): posted" "$out" "the member the batch owes is claimed"
log="$(cat "$FAKE_GH_LOG")"
expect_grep "POST repos/$repo/issues/201/comments" "$log" "the claim marker is posted"
expect_grep "POST repos/$repo/issues/201/labels" "$log" "fr:claimed is added"
"$(candidate_python)" - "$FAKE_FORGE" "$me" <<'EOF2' || fail "the forge does not show this scope's claim"
import json, sys
from fr.triage.claims import parse_marker

path, me = sys.argv[1:3]
w = json.load(open(path))["issues"]["201"]
marks = [parse_marker(c["body"]) for c in w["comments"]]
mine = [m for m in marks if m is not None and m.signer == me and m.released is None]
dead = [m for m in marks if m is not None and m.signer == "s-dddddddd" and m.released is None]
assert len(mine) == 1 and not dead and "fr:claimed" in w["labels"], (marks, w["labels"])
EOF2
echo "ok: triage-retire-sync"
