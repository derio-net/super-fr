#!/usr/bin/env bash
# Row merge-train-red-recovery (spec 2026-10-11-merge-train-safety R9-R11). The host driver (`fr triage batch drive
# --once --yes`) against the fake REST forge of merge-train-label-gate (its world in
# $FAKE_FORGE, `red` and `strict` keys), a fake herdr whose `tab list` is a live capture
# (the `batch-archive-followups` tab is idle) and which records every `agent prompt`, and
# a real bare remote where the driver's update pushes land. Phases:
#   A. the PR is red at a head fr made (an `update` event, base M0) and main has moved
#      since: the pass hands it back to the idle session like any red head, and never
#      updates the PR again (the `reupdate` rule is gone: spec 2026-11-19-wave-merge-queue
#      R13, R22, the queue never updates a PR branch);
#   B. a session pushes and that head is red: the pass hands it back to the idle session
#      once (one prompt naming the sha), a second pass over the same head sends nothing,
#      and the board's `failing-ci` need is gone while the hand-back covers the head;
#   B3. the session's tab is gone and a new head is red: the pass says no session can take
#      it, records it once, and the board shows a `red-pr` need.
# The `update` event seeded in A is one an older judgements.yaml carries: it is still read.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
export FR_HOST_ID=0123456789abcdef FR_FORGE_API=rest
export PATH="$here/fixtures/merge-train-red-recovery/bin:$here/fixtures/merge-train-label-gate/bin:$PATH"
repo=derio-net/super-fr
tab=derio-net/super-fr/run/batch-archive-followups

world="$(mktemp -d)"
trap 'rm -rf "$world"' EXIT
export HOME="$world/home" FAKE_GH_LOG="$world/gh.log" FAKE_FORGE="$world/forge.json"
export HERDR_FAKE_LOG="$world/herdr.log" HERDR_PROMPTS="$world/prompts"
export GIT_CONFIG_GLOBAL="$world/gitconfig"
export FR_HERDR_CACHE_DIR="$world/herdr-cache" FR_TRIAGE_LOCK_DIR="$world/locks"
mkdir -p "$HOME"
: > "$FAKE_GH_LOG" && : > "$HERDR_FAKE_LOG" && : > "$HERDR_PROMPTS"
bare="$world/github/$repo.git"
origin="file://localhost$bare"
mkdir -p "$(dirname "$bare")"
git init -q --bare "$bare" || fail "bare remote"
git config --global init.defaultBranch main

# The remote: main M0 (a CI workflow, so the repo is not `ci none`, and the triage config)
# and the batch branch two commits ahead of it: H0 (approved), H1 (fr's update of it).
seed="$world/seed"
git clone -q "$origin" "$seed" 2>/dev/null || fail "clone the bare remote"
config='merge_method: merge
'
mkdir -p "$seed/.github/workflows" "$seed/.fr"
printf 'on: push\njobs: {}\n' > "$seed/.github/workflows/ci.yml"
printf '%s' "$config" > "$seed/.fr/triage.yaml"
printf 'code\n' > "$seed/code.py"
git -C "$seed" add -A && git -C "$seed" commit -qm "seed" && git -C "$seed" push -q origin HEAD:main \
  || fail "seed main"
m0="$(git -C "$seed" rev-parse HEAD)"
push_branch() {  # push_branch <file> <text>: a session commit on the batch branch
  git -C "$seed" fetch -q origin && git -C "$seed" checkout -q -B feat/batch-archive-followups \
    origin/feat/batch-archive-followups && printf '%s\n' "$2" >> "$seed/$1" \
    && git -C "$seed" add -A && git -C "$seed" commit -qm "session: $2" \
    && git -C "$seed" push -q origin feat/batch-archive-followups || fail "push $2"
  git -C "$bare" rev-parse feat/batch-archive-followups
}
git -C "$seed" checkout -qb feat/batch-archive-followups && printf 'a\n' > "$seed/a.txt" \
  && git -C "$seed" add -A && git -C "$seed" commit -qm "followups: the change" \
  && git -C "$seed" push -q origin feat/batch-archive-followups || fail "seed the batch branch"
h0="$(git -C "$seed" rev-parse HEAD)"
h1="$(push_branch a.txt "fr update")"
git -C "$seed" checkout -q main && printf 'more code\n' >> "$seed/code.py" \
  && git -C "$seed" commit -qam "main moves" && git -C "$seed" push -q origin main || fail "move main"
m1="$(git -C "$seed" rev-parse HEAD)"

# The driver's clone: this fixture.
git remote add origin "$origin" && git fetch -q origin \
  && git remote set-head origin main && git checkout -q -B main origin/main || fail "the clone"

