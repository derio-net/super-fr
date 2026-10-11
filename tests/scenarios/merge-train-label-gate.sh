#!/usr/bin/env bash
# Rows merge-train-label-gate, approval-label-created, approval-board-and-briefs (spec
# 2026-10-11-merge-train-safety R1-R5, R8). The host driver (`fr triage batch drive
# --once --yes`) against a fake REST forge (fixtures/merge-train-label-gate/bin/gh, its
# world in $FAKE_FORGE) and a real bare remote, where the driver's update pushes land. The
# clone reaches it by a `file://localhost/.../derio-net/super-fr.git` URL rather than
# `url.<base>.insteadOf`: `git remote get-url` expands insteadOf, and the driver reads the
# batch's repo from that URL. Five passes:
#   1. the label is missing: the pass creates it and says so; the PR is green and
#      unlabelled, so it is held as awaiting approval, and the board asks for the label;
#   2. the operator labels it while main moved ahead: the pass records the approval at the
#      head and updates the PR (an `update` event with the fetched base);
#   3. the driver's own update keeps the approval (its CI is still running);
#   4. a session pushes: the approval is void, the label removed (logged), and the board
#      asks for a re-label;
#   5. the operator re-labels a draft: the pass marks it ready and merges it.
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
  run_fr page triage render --repo "$repo" --dir "$state"; require_exit 0 "$page"
  cat "$state/triage.html"
}
log() { cat "$FAKE_GH_LOG"; }
R="repos/$repo"

# 1. The label is created; an unlabelled green PR is held and the board asks for it.
drive
expect_grep "created label approved-fr on $repo" "$out" "the first pass creates the missing label"
expect_grep "awaiting approval b1 \(#1080\)" "$out" "the unlabelled green PR awaits approval"
refuse_grep "merged PR" "$out" "an unlabelled PR is never merged"
refuse_grep "pulls/1080/merge" "$(log)" "no merge call for an unlabelled PR"
expect_grep "label it approved-fr to merge" "$(board)" "the board's Needs you asks for the label"

# 2. The operator labels it; main has moved: the approval is recorded and fr updates it.
forge 'w["pr"]["labels"] = ["approved-fr"]'
git -C "$seed" checkout -q main && printf 'more code\n' >> "$seed/code.py" \
  && git -C "$seed" commit -qam "main moves" && git -C "$seed" push -q origin main || fail "move main"
labelled="$(git -C "$bare" rev-parse feat/batch-b1)"
drive
expect_grep "approval of PR #1080 recorded at ${labelled:0:12}" "$out" "the approval is recorded at the head"
expect_grep "updated PR #1080" "$out" "the PR behind main is updated"
updated="$(git -C "$bare" rev-parse feat/batch-b1)"
[ "$updated" != "$labelled" ] || fail "the update pushed nothing"
expect_grep "head_before: $labelled" "$(cat "$state/judgements.yaml")" "the update is recorded"
expect_grep "head_after: $updated" "$(cat "$state/judgements.yaml")" "the update names its new head"

# 3. fr's own update keeps the approval while its CI runs.
forge "w['pending'] = ['$updated']"
drive
refuse_grep "voided" "$out" "the driver's own update does not void the approval"
refuse_grep "issues/1080/labels" "$(log)" "the label stays on after fr's own update"
refuse_grep "merged PR" "$out" "a pending PR waits"

# 4. A session pushes: the approval is void, the label removed, the board asks again.
git -C "$seed" fetch -q origin && git -C "$seed" checkout -q -B feat/batch-b1 origin/feat/batch-b1 \
  && printf 'session\n' >> "$seed/a.txt" && git -C "$seed" commit -qam "session push" \
  && git -C "$seed" push -q origin feat/batch-b1 || fail "the session push"
pushed="$(git -C "$bare" rev-parse feat/batch-b1)"
forge 'w["pending"] = []'
drive
expect_grep "approval of PR #1080 at ${labelled:0:12} voided: head moved to ${pushed:0:12}" \
  "$out" "a push fr did not make voids the approval"
expect_grep "^-X DELETE $R/issues/1080/labels/approved-fr" "$(log)" "the void removes the label"
refuse_grep "merged PR" "$out" "a void PR is never merged"
drive  # the next pass collects the PR without its label: still held, never voided twice
refuse_grep "voided|merged PR" "$out" "an unlabelled PR after a void is held, nothing more"
expect_grep "awaiting approval b1 \(#1080\)" "$out" "the unlabelled PR awaits approval again"
expect_grep "changed since you approved it at ${labelled:0:12}: re-label to merge" "$(board)" \
  "the board asks for a re-label"

# 5. The operator re-labels a draft: fr marks it ready and merges it.
forge 'w["pr"]["labels"] = ["approved-fr"]; w["pr"]["draft"] = True'
drive
expect_grep "^-X POST $R/pulls/1080/ccr/ready_for_review" "$(log)" "the approved draft is marked ready"
expect_grep "^-X PUT $R/pulls/1080/merge" "$(log)" "the approved PR is merged"
expect_grep "merged PR #1080 at ${pushed:0:12}" "$out" "the merge names the approved head"
echo "ok: merge-train-label-gate"
