#!/usr/bin/env bash
# Row triage-adopt-holds-agent: `fr triage batch adopt` (no --yes) prints the message the
# adopted agent would get, held by default (the HOLD block under "    | "), and with
# --no-hold says "(not held)" with no HOLD line. herdr and gh are fakes replaying
# captured shapes (fixtures/triage-adopt/, ids redacted); the clone is a throwaway repo
# with a bare local origin and a linked worktree. Nothing here reaches a forge or herdr.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
export HERDR_FAKE_LOG="$work/herdr.log" FAKE_GH_LOG="$work/gh.log"
: > "$HERDR_FAKE_LOG"
export HERDR_ENV=1 HERDR_PANE_ID=w0:p0 HERDR_WORKSPACE_ID=w7
export FR_FORGE_API=rest FR_HOST_ID=0123456789abcdef
export GIT_REAL="$(command -v git)"
export PATH="$here/fixtures/triage-adopt/bin:$PATH"

"$GIT_REAL" init -q --bare "$work/origin.git"
"$GIT_REAL" init -q -b main "$work/clone"
"$GIT_REAL" -C "$work/clone" remote add origin "$work/origin.git"
"$GIT_REAL" -C "$work/clone" commit -q --allow-empty -m init
"$GIT_REAL" -C "$work/clone" push -q origin main
"$GIT_REAL" -C "$work/clone" remote set-head origin main 2>/dev/null || true
"$GIT_REAL" -C "$work/clone" worktree add -q -b feat/hand-started "$work/wt"

state="$work/state"
mkdir -p "$state"
cat > "$state/facts.json" <<'JSON'
{"schema": 3, "scope": "example-org--widgets", "kind": "repo",
 "collected_at": "2026-10-06T00:00:00Z", "repos": ["example-org/widgets"],
 "viewer": "operator",
 "issues": [{"repo": "example-org/widgets", "number": 1, "title": "one", "state": "open",
             "url": "https://github.com/example-org/widgets/issues/1"}]}
JSON
cat > "$state/judgements.yaml" <<'YAML'
schema: 6
tiers: [{n: 1, title: Now}]
issues:
  "widgets#1": {tier: 1}
batches:
  - id: lifecycle
    title: Lifecycle
    ids: ["widgets#1"]
    rationale: one
    bump: minor
    launch: {runner: herdr, harness: claude, model: claude-opus-5-5}
YAML

adopt() {
  run_fr out triage batch adopt lifecycle --tab w7:t5 --branch feat/hand-started \
    --checkout "$work/clone" --repo example-org/widgets --dir "$state" "$@"
}

adopt
require_exit 0 "$out"
expect_grep '  runner: message the agent \(held\)' "$out" "the plan says the message is held"
expect_grep '^    \| HOLD: acknowledge this message only\.' "$out" "the HOLD block is printed under the pipe prefix"
expect_grep "^    \\| operator's go-ahead\\.$" "$out" "the HOLD block is whole"
expect_grep 'nothing written' "$out" "a dry run says so"
refuse_grep 'driven' "$out" "the message no longer says driven"

adopt --no-hold
require_exit 0 "$out"
expect_grep '  runner: message the agent \(not held\)' "$out" "--no-hold says so"
refuse_grep 'HOLD' "$out" "--no-hold prints no HOLD line"
if grep -Eq 'tab rename|agent rename|agent start|send-text|prompt' "$HERDR_FAKE_LOG"; then
  cat "$HERDR_FAKE_LOG" >&2; fail "a dry run wrote to herdr"
fi
echo "ok: triage-adopt-hold"