state="$world/state"
mkdir -p "$state"
cat > "$state/judgements.yaml" <<EOF2
schema: 9
tiers: [{n: 1, title: Now}]
issues:
  super-fr#1074: {tier: 1}
batches:
  - id: archive-followups
    title: archive-followups
    ids: ["super-fr#1074"]
    wave: 1
    launch: {runner: herdr, harness: claude, model: claude-opus-5-5}
    events:
      - {kind: dispatch, at: 2026-10-07T05:00:00Z, runner: herdr, handle: h, branch: feat/batch-archive-followups}
      - {kind: approval, at: 2026-10-07T05:10:00Z, pr: 1080, head: $h0}
      - {kind: update, at: 2026-10-07T05:20:00Z, pr: 1080, head_before: $h0, head_after: $h1, base: $m0}
EOF2
python3 - "$FAKE_FORGE" "$bare" "$config" "$h1" <<'EOF2'
import json, sys
json.dump({"bare": sys.argv[2], "config": sys.argv[3], "label_defined": True,
           "pr": {"branch": "feat/batch-archive-followups", "draft": False,
                  "labels": ["approved-fr"], "merged": False},
           "issue_labels": [], "comments": [], "pending": [], "red": [sys.argv[4]]},
          open(sys.argv[1], "w"))
EOF2

forge() {  # forge <python statement over `w`>: the world changes, as the operator or CI would
  python3 - "$FAKE_FORGE" "$1" <<'EOF2'
import json, sys
w = json.load(open(sys.argv[1])); exec(sys.argv[2]); json.dump(w, open(sys.argv[1], "w"))
EOF2
}
drive() { run_fr out triage batch drive --once --yes --keep-sessions --repo "$repo" --dir "$state" \
  --checkout "$repo=$PWD"
  [ "$RC" -eq 0 ] || [ "$RC" -eq 3 ] || fail "drive exited $RC (3 is a pass waiting on checks): $out"; }
board() {  # the board over the facts the last pass collected
  run_fr page triage backlog --repo "$repo" --dir "$state"; require_exit 0 "$page"
  cat "$state/backlog.html"
}
log() { cat "$FAKE_GH_LOG"; }
prompts() { grep -c -- '^--END--$' "$HERDR_PROMPTS" || true; }
events() { grep -c -- "kind: $1" "$state/judgements.yaml" || true; }
R="repos/$repo"

# A. Red at fr's own update head, main moved since: handed back, never updated again.
drive
expect_grep "CI failing at ${h1:0:12}" "$out" "the red head is reported"
refuse_grep "updated PR" "$out" "a red fr-made head is never updated again"
[ "$(git -C "$bare" rev-parse feat/batch-archive-followups)" = "$h1" ] || fail "the PR branch moved"
[ "$(events update)" = 1 ] || fail "expected the one seeded update event, got $(events update)"
expect_grep "handed back to its session $tab" "$out" "it is handed back instead"
[ "$(prompts)" = 1 ] || fail "expected one prompt after phase A, got $(prompts)"

# B. A session pushes a red head: handed back to the idle session, once.
s1="$(push_branch a.txt "session one")"
forge "w['red'] = ['$s1']"
drive
expect_grep "CI failing at ${s1:0:12}" "$out" "the session's red head is reported"
expect_grep "handed back to its session $tab" "$out" "an idle session is handed the red PR"
[ "$(prompts)" = 2 ] || fail "expected a second prompt, got $(prompts)"
expect_grep "$s1" "$(cat "$HERDR_PROMPTS")" "the prompt names the failing sha"
expect_grep "approved-fr" "$(cat "$HERDR_PROMPTS")" "the prompt tells the session not to add the label"
drive  # the same red head again: nothing sent, nothing said
[ "$(prompts)" = 2 ] || fail "a second pass over the same red head sent another prompt"
refuse_grep "CI failing" "$out" "a second pass says nothing new about it"
[ "$(events red_handback)" = 2 ] || fail "expected two red_handback events"
page="$(board)"
refuse_grep 'data-need="failing-ci"' "$page" "a delivered hand-back is in progress, not a failing-ci need"

# B3. The session is gone and the next head is red: it needs you, once.
s2="$(push_branch a.txt "session two")"
forge "w['red'] = ['$s2']"
export HERDR_NO_TAB="$tab"
drive
expect_grep "no session can take it" "$out" "an unreachable session is a Needs-you"
[ "$(prompts)" = 2 ] || fail "a gone session was messaged"
drive
refuse_grep "CI failing" "$out" "the Needs-you is decided once per head"
expect_grep 'data-need="red-pr"' "$(board)" "the board shows a red-pr need"
unset HERDR_NO_TAB

echo "ok: merge-train-red-recovery"
