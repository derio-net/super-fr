#!/usr/bin/env bash
# Row placement-stealth: the stealth placement end to end (spec
# 2026-11-04-repo-feature-settings R2, R3, R5, R24). A target repo with a local bare origin
# and a separate local bare tracking repo: `fr settings init --stealth` pushes the target's
# settings file to the tracking branch; `fr isolation up --stealth` (host worktree)
# records stealth; a plan, a journal entry and a run cursor land in the tracking repo
# under local--origin/features/feat__s/, a code commit goes to the target with `fr push`.
# Then: the target's remote holds only the code commit (no fr path, no chore(fr)
# subject, no fr ref); a second HOME resumes the run from the tracking repo; the tracking
# repo removed mid-run makes the next resolve exit 2. Nothing reaches a forge.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
scenario_require_fresh_repo

HOME="$(mktemp -d)" && export HOME           # the worktrees and the tracking clone
export FR_ISOLATION_TARGET=worktree
base="$(mktemp -d)"
origin="$base/origin.git"
track="$base/track.git"
git init -q --bare -b main "$origin" || fail "bare origin"
git symbolic-ref HEAD refs/heads/main || fail "branch main"
git remote add origin "$origin"
echo seed > README.md
git add -A && git commit -qm seed || fail "seed commit"
git push -q -u origin main || fail "seed push"
git remote set-head origin main >/dev/null
target="$(git rev-parse --show-toplevel)"
repo="$(basename "$target")"

git init -q --bare -b main "$track" || fail "bare tracking repo"
seed="$base/track-seed"
git init -q -b main "$seed" && echo tracking > "$seed/README.md" \
  && git -C "$seed" add -A && git -C "$seed" commit -qm seed \
  && git -C "$seed" push -q "$track" main || fail "seed the tracking repo"

run_fr out settings init --stealth "$track@main"
require_exit 0 "$out"
git --git-dir="$track" show main:local--origin/settings.yaml | grep -qx 'placement: stealth' \
  || fail "the tracking branch lacks local--origin/settings.yaml saying placement: stealth"

run_fr out isolation up --branch feat/s --stealth "$track@main"
require_exit 0 "$out"
wt="$HOME/.cache/fr/worktrees/$repo/feat__s"
[ -d "$wt" ] || fail "no feature worktree: $out"
grep -q '"placement": "stealth"' "$wt/.fr-isolation" || fail "the marker does not record stealth"
grep -q "\"ref\": \"$track@main\"" "$wt/.fr-isolation" || fail "the marker lacks the tracking ref"
cd "$wt" || fail "cd $wt"

run_fr out plan create --slug 2026-11-12-s --target-repo derio-net/s
require_exit 0 "$out"
run_fr out journal add --scope plan --slug 2026-11-12-s --kind discovery --title t --body b --global
require_exit 0 "$out"
run_fr out run start fr-goal --branch feat/s
require_exit 0 "$out"
# Repository configuration fr would scaffold is refused before it is written (R24, p4-r3).
for cmd in "init agents" "init validator-wrapper" "settings init"; do
  run_fr out $cmd
  require_exit 2 "$out"
done
echo code > code.txt
git add -A && git commit -qm "feat(s): a code change" || fail "code commit"
refuse_grep '.' "$(git status --porcelain)" "the target checkout is clean"
run_fr out push
require_exit 0 "$out"
run_id="$(git --git-dir="$track" ls-tree -r --name-only main \
  | sed -n 's|^local--origin/features/feat__s/docs/superpowers/runs/\([^/]*\)\.yaml$|\1|p' | head -1)"
[ -n "$run_id" ] || fail "no run cursor in the tracking repo"
run_fr out run advance "$run_id"   # a state write after the code push: it records that head

# The target's remote, after `git add -A` and `fr push`: only the code commit, no fr path,
# no chore(fr) subject, no fr ref.
refs="$(git --git-dir="$origin" for-each-ref --format='%(refname)' | sort | tr '\n' ' ')"
[ "$refs" = "refs/heads/feat/s refs/heads/main " ] || fail "origin holds other refs: $refs"
[ "$(git --git-dir="$origin" log --format=%s main..feat/s)" = "feat(s): a code change" ] \
  || fail "origin feat/s holds more than the code commit"
for ref in main feat/s; do
  fr_paths="$(git --git-dir="$origin" ls-tree -r --name-only "$ref" | grep -E '^(docs/(superpowers|acceptance)/|features/|\.fr/|\.fr-isolation|\.claude/agents/fr-|scripts/validate-plans\.sh|\.devcontainer/fr-profiles\.yaml)' || true)"
  [ -z "$fr_paths" ] || fail "origin $ref carries fr paths: $fr_paths"
  refuse_grep '^chore\(fr\)' "$(git --git-dir="$origin" log --format=%s "$ref")" "no chore(fr) commit on origin $ref"
done
tracked="$(git --git-dir="$track" ls-tree -r --name-only main)"
expect_grep '^local--origin/features/feat__s/docs/superpowers/plans/2026-11-12-s/_meta.yaml$' \
  "$tracked" "the tracking repo holds the plan"
expect_grep "^local--origin/features/feat__s/docs/superpowers/runs/$run_id.stealth.json$" \
  "$tracked" "the tracking repo holds the product head beside the cursor"

# Another host: a fresh HOME and a fresh clone of the target resume from the tracking repo.
host_one="$HOME"
HOME="$(mktemp -d)" && export HOME
clone="$(mktemp -d)/origin"
git clone -q "$origin" "$clone" || fail "clone the target on host two"
cd "$clone" || fail "cd $clone"
run_fr out isolation up --stealth "$track@main" --resume "$run_id"
require_exit 0 "$out"
expect_grep 'agree' "$(printf '%s' "$out" | tr '\n' ' ')" "resume reconciles equal heads"
[ -f "$HOME/.cache/fr/worktrees/origin/feat__s/code.txt" ] || fail "host two has no workspace with the code"

# The tracking repo removed mid-run: the next resolve refuses, exit 2.
HOME="$host_one" && export HOME
cd "$wt" || fail "cd $wt"
mv "$track" "$track.gone" || fail "remove the tracking repo"
run_fr out run resolve "$run_id" --step brainstorm --state failed --reason "tracking gone"
[ "$RC" -eq 2 ] || fail "resolve did not exit 2 without its tracking repo (exit $RC): $out"
expect_grep 'unreachable' "$(printf '%s' "$out" | tr '\n' ' ')" "the refusal names the unreachable tracking repo"
echo "ok: placement-stealth"
