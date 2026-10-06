#!/usr/bin/env bash
# Row prerelease-command-shape: `fr verification prerelease --dry-run` prints
# the workflow dispatch for a branch and its rc tag, and refuses on a
# non-GitHub forge. The remote is a LOCAL bare repo that git is told to treat
# as a public GitHub URL (insteadOf), so `ls-remote` is real and no forge, `gh`
# or network is ever reached: --dry-run calls nothing.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

remote=https://github.com/example-org/example-repo
bare="$(mktemp -d)/bare.git"
trap 'rm -rf "$(dirname "$bare")"' EXIT
git init -q --bare "$bare"
git checkout -q -B main
git remote add origin "$remote" 2>/dev/null || git remote set-url origin "$remote"
git config "url.$bare.insteadOf" "$remote"
git config user.email scenario@example.invalid
git config user.name scenario
echo a > a && git add a && git commit -qm a
git checkout -q -b feat/x
git push -q origin feat/x
sha="$(git rev-parse HEAD)"
tag="rc/feat-x/${sha:0:12}"

run_fr out verification prerelease --branch feat/x --dry-run
require_exit 0 "$out"
expect_grep 'gh workflow run prerelease.yml' "$out" "the dispatch command is printed"
expect_grep '-f branch=feat/x' "$out" "the dispatch names the branch"
expect_grep "-f sha=$sha" "$out" "the dispatch names the remote head"
expect_grep "$tag" "$out" "the rc tag is printed"
expect_grep "git\\+$remote@$tag" "$out" "the install source is printed as git+<remote>@<tag>"

# An unknown branch is refused rather than guessed at.
run_fr out verification prerelease --branch nope --dry-run
require_exit 2 "$out"

# A non-GitHub forge cannot dispatch the workflow: --dry-run refuses too.
mkdir -p .devcontainer
printf 'backend: gitlab\n' > .devcontainer/fr-profiles.yaml
run_fr out verification prerelease --branch feat/x --dry-run
require_exit 2 "$out"
expect_grep 'dispatch_workflow' "$out" "the refusal names the unsupported operation"
echo "ok: prerelease-command-shape"
