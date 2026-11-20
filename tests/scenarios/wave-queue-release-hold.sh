#!/usr/bin/env bash
# Row wave-queue-release-hold: `fr release status --from-json` judges a merge queue's hold
# (spec 2026-11-19-wave-merge-queue R17, R18). Over the facts release.py reads, a fresh
# `open` hold is reported held, naming its scope and wave; an `open` hold refreshed more
# than 24 hours ago is ignored with a warning that names it; a `drained` and a `cleared`
# hold never hold. fr decides from the facts alone: no forge, no credential, nothing
# written. The fixture is a fresh `git init` with no remote.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

git init -q -b main . || fail "git init"
before="$(git status --porcelain)"
facts_dir="$(mktemp -d)"   # the facts live outside the fixture, which must stay unwritten
facts_file="$facts_dir/facts.json"

iso_ago() { # <hours>: the UTC time that many hours ago, ISO 8601
  python3 - "$1" <<'PY'
import sys
from datetime import UTC, datetime, timedelta
print((datetime.now(UTC) - timedelta(hours=float(sys.argv[1]))).strftime("%Y-%m-%dT%H:%M:%SZ"))
PY
}

# facts <state> <hours-ago>: the facts file release.py writes, with a hold of <state> last
# refreshed <hours-ago> hours ago, over no merged PR.
facts() {
  cat > "$facts_file" <<JSON
{"repo": "example-org/demo", "last_final": null, "since": null, "prs": [],
 "hold": {"state": "$1", "scope": "s-11111111", "wave": 3, "opened": "$(iso_ago 5)",
          "refreshed": "$(iso_ago "$2")", "parent": "$(git hash-object -t tree /dev/null)"}}
JSON
}

# an open hold refreshed an hour ago: held, naming the scope and the wave
facts open 1
run_fr out release status --from-json "$facts_file" --json
require_exit 0 "$out"
expect_grep '"held": \{' "$out" "a fresh open hold holds the release"
expect_grep '"scope": "s-11111111"' "$out" "it names the scope"
expect_grep '"wave": 3' "$out" "it names the wave"
run_fr out release status --from-json "$facts_file"
require_exit 0 "$out"
expect_grep 'held: the merge queue of scope s-11111111 \(wave 3\)' "$out" "the text says so too"

# an open hold refreshed 25 hours ago: warned, not held
facts open 25
run_fr out release status --from-json "$facts_file" --json
require_exit 0 "$out"
expect_grep '"held": null' "$out" "an open hold older than 24 hours holds nothing"
expect_grep 'refreshed .* more than 24 hours ago' "$out" "it warns, naming the hold"
expect_grep 's-11111111' "$out" "the warning names the scope"

# drained and cleared holds never hold, however fresh
for state in drained cleared; do
  facts "$state" 0
  run_fr out release status --from-json "$facts_file" --json
  require_exit 0 "$out"
  expect_grep '"held": null' "$out" "a $state hold never holds a release"
  refuse_grep 'more than 24 hours' "$out" "a $state hold is not a stale open one"
done

[ "$(git status --porcelain)" = "$before" ] || fail "fr release status wrote into the repo"
echo "ok: wave-queue-release-hold"
