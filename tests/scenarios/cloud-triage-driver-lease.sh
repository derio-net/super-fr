#!/usr/bin/env bash
# Row cloud-triage-driver-lease: one driver per scope (spec 2026-10-07-cloud-triage R9, R12,
# Test Plan 14). An empty workspace B restores the scope's state from the ref a workspace A
# pushed; one `fr triage drive pass` against the fake forge renews the lease and pushes it,
# so the ref advances; a scripted session executor answers the outbox, and `drive record`
# applies it and empties the outbox. Then a second driver (another FR_HOST_ID, same
# workspace) is refused naming the holder and expiry, and `fr triage lease take` without
# --yes changes nothing. Then the realistic contender (p4-r8): the SAME host id under the
# other kind (a `host:` driver against the `cloud:` lease), in a SEPARATE workspace C
# restored from the ref, is refused through the ref's lease.yaml. The state remote is a
# bare repo standing in for GitHub through git's own `url.<base>.insteadOf`; the forge is
# fixtures/cloud-triage-driver/bin/gh. The claude-cloud runner (phase 5) is not installed
# here and a pass without it refuses (p4-r6), so the cloud driver's commands run the
# installed fr through fixtures/cloud-triage-driver/stub_cloud.py, which injects a stub
# Mailbox runner; the scope has no batch, so the outbox holds no request, and the executor
# answers each request it is given, which is none.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
export FR_HOST_ID=0123456789abcdef FR_FORGE_API=rest
export PATH="$here/fixtures/cloud-triage-driver/bin:$PATH"
repo=derio-net/super-fr
scope=derio-net--super-fr

world="$(mktemp -d)"
trap 'rm -rf "$world"' EXIT
export HOME="$world/home" FAKE_GH_LOG="$world/gh.log"
# git's global config is this world's own file: the test suite lends the operator's
# (GIT_CONFIG_GLOBAL) to its children, and the insteadOf below must never reach it.
export GIT_CONFIG_GLOBAL="$world/gitconfig"
mkdir -p "$HOME"
git init -q --bare "$world/state.git" || fail "bare remote"
git config --global url."$world/state.git".insteadOf "https://github.com/$repo.git" \
  || fail "insteadOf"
# The installed fr's own interpreter runs it with the stub claude-cloud runner (p4-r6).
fr_py="$(head -1 "$(readlink -f "$(command -v fr)")" | sed 's/^#![[:space:]]*//')"
[ -x "$fr_py" ] || fail "no interpreter for the installed fr ($fr_py)"
run_cloud() {
  local __var="$1"; shift
  local __out
  __out="$("$fr_py" "$here/fixtures/cloud-triage-driver/stub_cloud.py" "$@" 2>&1)"; RC=$?
  printf -v "$__var" '%s' "$__out"
}
ref_sha() { git -C "$world/state.git" for-each-ref --format='%(objectname)' refs/fr/triage/; }

# Workspace A (the fixture) seeds the ref.
a="$PWD"
seed="$a/.fr/triage-state/$scope"
mkdir -p "$seed"
printf 'schema: 6\ntiers: [{n: 1, title: Now}]\nissues: {}\n' > "$seed/judgements.yaml"
printf 'state_repo: %s\n' "$repo" > "$seed/scope-durable.yaml"
run_fr out triage state push --repo "$repo"
require_exit 0 "$out"
seeded="$(ref_sha)"
[ -n "$seeded" ] || fail "workspace A pushed no ref"

