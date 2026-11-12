#!/usr/bin/env bash
# Row repo-settings-forge-quiet: a repo whose origin main carries
# `forge: {labels: off, comments: off, issues: off}` files nothing. `fr journal file`
# on an out-of-scope finding refuses naming the setting, `fr debt issue --yes` skips
# naming it, and the recording `gh` (fixtures/repo-settings-forge-quiet/bin/gh) logs no
# issue, label or comment call. The fixture is a fresh `git init` whose origin url names
# a github.com repo, served from a local bare repo through `insteadOf` — no real forge.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
export PATH="$here/fixtures/repo-settings-forge-quiet/bin:$PATH"

world="$(mktemp -d)"
trap 'rm -rf "$world"' EXIT
export FAKE_GH_LOG="$world/gh.log"
: > "$FAKE_GH_LOG"

git init -q --bare -b main "$world/origin.git" || fail "bare origin"
git symbolic-ref HEAD refs/heads/main || fail "branch main"
git remote add origin https://github.com/example-org/widgets.git
git config url."$world/origin.git".insteadOf https://github.com/example-org/widgets.git
echo seed > README.md
mkdir -p .fr
printf 'forge:\n  labels: off\n  comments: off\n  issues: off\n' > .fr/settings.yaml
git add -A && git commit -qm "seed with settings" || fail "seed commit"
git push -q -u origin main || fail "seed push"
git remote set-head origin main >/dev/null

git checkout -qb feat/quiet
run_fr out journal add --scope debug --slug quiet --kind finding --id f1 \
  --title "old debt" --body "predates this change" --state open --review-scope out
require_exit 0 "$out"
run_fr out journal resolve --scope debug --slug quiet --id f1 --state out-of-scope \
  --note "not this change's"
require_exit 0 "$out"

run_fr out journal file --scope debug --slug quiet --id f1
require_exit 2 "$out"
expect_grep 'refused, nothing filed' "$out" "journal file refuses"
expect_grep 'forge\.issues: off' "$out" "journal file names the setting"

run_fr out debt issue --yes
require_exit 0 "$out"
expect_grep 'skipped' "$out" "debt issue skips"
expect_grep 'forge\.issues: off' "$out" "debt issue names the setting"

calls="$(cat "$FAKE_GH_LOG")"
refuse_grep 'issue (create|edit|close|comment)|label|pr (comment|edit)|issues/|comments' \
  "$calls" "a forge write reached gh under forge quiet"
echo "ok: repo-settings-forge-quiet"
