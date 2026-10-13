#!/usr/bin/env bash
# Rows merge-train-queue and ci-merge-group-trigger (spec 2026-10-11-merge-train-safety
# R12, R13, R15). The host driver (`fr triage batch drive --once --yes`) against the fake
# REST forge of merge-train-label-gate (its world in $FAKE_FORGE, `queue` key) and a real
# bare remote. Under `forge.api rest`, which cannot enqueue:
#   A. the base's ruleset has a merge_queue rule: the pass holds the repo and says "forge.api
#      rest cannot enqueue" (the approved, green PR is neither merged nor enqueued);
#   B. the rule is gone: the same PR merges as it always did (the train is unchanged).
# The GraphQL enqueue and ejection path has no live forge here: unit tests cover it. The
# workflows' merge_group triggers are checked from the shipped files.
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
json.dump({"bare": sys.argv[2], "config": sys.argv[3], "label_defined": True, "queue": True,
           "pr": {"branch": "feat/batch-b1", "draft": False, "labels": ["approved-fr"],
                  "merged": False},
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
log() { cat "$FAKE_GH_LOG"; }
R="repos/$repo"

# A. A merge queue is required and forge.api is rest: the repo is held, nothing merges.
drive
expect_grep "held b1: $repo requires a merge queue, and forge.api rest cannot enqueue" "$out" \
  "a queue repo under forge.api rest is held with the spec's words"
refuse_grep "merged PR" "$out" "a held queue repo is never merged directly"
refuse_grep "pulls/1080/merge" "$(log)" "no merge call under a merge queue"
expect_grep "rules/branches/main" "$(log)" "the driver read the base's rules"

# B. No queue rule: the same approved, green PR merges as before.
forge 'w["queue"] = False'
drive
expect_grep "^-X PUT $R/pulls/1080/merge" "$(log)" "without a queue the PR is merged"
expect_grep "merged PR #1080" "$out" "the merge is reported"
refuse_grep "merge queue" "$out" "no queue hold once the rule is gone"

# R15: both workflows build merge groups.
root="$(cd "$here/../.." && pwd)"
for wf in ci acceptance-report; do
  grep -q "^  merge_group" "$root/.github/workflows/$wf.yml" || fail "$wf.yml lacks merge_group"
done
echo "ok: merge-train-queue"
