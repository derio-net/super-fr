#!/usr/bin/env bash
# Row placement-fr-enabled (spec 2026-11-04-repo-feature-settings R26; plan
# 2026-11-12-placement-resolver phase 6).
#
# A quiet repo keeps no devcontainer profile and no plans dir in its checkout, so the
# legacy test called it "not fr-enabled" and the edit gate let every base-clone edit
# through. Here: a repo whose origin/fr says `placement: quiet` and nothing else. Sourcing
# the shell decision library, `fr_isolation_decide_edit` denies an edit in the base clone
# and allows one in an `up` workspace, and it still denies with no `fr` on PATH (the direct
# checks do not need it). An `fr` branch without the switch leaves the repo not fr-enabled.
# A stealth marker makes a workspace fr-enabled by the marker alone. Nothing reaches a forge.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
LIB="$here/../../plugins/super-fr/hooks/lib/fr-isolation-decision.sh"
[ -r "$LIB" ] || fail "no decision library at $LIB"

HOME="$(mktemp -d)" && export HOME
export FR_ISOLATION_TARGET=worktree
unset FR_BASE_OK
base="$(pwd)"
origin="$(mktemp -d)/origin.git"
git init -q --bare -b main "$origin" || fail "bare origin"
git symbolic-ref HEAD refs/heads/main || fail "branch main"
git remote add origin "$origin"
echo seed > README.md
git add -A && git commit -qm seed || fail "seed commit"
git push -q -u origin main || fail "seed push"
git remote set-head origin main >/dev/null
repo="$(basename "$(git rev-parse --show-toplevel)")"
[ ! -d .devcontainer ] && [ ! -d docs/superpowers/plans ] || fail "the fixture must have no profile and no plans dir"

# decide <dir> <file> [env...]: the library's edit decision in a clean shell (0 allow, 1 deny)
decide() {
  local dir="$1" file="$2"; shift 2
  ( cd "$dir" && env "$@" bash -c '. "$1"; fr_isolation_decide_edit "$2"' _ "$LIB" "$file" )
}
FRBIN="$(dirname "$(command -v fr)")"
GITBIN="$(dirname "$(command -v git)")"
NOFR_PATH="$GITBIN:/usr/bin:/bin"
case ":$NOFR_PATH:" in *":$FRBIN:"*) [ "$FRBIN" = "$GITBIN" ] && fail "fr and git share a bin dir: cannot hide fr" ;; esac

# 1. not quiet yet: not fr-enabled, so the base-clone edit is allowed
decide "$base" "$base/README.md" "PATH=$PATH" || fail "a repo with no switch must not be fr-enabled"

# 2. the quiet switch, with fr and without it
run_fr out settings init --quiet
require_exit 0 "$out"
git fetch -q origin || fail "fetch"
git rev-parse --verify -q refs/remotes/origin/fr >/dev/null || fail "no origin/fr after the switch"
decide "$base" "$base/README.md" "PATH=$PATH" && fail "quiet: the base-clone edit was allowed (fr on PATH)"
decide "$base" "$base/README.md" "PATH=$NOFR_PATH" && fail "quiet: the base-clone edit was allowed with no fr"

# 3. an `up` workspace is the valid marker: its edits are allowed
run_fr out isolation up --branch feat/a
require_exit 0 "$out"
wt="$HOME/.cache/fr/worktrees/$repo/feat__a"
[ -d "$wt" ] || fail "no workspace at $wt: $out"
decide "$wt" "$wt/README.md" "PATH=$PATH" || fail "quiet: an edit in the up workspace was denied"
decide "$wt" "$wt/README.md" "PATH=$NOFR_PATH" || fail "quiet: an edit in the up workspace was denied with no fr"
grep -q '"placement": "quiet"' "$wt/.fr-isolation" || fail "the marker does not record the quiet placement"

# 4. an fr branch without the switch is not fr-enabled
plain="$(mktemp -d)/plain"
git init -q -b main "$plain" && cd "$plain" || fail "plain repo"
git remote add origin "$origin"
echo x > f.txt && git add -A && git commit -qm x || fail "plain commit"
blob="$(printf 'placement: repo\n' | git hash-object -w --stdin)"
tree="$(printf '100644 blob %s\tsettings.yaml\n' "$blob" | git mktree)"
commit="$(git commit-tree "$tree" -m "no switch")"
git update-ref refs/remotes/origin/fr "$commit"
decide "$plain" "$plain/f.txt" "PATH=$NOFR_PATH" || fail "an fr branch without the switch denied an edit"

# 5. a stealth marker makes the workspace fr-enabled by itself (no switch, no fr)
steal="$(mktemp -d)/steal"
git init -q -b main "$steal" && cd "$steal" || fail "stealth repo"
echo x > f.txt && git add -A && git commit -qm x || fail "stealth commit"
printf '{"toplevel": "%s", "branch": "main", "mode": "worktree", "placement": "stealth"}\n' \
  "$(pwd -P)" > .fr-isolation
decide "$steal" "$steal/f.txt" "PATH=$NOFR_PATH" && fail "a stealth marker in a primary tree must deny, not allow"
echo "ok: placement-fr-enabled"
