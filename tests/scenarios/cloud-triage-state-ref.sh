#!/usr/bin/env bash
# Row cloud-triage-state-ref: a scope's state lives in the workspace, out of git, and its
# durable copy is the ref refs/fr/triage/<scope-id> (spec 2026-10-07-cloud-triage R4, R5).
# Workspace A (the fixture `git init`) writes every REF_FILES entry, leaves `git status`
# clean, and pushes to a bare remote; a second, empty workspace B with the same
# FR_HOST_ID restores every entry byte for byte, and facts.json never travels. The one
# forge read (the privacy guard's `GET repos/derio-net/super-fr` before the push) is a
# fake gh answering with the captured repo record (fixtures/cloud-triage-state/bin/gh).
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
export FR_HOST_ID=0123456789abcdef FR_FORGE_API=rest
export PATH="$here/fixtures/cloud-triage-state/bin:$PATH"
repo=derio-net/super-fr
scope=derio-net--super-fr

world="$(mktemp -d)"
trap 'rm -rf "$world"' EXIT
export HOME="$world/home" FAKE_GH_LOG="$world/gh.log"
mkdir -p "$HOME"
git init -q --bare "$world/state.git" || fail "bare remote"
a="$PWD"

run_fr out triage batch list --repo "$repo"
require_exit 0 "$out"
state="$a/.fr/triage-state/$scope"
grep -qx '.fr/triage-state/' "$(git rev-parse --git-common-dir)/info/exclude" \
  || fail "info/exclude does not keep the state out of git"

mkdir -p "$state"/{board,origins,architecture,history,snapshots,authored-src}
printf 'schema: 6\ntiers: [{n: 1, title: Now}]\nissues:\n  "super-fr#1": {tier: 1}\n' > "$state/judgements.yaml"
printf 'schema: 2\n' > "$state/origins.yaml"
printf 'subsystems: []\n' > "$state/subsystems.yaml"
for d in board origins architecture history; do printf 'fragments: []\n' > "$state/$d/manifest.yaml"; done
printf '{}\n' > "$state/snapshots/2026-10-08.json"
printf '# notes\n' > "$state/authored-src/notes.md"
printf '{"stops": []}\n' > "$state/merge-stops.json"
for f in lease requests sessions rehomes; do printf '%s: []\n' "$f" > "$state/$f.yaml"; done
printf 'state_repo: %s\nforge_api: rest\n' "$repo" > "$state/scope-durable.yaml"
printf '{"not": "durable"}\n' > "$state/facts.json"
[ -z "$(git status --porcelain --untracked-files=all)" ] || fail "the state shows in git status"

run_fr out triage state push --repo "$repo" --remote "$world/state.git"
require_exit 0 "$out"
ref="$(git -C "$world/state.git" for-each-ref --format='%(refname)' refs/fr/triage/)"
expect_grep '^refs/fr/triage/s-[0-9a-f]{8}$' "$ref" "the push wrote the scope's ref"
refuse_grep 'triage' "$(git -C "$world/state.git" branch -a)" "the ref is no branch"
expect_grep "^repos/$repo\$" "$(cat "$FAKE_GH_LOG")" "the push read the state repo's visibility"
[ -z "$(git status --porcelain --untracked-files=all)" ] || fail "the push changed git status"

b="$world/b"
git init -q "$b" || fail "workspace B"
cd "$b" || fail "cd B"
run_fr out triage state fetch --repo "$repo" --remote "$world/state.git" --state-repo "$repo"
require_exit 0 "$out"
expect_grep "^restored $ref " "$out" "the fetch names the ref it restored"
restored="$b/.fr/triage-state/$scope"
for rel in judgements.yaml origins.yaml subsystems.yaml board/manifest.yaml \
  origins/manifest.yaml architecture/manifest.yaml history/manifest.yaml \
  snapshots/2026-10-08.json authored-src/notes.md merge-stops.json lease.yaml \
  scope-durable.yaml requests.yaml sessions.yaml rehomes.yaml; do
  cmp -s "$state/$rel" "$restored/$rel" || fail "$rel was not restored byte for byte"
done
[ ! -e "$restored/facts.json" ] || fail "facts.json travelled on the ref"
grep -qx 'api: rest' "$HOME/.config/fr/forge.yaml" || fail "the restore did not write forge.api"
expect_grep "state_repo: \"$repo\"" "$(cat "$restored/scope.yaml")" "scope.yaml mirrors the state repo"
[ -z "$(git status --porcelain --untracked-files=all)" ] || fail "the restore shows in git status"
echo "ok: cloud-triage-state-ref"
