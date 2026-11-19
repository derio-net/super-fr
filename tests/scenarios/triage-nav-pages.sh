#!/usr/bin/env bash
# Row triage-nav-present-pages: every triage page's nav lists only the pages present in
# the state dir, and a render brings the nav of the pages already there into agreement.
# Org scope, facts only: render the backlog, then history, then the board; history.html's
# nav must then name Backlog, Issues, Batches and History and no page may link
# origins/architecture.
# The facts are fixtures/config-skew-facts.json (any valid org-scope facts would do).
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

state="$(mktemp -d)"
trap 'rm -rf "$state"' EXIT
cp "$here/fixtures/config-skew-facts.json" "$state/facts.json"

run_fr out triage backlog --org example-org --dir "$state"
require_exit 0 "$out"
run_fr out triage history render --org example-org --dir "$state"
require_exit 0 "$out"

nav() { grep -o '<nav class="pages"[^>]*>.*</nav>' "$state/$1" | grep -o '>[A-Za-z]*</a>' | sed 's/^>//; s/<\/a>$//' | tr '\n' ' '; }
[ "$(nav history.html)" = "Backlog Issues History " ] || fail "before the board, history.html's nav is: $(nav history.html)"

run_fr out triage batches --org example-org --dir "$state"
require_exit 0 "$out"

for page in backlog.html issues.html batches.html history.html; do
  got="$(nav "$page")"
  [ "$got" = "Backlog Issues Batches History " ] || fail "$page nav is '$got', want 'Backlog Issues Batches History '"
  html="$(cat "$state/$page")"
  refuse_grep 'origins\.html' "$html" "$page links no origins page that was never rendered"
  refuse_grep 'architecture\.html' "$html" "$page links no architecture page that was never rendered"
done
html="$(cat "$state/history.html")"
expect_grep 'href="history.html" aria-current="page"' "$html" "history.html marks itself current"
echo "ok: triage-nav-pages"
