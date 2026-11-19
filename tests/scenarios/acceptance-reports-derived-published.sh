#!/usr/bin/env bash
# Row acceptance-reports-derived-published (spec 2026-11-04-repo-feature-settings R20-R22):
# in a fresh repo with a GitHub-shaped origin and NO forge token, `fr acceptance init
# --with-ci` cannot read the Pages visibility, so it fails closed: the workflow has no Pages
# job, and the README badge points at the latest CI run, between its markers. Running it
# again changes nothing. `fr acceptance report` then writes the derived report, which git
# ignores, so the tree stays clean; and `check` fails once a report file is tracked.
# Portable: no GNU-only flags (no `sed -i`; BSD/macOS and GNU userlands alike).
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

# No forge is reachable: a token that cannot authenticate, whatever the machine has.
export GH_TOKEN=scenario-no-forge-token GITHUB_TOKEN=scenario-no-forge-token

git symbolic-ref HEAD refs/heads/main || fail "name the default branch main"
git remote add origin https://github.com/example-org/widgets.git || fail "remote"
printf '# widgets\n\nA fixture.\n' > README.md
git add -A && git commit -qm seed || fail "seed commit"
git checkout -qb feat/reports || fail "work off the default branch"

# Hermetic pin: `init --with-ci` pins the install line to the commit of the installed fr's
# release tag, read with `git ls-remote` from github.com. Here a local bare repo holds that
# annotated tag, and a scratch HOME's gitconfig rewrites the URL to it (the read keeps HOME).
# No network, and it works before the version is tagged (release.yml's pre-tag suite).
world="$(cd "$(mktemp -d)" && pwd -P)"
export HOME="$world/home"; mkdir -p "$HOME"
version="$(fr --version | grep -Eo '[0-9]+\.[0-9]+\.[0-9]+(rc[0-9]+)?' | head -1)"
[ -n "$version" ] || fail "no version from fr --version"
tag="v$(printf '%s' "$version" | sed -E 's/^([0-9]+\.[0-9]+\.[0-9]+)rc([0-9]+)$/\1-rc.\2/')"
git init -q "$world/seed" || fail "seed repo"
git -C "$world/seed" -c user.name=s -c user.email=s@example.invalid commit -q --allow-empty -m release || fail "seed commit"
git -C "$world/seed" -c user.name=s -c user.email=s@example.invalid tag -a "$tag" -m "$tag" || fail "annotated tag"
sha="$(git -C "$world/seed" rev-parse "$tag^{commit}")"
git clone -q --bare "$world/seed" "$world/super-fr.git" || fail "bare repo"
printf '[url "file://%s"]\n\tinsteadOf = https://github.com/derio-net/super-fr\n' "$world/super-fr.git" > "$HOME/.gitconfig"

run_fr out acceptance init --with-ci
require_exit 0 "$out"
wf=".github/workflows/acceptance-report.yml"
[ -f "$wf" ] || fail "init wrote no workflow"
workflow="$(cat "$wf")"
expect_grep 'fr acceptance check' "$workflow" "the workflow gates"
expect_grep 'fr acceptance summary' "$workflow" "the job summary is written"
expect_grep 'fetch-depth: 0' "$workflow" "the fold gets full history"
case "$workflow" in
  *"super-fr@$sha#subdirectory=packages/fr\"  # $tag"*) ;;
  *) fail "the workflow does not pin fr to $tag ($sha)" ;;
esac
refuse_grep 'pages-check|deploy-pages|pages:' "$workflow" "no Pages job when visibility is unknown"
readme="$(cat README.md)"
expect_grep '<!-- fr:acceptance-badge -->' "$readme" "the badge opens"
expect_grep '<!-- /fr:acceptance-badge -->' "$readme" "the badge closes"
expect_grep 'actions/workflows/acceptance-report.yml' "$readme" "the badge points at the CI run"
refuse_grep 'github\.io' "$readme" "no Pages link"

before="$(cat README.md)"
run_fr out acceptance init --with-ci
require_exit 0 "$out"
[ "$(cat README.md)" = "$before" ] || fail "a second init changed the README"

git add -A; git commit -qm "scaffold" 2>/dev/null
run_fr out acceptance report
require_exit 0 "$out"
[ -f docs/acceptance/report.html ] || fail "no report was written"
status="$(git status --porcelain)"
[ -z "$status" ] || fail "the report dirtied the tree: $status"
run_fr out acceptance report --format md
require_exit 0 "$out"
[ -f docs/acceptance/report.md ] || fail "no Markdown report"
[ -z "$(git status --porcelain)" ] || fail "the Markdown report dirtied the tree"

run_fr out acceptance pages-check
require_exit 1 "$out"
expect_grep 'Pages are not published' "$out" "pages-check says why"

git add -f docs/acceptance/report.html && git commit -qm "commit a report" || fail "commit a report"
run_fr out acceptance check
[ "$RC" -ne 0 ] || fail "check passed with a tracked report"
expect_grep 'reports are derived; remove docs/acceptance/report.html' "$out" "check names the file"

echo "ok: acceptance-reports-derived-published"