# Workspace B: empty, restored from the ref by its first pass.
b="$world/b"
git init -q "$b" && git -C "$b" remote add origin "git@github.com:$repo.git" || fail "workspace B"
cd "$b" || fail "cd B"
state="$b/.fr/triage-state/$scope"
run_fr out triage drive pass --repo "$repo" --state-repo "$repo" --outbox "$world/none.json"
require_exit 2 "$out"
expect_grep 'claude-cloud' "$out" "a pass with no cloud runner refuses, naming it (p4-r6)"
[ ! -f "$world/none.json" ] || fail "a refused pass wrote an outbox"
run_cloud out triage drive pass --repo "$repo" --state-repo "$repo" --outbox "$world/outbox.json"
require_exit 0 "$out"
cmp -s "$seed/judgements.yaml" "$state/judgements.yaml" || fail "the pass did not restore the state"
advanced="$(ref_sha)"
[ -n "$advanced" ] && [ "$advanced" != "$seeded" ] || fail "the pass did not advance the ref"
lease="$(git -C "$world/state.git" show "$advanced:lease.yaml")"
expect_grep "^holder: s-[0-9a-f]{8} cloud:$FR_HOST_ID\$" "$lease" "the pushed lease names this cloud driver"
expect_grep '^last_pass: ' "$lease" "the pushed lease records the pass"
refuse_grep 'install.sh' "$out" "the cloud driver ran no post_merge"
[ -f "$world/outbox.json" ] || fail "the pass wrote no outbox"

# The scripted session executor: one result per request in the outbox.
printf '[' > "$world/results.json"
sed -n 's/.*"id": "\([^"]*\)".*/{"id": "\1", "session": "session-for-\1"}/p' "$world/outbox.json" \
  | paste -sd, - >> "$world/results.json"
printf ']\n' >> "$world/results.json"
run_cloud out triage drive record --repo "$repo" --outbox "$world/outbox.json" --result "$world/results.json"
require_exit 0 "$out"
expect_grep '"requests": \[\]' "$(cat "$world/outbox.json")" "the record emptied the outbox"
[ -z "$(git status --porcelain --untracked-files=all)" ] || fail "the driver's state shows in git status"

# A second driver on this workspace is refused by the lease.
before="$(cat "$state/lease.yaml")"
FR_HOST_ID=fedcba9876543210 run_cloud out triage drive pass --repo "$repo" --outbox "$world/o2.json"
require_exit 2 "$out"
flat="$(printf '%s' "$out" | tr -s '[:space:]' ' ')"
expect_grep "held by s-[0-9a-f]{8} cloud:0123456789abcdef" "$flat" "the refusal names the holder"
expect_grep 'expires 20[0-9-]{8}T' "$flat" "the refusal names the expiry"
FR_HOST_ID=fedcba9876543210 run_fr out triage lease take --as cloud --repo "$repo"
require_exit 2 "$out"
expect_grep -- '--yes' "$out" "lease take without --yes says how to take it"
[ "$(cat "$state/lease.yaml")" = "$before" ] || fail "lease take without --yes changed the lease"

# Workspace C (p4-r8): a host driver on the SAME host id, restored from the ref alone, is
# refused by the cloud driver's lease the ref carries, naming it; it writes nothing.
c="$world/c"
git init -q "$c" && git -C "$c" remote add origin "git@github.com:$repo.git" || fail "workspace C"
cd "$c" || fail "cd C"
run_fr out triage state fetch --repo "$repo" --state-repo "$repo"
require_exit 0 "$out"
cstate="$c/.fr/triage-state/$scope"
cmp -s "$state/lease.yaml" "$cstate/lease.yaml" || fail "workspace C did not restore the lease"
held_ref="$(ref_sha)"
run_fr out triage batch drive --once --yes --repo "$repo"
require_exit 2 "$out"
flat="$(printf '%s' "$out" | tr -s '[:space:]' ' ')"
expect_grep "held by s-[0-9a-f]{8} cloud:$FR_HOST_ID" "$flat" \
  "the host driver on the same host id is refused by the cloud lease"
refuse_grep "host:$FR_HOST_ID" "$(cat "$cstate/lease.yaml")" "the refused host driver took the lease"
[ "$(ref_sha)" = "$held_ref" ] || fail "the refused host driver moved the ref"
echo "ok: cloud-triage-driver-lease"
