#!/usr/bin/env bash
# Row triage-adopt-list-columns: `fr triage batch adopt --list` prints its header, then one
# tab-separated row per runner tab with the state, repo, branch, PR and classified refs.
# herdr and gh are fakes replaying shapes (fixtures/triage-adopt-list/, projected from
# captured herdr and REST output, names redacted); the two agents sit in throwaway clones
# whose origin URL names example-org/widgets. Nothing here reaches a forge or herdr.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
export HERDR_FAKE_LOG="$work/herdr.log" FAKE_GH_LOG="$work/gh.log"
: > "$HERDR_FAKE_LOG"
export HERDR_ENV=1 HERDR_PANE_ID=w0:p0 HERDR_WORKSPACE_ID=w7
export FR_FORGE_API=rest FR_HOST_ID=0123456789abcdef
export PATH="$here/fixtures/triage-adopt-list/bin:$PATH"

clone() { # <dir> <branch>
  git init -q -b main "$1"
  git -C "$1" commit -q --allow-empty -m init
  git -C "$1" remote add origin https://github.com/example-org/widgets.git
  git -C "$1" symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main
  [ "$2" = main ] || git -C "$1" checkout -q -b "$2"
}
clone "$work/feat" feat/hand-started
clone "$work/main" main
export LIST_FEAT="$work/feat" LIST_MAIN="$work/main"

run_fr out triage batch adopt --list
require_exit 0 "$out"
tab="$(printf '\t')"
expect_grep "^TAB${tab}WORKSPACE${tab}STATUS${tab}STATE${tab}REPO${tab}BRANCH${tab}FR WORKSPACE${tab}PR${tab}REFS${tab}LABEL\$" "$out" "the header line"
expect_grep "^w7:t5${tab}.*${tab}adoptable${tab}example-org/widgets${tab}feat/hand-started${tab}.*${tab}#40 closes widgets#1${tab}" "$out" "the adoptable row, with its PR and what it closes"
expect_grep "${tab}example-org/widgets#1 \\(issue\\), #40 \\(pr\\)${tab}" "$out" "refs are classified through the forge"
expect_grep "^w7:t6${tab}.*${tab}on default branch${tab}example-org/widgets${tab}main${tab}.*${tab}-${tab}widgets#1 \\(issue\\)${tab}" "$out" "the default-branch row has no PR column"
if grep -Eq 'tab rename|agent rename|agent start|send-text|prompt' "$HERDR_FAKE_LOG"; then
  cat "$HERDR_FAKE_LOG" >&2; fail "a listing wrote to herdr"
fi
echo "ok: triage-adopt-list"
