#!/usr/bin/env bash
# Row batch-merge-skip-held (spec 2026-10-11-merge-train-safety R7). `fr triage batch merge`
# with no ids skips each queued batch another scope holds, naming it, and merges the rest;
# with every batch held it says "nothing to merge" and exits 0; naming a held batch still
# refuses with exit 2. The fake REST forge and the bare remote are those of
# merge-train-label-gate. Batch b1 (issue 1074, PR 1080: green, labelled approved-fr, up to
# date) is the free one. Batch b2 (issue 9999, PR 1081) exists only in the collected facts,
# with another scope's live claim on its issue; the facts edit goes through the model's own
# serializer, and the forge is never asked about b2, which is skipped before any read.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
export FR_HOST_ID=0123456789abcdef FR_FORGE_API=rest
export PATH="$here/fixtures/merge-train-label-gate/bin:$PATH"
repo=derio-net/super-fr
py="$(candidate_python)"

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
  super-fr#9999: {tier: 1}
batches:
  - id: b1
    title: b1
    ids: ["super-fr#1074"]
    wave: 1
    events:
      - {kind: dispatch, at: 2026-10-07T05:00:00Z, runner: herdr, handle: h, branch: feat/batch-b1}
  - id: b2
    title: b2
    ids: ["super-fr#9999"]
    wave: 1
    events:
      - {kind: dispatch, at: 2026-10-07T05:00:00Z, runner: herdr, handle: h2, branch: feat/batch-b2}
EOF2
python3 - "$FAKE_FORGE" "$bare" "$config" <<'EOF2'
import json, sys
json.dump({"bare": sys.argv[2], "config": sys.argv[3], "label_defined": True,
           "pr": {"branch": "feat/batch-b1", "draft": False, "labels": ["approved-fr"],
                  "merged": False},
           "issue_labels": [], "comments": [], "pending": []}, open(sys.argv[1], "w"))
EOF2

run_fr out triage collect --repo "$repo" --dir "$state"; require_exit 0 "$out"
# b2's issue and PR, and another scope's live claim on b2's issue (and, in `held`, b1's).
cat > "$world/facts.py" <<'EOF2'
import json
import sys

from fr.triage.model import Issue, IssueClaim, PullRequest, load_facts

path, hold_b1 = sys.argv[1], sys.argv[2] == "yes"
facts = load_facts(path)
repo = "derio-net/super-fr"
claim = IssueClaim(signer="s-aaaaaaaa", batch="their-batch", claimed="2026-10-11T00:00:00Z",
                   heartbeat="2026-10-11T00:00:00Z", expires="2099-01-01T00:00:00Z",
                   comment_id=101, created_at="2026-10-11T00:00:00Z")
pr = PullRequest(repo=repo, number=1081, title="b2", state="OPEN", is_draft=False,
                 created_at="2026-10-08T00:00:00Z", url=f"https://github.com/{repo}/pull/1081",
                 head_ref="feat/batch-b2", head_oid="b" * 40, author=facts.viewer,
                 cross_repo=False, files=["b.py"], checks={"pass": 1, "fail": 0, "pending": 0},
                 labels=["approved-fr"])
issues = [i for i in facts.issues if i.number != 9999]
issues = [i.model_copy(update={"claims": [claim] if hold_b1 else []}) if i.number == 1074 else i
          for i in issues]
issues.append(Issue(repo=repo, number=9999, title="held elsewhere", state="open",
                    url=f"https://github.com/{repo}/issues/9999", prs=[pr], claims=[claim]))
prs = [p for p in facts.prs if p.number != 1081] + [pr]
open(path, "w").write(
    json.dumps(facts.model_copy(update={"issues": issues, "prs": prs}).to_json())
)
EOF2
hold() { "$py" "$world/facts.py" "$state/facts.json" "$1"; }
merge() { run_fr out triage batch merge "$@" --repo "$repo" --dir "$state" --checkout "$PWD"; }
log() { cat "$FAKE_GH_LOG"; }
R="repos/$repo"

# Every queued batch held: each named, "nothing to merge", exit 0, no forge write.
hold yes
merge --yes
require_exit 0 "$out"
expect_grep "skipped b1: held by s-aaaaaaaa" "$out" "b1 is skipped and named"
expect_grep "skipped b2: held by s-aaaaaaaa" "$out" "b2 is skipped and named"
expect_grep "nothing to merge" "$out" "with every batch held there is nothing to merge"
refuse_grep "pulls/1080/merge" "$(log)" "nothing is merged"

# Naming a held batch refuses, exit 2, and writes nothing.
before="$(cat "$state/judgements.yaml")"
merge b2 --yes
require_exit 2 "$out"
expect_grep "s-aaaaaaaa" "$out" "the refusal names the holder"
[ "$(cat "$state/judgements.yaml")" = "$before" ] || fail "a refused merge wrote state"

# Only b2 held: b2 is skipped and b1 merges.
hold no
merge --yes
require_exit 0 "$out"
expect_grep "skipped b2: held by s-aaaaaaaa" "$out" "b2 is skipped and named"
refuse_grep "skipped b1" "$out" "the free batch is not skipped"
expect_grep "^-X PUT $R/pulls/1080/merge" "$(log)" "the free batch's PR is merged"
echo "ok: batch-merge-skip-held"
