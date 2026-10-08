#!/usr/bin/env bash
# Row cloud-triage-version-drift: a run recorded under another fr major is re-homed once
# (spec 2026-10-07-cloud-triage R16, R17, §G; Test Plan 12). Three batches are live on
# the fake forge, each with a draft PR whose head carries its run cursor and a recorded
# idle claude-cloud session: b1's cursor records fr 4.9.0, b2's 5.17.0, b3's none. The
# latest release is the captured v5.17.1. One `fr triage drive pass` writes exactly one
# `rehome` request (b1's) to the outbox and reports b3's run as having no recorded
# version; `drive record` applies the agent's result; a second pass writes no rehome
# request and does not report b3 again (rehomes.yaml, in the state ref). The forge is
# fixtures/cloud-triage-drift/bin/gh (captured and derived answers, its header says
# which); the state remote is a bare repo standing in for GitHub through git's
# `url.<base>.insteadOf`.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
export FR_HOST_ID=0123456789abcdef FR_FORGE_API=rest
export PATH="$here/fixtures/cloud-triage-drift/bin:$PATH"
repo=derio-net/super-fr
scope=derio-net--super-fr

world="$(mktemp -d)"
trap 'rm -rf "$world"' EXIT
export HOME="$world/home" FAKE_GH_LOG="$world/gh.log" DRIFT_CURSORS="$world/cursors"
export GIT_CONFIG_GLOBAL="$world/gitconfig"  # never the caller's (p4-o1)
mkdir -p "$HOME" "$DRIFT_CURSORS"
git init -q --bare "$world/state.git" || fail "bare remote"
git config --global url."$world/state.git".insteadOf "https://github.com/$repo.git" \
  || fail "insteadOf"
ref_sha() { git -C "$world/state.git" for-each-ref --format='%(objectname)' refs/fr/triage/; }

git remote add origin "git@github.com:$repo.git" || fail "origin"

# The run cursors on the batch branches' head: fr's own artifact, one per batch.
for b in b1 b2 b3; do
  printf 'schema_version: 10\nrun: r-%s\nbranch: feat/batch-%s\n' "$b" "$b" > "$DRIFT_CURSORS/r-$b.yaml"
done
printf 'fr_version: 4.9.0\n' >> "$DRIFT_CURSORS/r-b1.yaml"
printf 'fr_version: 5.17.0\n' >> "$DRIFT_CURSORS/r-b2.yaml"

# The scope's state, pushed to the ref: three dispatched batches and their sessions.
state="$PWD/.fr/triage-state/$scope"
mkdir -p "$state"
{
  printf 'schema: 6\ntiers: [{n: 1, title: Now}]\nissues:\n'
  for m in 432 458 471; do printf '  super-fr#%s: {tier: 1}\n' "$m"; done
  printf 'batches:\n'
  for n in 1 2 3; do
    m=$((n == 1 ? 432 : n == 2 ? 458 : 471))
    printf '  - id: b%s\n    title: b%s\n    ids: ["super-fr#%s"]\n    wave: 1\n' "$n" "$n" "$m"
    printf '    events:\n      - {kind: dispatch, at: 2026-10-07T05:00:00Z, runner: claude-cloud, handle: h, branch: feat/batch-b%s}\n' "$n"
  done
} > "$state/judgements.yaml"
{
  printf 'sessions:\n'
  for n in 1 2 3; do
    printf -- '- {item: %s/run/batch-b%s, session: s-b%s, state: completed, branch: feat/batch-b%s}\n' \
      "$repo" "$n" "$n" "$n"
  done
} > "$state/sessions.yaml"
printf 'state_repo: %s\n' "$repo" > "$state/scope-durable.yaml"
run_fr out triage state push --repo "$repo"
require_exit 0 "$out"

# Pass 1: exactly one rehome request, for b1's run; b3's run reported.
run_fr out triage drive pass --repo "$repo" --state-repo "$repo" --outbox "$world/outbox.json"
[ "$RC" -eq 0 ] || [ "$RC" -eq 3 ] || fail "pass 1 exit $RC: $out"
box="$(cat "$world/outbox.json")"
[ "$(printf '%s\n' "$box" | grep -c '"kind": "rehome"')" -eq 1 ] \
  || { printf '%s\n' "$box" >&2; fail "pass 1 wrote other than one rehome request"; }
expect_grep "\"id\": \"$repo/run/batch-b1:rehome:1\"" "$box" "the rehome request is b1's"
expect_grep 'fr pickup --run r-b1' "$box" "the resume brief continues b1's run"
expect_grep 'r-b3 has no recorded fr version' "$out" "b3's run is reported"
refuse_grep 'rehome b2' "$out" "b2's run, on the release's major, is left alone"
expect_grep 'releases/latest' "$(cat "$FAKE_GH_LOG")" "the pass read the latest release"
expect_grep "release: v5.17.1" "$(git -C "$world/state.git" show "$(ref_sha):rehomes.yaml")" \
  "the ref carries the re-home ledger"

# The agent re-homes b1's session and records the new one.
printf '[{"id": "%s/run/batch-b1:rehome:1", "session": "s-b1-new"}]\n' "$repo" > "$world/results.json"
run_fr out triage drive record --repo "$repo" --outbox "$world/outbox.json" --result "$world/results.json"
require_exit 0 "$out"

# Pass 2 (interval 0: a full pass, not a renewal): no rehome request, b3 not reported again.
run_fr out triage drive pass --repo "$repo" --interval 0 --outbox "$world/outbox.json"
[ "$RC" -eq 0 ] || [ "$RC" -eq 3 ] || fail "pass 2 exit $RC: $out"
refuse_grep '"kind": "rehome"' "$(cat "$world/outbox.json")" "pass 2 re-homed again"
refuse_grep 'r-b3 has no recorded fr version' "$out" "b3's run was reported twice"
echo "ok: cloud-triage-version-drift"
