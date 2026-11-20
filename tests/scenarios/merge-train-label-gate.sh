#!/usr/bin/env bash
# Rows merge-train-label-gate, approval-label-created, approval-board-and-briefs (spec
# 2026-10-11-merge-train-safety R1-R5, R8; 2026-11-19-wave-merge-queue R12, R22). The host
# driver (`fr triage batch drive --once --yes`) against a fake REST forge
# (fixtures/merge-train-label-gate/bin/gh, its world in $FAKE_FORGE) and a real bare remote.
# The clone reaches it by a `file://localhost/.../derio-net/super-fr.git` URL rather than
# `url.<base>.insteadOf`: `git remote get-url` expands insteadOf, and the driver reads the
# batch's repo from that URL. The repo declares no `queue.ci`, so its queue is held and no
# PR lands: what is proved is the approval, which is the queue's entry rule. Four passes:
#   1. the label is missing: the pass creates it and says so; the PR is green and
#      unlabelled, so it is held as awaiting approval, the board asks for the label and
#      its card awaits approval; `batch merge` refuses it by name (exit 2);
#   2. the operator labels it: the pass records the approval at the head and its patch-id;
#   3. a session pushes a change: the approval is void, the label removed (logged), and the
#      board asks for a re-label;
#   4. the operator re-labels: the approval is recorded again, and fr merges nothing by the
#      forge's API (the queue lands by push).
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
export FR_HOST_ID=0123456789abcdef FR_FORGE_API=rest
export PATH="$here/fixtures/merge-train-label-gate/bin:$PATH"
repo=derio-net/super-fr

world="$(mktemp -d)"
trap 'rm -rf "$world"' EXIT
export HOME="$world/home" FAKE_GH_LOG="$world/gh.log" FAKE_FORGE="$world/forge.json"
export GIT_CONFIG_GLOBAL="$world/gitconfig"
mkdir -p "$HOME"
: > "$FAKE_GH_LOG"
bare="$world/github/$repo.git"
origin="file://localhost$bare"
mkdir -p "$(dirname "$bare")"
git init -q --bare "$bare" || fail "bare remote"
git config --global init.defaultBranch main

# The remote: main (with a CI workflow, so the repo is not `ci none`, and the triage
# config) and the batch branch one commit ahead of it.
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
git -C "$seed" checkout -qb feat/batch-b1 && printf 'a\n' > "$seed/a.txt" \
  && git -C "$seed" add -A && git -C "$seed" commit -qm "b1: the change" \
  && git -C "$seed" push -q origin feat/batch-b1 || fail "seed the batch branch"

# The driver's clone: this fixture.
git remote add origin "$origin" && git fetch -q origin \
  && git remote set-head origin main && git checkout -q -B main origin/main || fail "the clone"

state="$world/state"
mkdir -p "$state"
cat > "$state/judgements.yaml" <<'EOF2'
schema: 9
tiers: [{n: 1, title: Now}]
issues:
  super-fr#1074: {tier: 1}
batches:
  - id: b1
    title: b1
    ids: ["super-fr#1074"]
    wave: 1
    events:
      - {kind: dispatch, at: 2026-10-07T05:00:00Z, runner: herdr, handle: h, branch: feat/batch-b1}
EOF2
python3 - "$FAKE_FORGE" "$bare" "$config" <<'EOF2'
import json, sys
json.dump({"bare": sys.argv[2], "config": sys.argv[3], "label_defined": False,
           "pr": {"branch": "feat/batch-b1", "draft": False, "labels": [], "merged": False},
           "issue_labels": [], "comments": [], "pending": []}, open(sys.argv[1], "w"))
EOF2

forge() {  # forge <python statement over `w`>: the operator acts on the forge
  python3 - "$FAKE_FORGE" "$1" <<'EOF2'
import json, sys
w = json.load(open(sys.argv[1])); exec(sys.argv[2]); json.dump(w, open(sys.argv[1], "w"))
EOF2
}
drive() { run_fr out triage batch drive --once --yes --keep-sessions --repo "$repo" --dir "$state" \
  --checkout "$repo=$PWD"; }
board() {  # the board over the facts the last pass collected
  run_fr page triage backlog --repo "$repo" --dir "$state"; require_exit 0 "$page"
  cat "$state/backlog.html"
}
log() { cat "$FAKE_GH_LOG"; }
R="repos/$repo"

# 1. The label is created; an unlabelled green PR is held and the board asks for it.
drive
expect_grep "created label approved-fr on $repo" "$out" "the first pass creates the missing label"
refuse_grep "merged PR" "$out" "an unlabelled PR is never merged"
refuse_grep "pulls/1080/merge" "$(log)" "no merge call for an unlabelled PR"
page="$(board)"
expect_grep "label it approved-fr to merge" "$page" "the board's Needs you asks for the label"
expect_grep 'data-need="approve-pr"' "$page" "the ask is an approve-pr Need"
expect_grep "awaiting approval" "$(cat "$state/batches.html")" "the kanban card awaits approval"

# `batch merge` names the label when a named batch lacks it; nothing is written.
merge() { run_fr out triage batch merge "$@" --repo "$repo" --dir "$state" --checkout "$PWD"; }
before="$(cat "$state/judgements.yaml")"
merge b1 --yes
require_exit 2 "$out"
expect_grep "approved-fr" "$out" "naming an unapproved batch is refused naming the label"
refuse_grep "pulls/1080/merge" "$(log)" "batch merge never merges an unlabelled PR"
[ "$(cat "$state/judgements.yaml")" = "$before" ] || fail "an unapproved batch merge wrote state"

# 2. The operator labels it: the approval is recorded at the head, pinned to its patch-id.
forge 'w["pr"]["labels"] = ["approved-fr"]'
labelled="$(git -C "$bare" rev-parse feat/batch-b1)"
drive
expect_grep "approval of PR #1080 recorded at ${labelled:0:12}" "$out" "the approval is recorded at the head"
expect_grep "patch_id:" "$(cat "$state/judgements.yaml")" "the approval is pinned to the PR's diff"
refuse_grep "pulls/1080/merge" "$(log)" "fr merges nothing by the forge's API"
refuse_grep "kind: update|kind: enqueue" "$(cat "$state/judgements.yaml")" "no update or enqueue event is written"

# 3. A session pushes: the approval is void, the label removed, the board asks again.
git -C "$seed" fetch -q origin && git -C "$seed" checkout -q -B feat/batch-b1 origin/feat/batch-b1 \
  && printf 'session\n' >> "$seed/a.txt" && git -C "$seed" commit -qam "session push" \
  && git -C "$seed" push -q origin feat/batch-b1 || fail "the session push"
pushed="$(git -C "$bare" rev-parse feat/batch-b1)"
drive
# The approval recorded its patch-id (wave-merge-queue R12), and the push changed the
# PR's diff: the void says so.
expect_grep "approval of PR #1080 at ${labelled:0:12} voided: its diff changed at ${pushed:0:12}" \
  "$out" "a push fr did not make voids the approval"
expect_grep "^-X DELETE $R/issues/1080/labels/approved-fr" "$(log)" "the void removes the label"
refuse_grep "merged PR" "$out" "a void PR is never merged"
drive  # the next pass collects the PR without its label: still held, never voided twice
refuse_grep "voided|merged PR" "$out" "an unlabelled PR after a void is held, nothing more"
expect_grep "changed since you approved it at ${labelled:0:12}: re-label to merge" "$(board)" \
  "the board asks for a re-label"

# 4. The operator re-labels a draft: the approval is recorded again; nothing is merged.
forge 'w["pr"]["labels"] = ["approved-fr"]; w["pr"]["draft"] = True'
drive
expect_grep "approval of PR #1080 recorded at ${pushed:0:12}" "$out" "the new head is approved"
refuse_grep "pulls/1080/merge" "$(log)" "the approved PR is not merged by the forge's API"
refuse_grep "ready_for_review" "$(log)" "a draft is readied when the queue builds it, never by a pass"
echo "ok: merge-train-label-gate"
