#!/usr/bin/env bash
# Rows s1-config-root, s1-switch-moved, s1-executable-config-protection, s1-migration,
# s1-shipped-defaults and s1-triage-state-home: S1, configuration homes (spec
# 2026-11-19-event-driven-a-la-carte, its candidate walk; plan
# 2026-11-24-s1-configuration-homes P7.T1.S1). Against the installed candidate, in scratch
# directories with a scratch HOME and local bare origins (no network):
#
# 1. shipped defaults resolve from the wheel's one `defaults/` tree, the old per-kind wheel
#    copies are gone, FR_SHIPPED_DEFAULTS_DIR points the resolver at another tree, and a
#    per-kind variable still works and names FR_SHIPPED_DEFAULTS_DIR (R15, R16);
# 2. under repo, a product holding every old path migrates in one `chore(fr): migrate` commit
#    of renames to `.fr/` (allowlist, models, trackers, plan-config, profiles at 3, a
#    workflow, a strategy), and `fr settings paths`, `fr workflow check` and `fr verification
#    list` read the new homes (R1, R8, R9, R10);
# 3. under quiet (a pre-S1 repo: the switch is only `settings.yaml` on `fr`), with origin
#    spelled git@github.com:example-org/demo.git and served from a local bare repo by a fake
#    ssh, and a fake gh replaying the captured rules replies: a refused push of `fr-config`
#    removes nothing; then the migration creates `fr-config` (every moved file, the product's
#    own `.fr/` files, the executable bit kept) before the product's migrate commit removes
#    the old paths; the switch reads from `fr-config` with the old copy in step; a repo shape
#    on an unprotected (free-plan) `fr-config` is ignored by `fr run start`/`advance` and
#    used when the rules read enforced; the walk runs `.fr/candidate-install` from the
#    fetched tip when enforced and refuses on the free-plan 403 and on an unreadable answer;
#    a direct push to `fr-config` makes readers refuse naming `fr settings sync`, whose
#    `--yes` needs `--expect` while unprotected (R3-R7, R10-R13);
# 4. under stealth (a pre-S1 target: the switch is only `<target>/settings.yaml` on the
#    tracking `main`), the migration creates `main-config` on the tracking repo and keeps the
#    product file, printing the `git rm` (R5, R10);
# 5. a scope's triage state in a clone's `.fr/triage-state/<scope>/` moves to the cache
#    repository, refused while a live `drive.lock` names a driver, leaving a tombstone and
#    saying to restart the driver (R17, R18).
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
scenario_require_fresh_repo
fixtures="$here/fixtures/config-homes/bin"

world="$(mktemp -d)"
trap 'rm -rf "$world"' EXIT
HOME="$world/home" && mkdir -p "$HOME" && export HOME
export FR_ISOLATION_TARGET=worktree FR_FORGE_API=rest FR_HOST_ID=0123456789abcdef
export PATH="$fixtures:$PATH" FAKE_GH_LOG="$world/gh.log" GIT_SSH_COMMAND="$fixtures/fake-ssh"
unset FR_SHIPPED_DEFAULTS_DIR FR_SHIPPED_WORKFLOWS_DIR FR_SHIPPED_VERIFICATIONS_DIR FR_SHIPPED_LENSES_DIR
QUIET='schema: 1
placement: quiet
forge:
  labels: off
'

# gate <var> <args...>: one fr command with the CLI-entry gate live (no CI marker, no skip),
# which migrates AND commits in a valid workspace (the explicit `fr migrate artifacts --yes`
# never commits).
gate() {
  local __var="$1"; shift
  local __out
  __out="$(env -u CI -u GITHUB_ACTIONS -u FR_SKIP_MIGRATION fr "$@" 2>&1)"; RC=$?
  printf -v "$__var" '%s' "$__out"
}

# load_paths: the resolver's FR_* answers into this shell (stdout only: a notice on stderr
# may hold a quote).
load_paths() {
  local p
  p="$(fr settings paths --shell 2>/dev/null)" || fail "fr settings paths --shell failed"
  eval "$p"
}

py="$(candidate_python)"
wheel="$("$py" -I -c 'import fr, os; print(os.path.dirname(fr.__file__))')"

# old_paths <dir> <workflow name>: every pre-S1 path (R8, R9) in the checkout <dir>.
old_paths() {
  mkdir -p "$1/docs/superpowers/workflows" "$1/docs/superpowers/verifications" "$1/.devcontainer"
  sed "s/^workflow: .*/workflow: $2/" "$wheel/defaults/workflows/fr-goal-light.yaml" \
    > "$1/docs/superpowers/workflows/$2.yaml"
  cp "$wheel/defaults/verifications/candidate.yaml" "$1/docs/superpowers/verifications/mine.yaml"
  printf 'opencode:\n  hard: m\n' > "$1/docs/superpowers/models.yaml"
  printf '{}\n' > "$1/docs/superpowers/trackers.yaml"
  printf 'plan: {}\n' > "$1/docs/superpowers/plan-config.yaml"
  printf 'schema_version: 2\nprofiles:\n  dev:\n    purpose: dev\n    secrets: []\ndefault: dev\nforge:\n  type: github\nci:\n  type: github-actions\ntracking:\n  type: github\n' \
    > "$1/.devcontainer/fr-profiles.yaml"
  printf 'data/**\n' > "$1/.fr-isolation-allow"
}
OLD=(docs/superpowers/workflows docs/superpowers/verifications/mine.yaml
  docs/superpowers/models.yaml docs/superpowers/trackers.yaml docs/superpowers/plan-config.yaml
  .devcontainer/fr-profiles.yaml .fr-isolation-allow)

# --- 1. shipped defaults: one tree, in the wheel (R15, R16) -----------------------------
for kind in workflows verifications lenses; do
  [ -n "$(ls "$wheel/defaults/$kind/"*.yaml 2>/dev/null)" ] || fail "the wheel has no defaults/$kind/"
done
for old in workflows verifications lens_manifests; do
  [ ! -d "$wheel/$old" ] || fail "the wheel still carries the old per-kind copy fr/$old/"
done
run_fr out verification list
require_exit 0 "$out"
for s in candidate client-live live prerelease; do
  expect_grep "^$s +wheel$" "$out" "strategy $s resolves from the wheel"
done
run_fr out lenses list
require_exit 0 "$out"
for l in errors security simplicity tests; do
  expect_grep "^$l .*\[shipped\]" "$out" "lens $l is shipped"
done
run_fr out workflow check --all
require_exit 0 "$out"
alt="$world/defaults"
mkdir -p "$alt/workflows"
sed 's/^workflow: .*/workflow: alt-shape/' "$wheel/defaults/workflows/fr-goal-light.yaml" \
  > "$alt/workflows/alt-shape.yaml"
out="$(FR_SHIPPED_DEFAULTS_DIR="$alt" fr workflow check alt-shape 2>&1)"; RC=$?
require_exit 0 "$out"
expect_grep '^alt-shape: ok' "$out" "FR_SHIPPED_DEFAULTS_DIR points the resolver at another tree"
out="$(FR_SHIPPED_WORKFLOWS_DIR="$alt/workflows" fr workflow check alt-shape 2>&1)"; RC=$?
require_exit 0 "$out"
expect_grep 'FR_SHIPPED_WORKFLOWS_DIR is deprecated; set \$FR_SHIPPED_DEFAULTS_DIR' "$out" \
  "a per-kind variable still resolves and names FR_SHIPPED_DEFAULTS_DIR"

# --- 2. repo: renames in one checkout, one migrate commit (R1, R8-R10) ------------------
repo_origin="$world/repo-origin.git"
git init -q --bare -b main "$repo_origin" || fail "bare origin"
git symbolic-ref HEAD refs/heads/main || fail "branch main"
git remote add origin "$repo_origin"
echo seed > README.md
old_paths . mine
git add -A && git commit -qm seed && git push -q -u origin main || fail "seed the repo fixture"
git remote set-head origin main >/dev/null
run_fr out isolation up --branch feat/r
require_exit 0 "$out"
cd "$HOME/.cache/fr/worktrees/$(basename "$PWD")/feat__r" || fail "no repo workspace: $out"
gate out acceptance status --brief
expect_grep 'fr: migrated and committed .*: chore\(fr\): migrate 7 artifacts' "$out" "the gate migrates the seven old paths"
expect_grep '^chore\(fr\): migrate 7 artifacts' "$(git log -1 --format=%s)" "one migrate commit"
renames="$(git show --name-status -M --format= HEAD)"
for pair in ".fr-isolation-allow .fr/isolation-allow" "docs/superpowers/models.yaml .fr/models.yaml" \
  "docs/superpowers/trackers.yaml .fr/trackers.yaml" "docs/superpowers/plan-config.yaml .fr/plan-config.yaml" \
  "docs/superpowers/workflows/mine.yaml .fr/workflows/mine.yaml" \
  "docs/superpowers/verifications/mine.yaml .fr/verifications/mine.yaml"; do
  set -- $pair
  expect_grep "^R[0-9]+	$1	$2$" "$renames" "$1 is git-moved to $2"
done
expect_grep '	\.devcontainer/fr-profiles\.yaml	\.fr/profiles\.yaml$' "$renames" "profiles moves to .fr/"
grep -qx 'schema_version: 3' .fr/profiles.yaml || fail "the profiles file is not at version 3"
refuse_grep '.' "$(git status --porcelain)" "the repo migration leaves a clean tree"
run_fr paths settings paths --shell
require_exit 0 "$paths"
expect_grep "^FR_PLACEMENT=repo$" "$paths" "repo placement"
here_p="$(pwd -P)"
expect_grep "^FR_WORKFLOWS_DIR=$here_p/\.fr/workflows$" "$paths" "repo: workflows live in the product's .fr/"
expect_grep "^FR_MODELS_FILE=$here_p/\.fr/models\.yaml$" "$paths" "repo: models live in the product's .fr/"
run_fr out workflow check --all
require_exit 0 "$out"
expect_grep '^mine: ok' "$out" "the repo's own shape resolves from .fr/workflows/"
run_fr out verification list
expect_grep '^mine +repo$' "$out" "the repo's strategy resolves from .fr/verifications/"
run_fr out validate artifacts
require_exit 0 "$out"

# --- 3. quiet: fr-config, the switch, protection (R3-R7, R10-R13) ------------------------
export FAKE_SSH_ROOT="$world/ssh"
qorigin="$FAKE_SSH_ROOT/example-org/demo.git"
mkdir -p "$FAKE_SSH_ROOT/example-org"
git init -q --bare -b main "$qorigin" || fail "bare quiet origin"
q="$world/demo"
git init -q -b main "$q" || fail "quiet product"
cd "$q" || fail "cd $q"
git remote add origin git@github.com:example-org/demo.git
echo seed > README.md
old_paths . fr-goal
mkdir -p .fr
printf '#!/bin/sh\necho "candidate-install ran from $0" >&2\nexit 7\n' > .fr/candidate-install
chmod +x .fr/candidate-install
printf 'tests: ci\n' > .fr/ci.yaml
git add -A && git commit -qm seed && git push -q -u origin main || fail "seed the quiet product"
git remote set-head origin main >/dev/null
git checkout -q --orphan fr && git rm -rfq . && printf '%s' "$QUIET" > settings.yaml \
  && git add -A && git commit -qm fr && git push -q origin fr && git checkout -q main \
  && git branch -qD fr || fail "the pre-S1 switch on fr"
run_fr out isolation up --branch feat/q
require_exit 0 "$out"
qw="$HOME/.cache/fr/worktrees/demo/feat__q"
cd "$qw" || fail "no quiet workspace: $out"
export FAKE_RULES=free-plan  # the forge answers the free-plan 403 unless a step says otherwise

# A refused push of the new configuration branch removes nothing (R10).
printf '#!/bin/sh\necho "fr-config refused here" >&2\nexit 1\n' > "$qorigin/hooks/pre-receive"
chmod +x "$qorigin/hooks/pre-receive"
gate out acceptance status --brief
expect_grep 'refused' "$out" "the refused fr-config push is reported"
for old in "${OLD[@]}" .fr/candidate-install .fr/ci.yaml; do
  [ "$old" = .fr-isolation-allow ] && continue  # R8: it stays in the product, renamed in place
  [ -e "$old" ] || fail "a refused push removed $old"
done
[ -z "$(git --git-dir="$qorigin" for-each-ref refs/heads/fr-config)" ] || fail "fr-config exists after a refused push"
rm "$qorigin/hooks/pre-receive"

gate out acceptance status --brief
expect_grep "ignoring the product checkout's \.fr/ under quiet: candidate-install, ci\.yaml" "$out" \
  "R4: the product's own .fr/ is named as ignored"
expect_grep '^chore\(fr\): migrate' "$(git log -1 --format=%s)" "the quiet migrate commit"
deleted="$(git show --name-status --format= HEAD)"
for old in docs/superpowers/workflows/fr-goal.yaml docs/superpowers/verifications/mine.yaml \
  docs/superpowers/models.yaml docs/superpowers/trackers.yaml docs/superpowers/plan-config.yaml \
  .devcontainer/fr-profiles.yaml .fr/candidate-install .fr/ci.yaml; do
  expect_grep "^D	$old$" "$deleted" "the product's migrate commit removes $old"
done
[ -f .fr/isolation-allow ] || fail "R8: the allowlist stays in the product as .fr/isolation-allow"
tree="$(git --git-dir="$qorigin" ls-tree -r fr-config)"
for f in settings.yaml models.yaml trackers.yaml plan-config.yaml profiles.yaml workflows/fr-goal.yaml \
  verifications/mine.yaml ci.yaml; do
  expect_grep "	\.fr/$f$" "$tree" "fr-config holds .fr/$f"
done
expect_grep '^100755 blob [0-9a-f]+	\.fr/candidate-install$' "$tree" "the candidate install keeps its executable bit"
refuse_grep 'isolation-allow' "$tree" "the allowlist never moves to fr-config"
[ "$(git --git-dir="$qorigin" rev-list --count fr-config)" = 1 ] || fail "fr-config is not one orphan commit"
[ "$(git --git-dir="$qorigin" show fr-config:.fr/settings.yaml)" = "$(git --git-dir="$qorigin" show fr:settings.yaml)" ] \
  || fail "R6: the old switch is not in step with fr-config's"
run_fr out settings show
require_exit 0 "$out"
expect_grep '^placement +quiet +quiet$' "$out" "the switch reads quiet"
load_paths
[ "$FR_PLACEMENT" = quiet ] || fail "FR_PLACEMENT is $FR_PLACEMENT"
case "$FR_MODELS_FILE" in */.cache/fr/worktrees/demo/fr-config/.fr/models.yaml) ;;
  *) fail "quiet: models are not read from the fr-config worktree: $FR_MODELS_FILE" ;; esac
case "$FR_WORKFLOWS_DIR" in */.cache/fr/worktrees/demo/fr-config/.fr/workflows) ;;
  *) fail "quiet: workflows are not read from the fr-config worktree: $FR_WORKFLOWS_DIR" ;; esac
run_fr out workflow check fr-goal
require_exit 0 "$out"
refuse_grep 'old location' "$out" "an emptied old directory says nothing"
git push -q origin HEAD:main || fail "land the quiet migration on main"   # as its PR would

# fr run start / advance under quiet (p4-r11): the repo's fr-goal (a copy of fr-goal-light:
# brainstorm, then plan) degrades to the shipped one (brainstorm, then spec-review) while
# fr-config is unprotected, and is used once its rules read enforced. One feature each.
for rules in free-plan approved; do
  export FAKE_RULES="$rules"
  cd "$q" || fail "cd $q"
  run_fr out isolation up --branch "feat/q-$rules"
  require_exit 0 "$out"
  cd "$HOME/.cache/fr/worktrees/demo/feat__q-$rules" || fail "no workspace for feat/q-$rules: $out"
  run_fr out run start fr-goal --branch "feat/q-$rules" --run-id "q-$rules"
  require_exit 0 "$out"
  if [ "$rules" = free-plan ]; then
    expect_grep 'ignoring workflows/fr-goal\.yaml .*not protected \(GitHub does not enforce rulesets' \
      "$out" "an unprotected fr-config's shape is ignored with the reason"
    expect_grep 'keep the ruleset.s bypass list empty' "$out" "the fix names the bypass list"
  else
    refuse_grep 'ignoring workflows/fr-goal' "$out" "an enforced fr-config's shape is used"
  fi
  run_fr out run advance "q-$rules"
  require_exit 0 "$out"
  expect_grep '"step": "brainstorm"' "$out" "the run advances to brainstorm"
  load_paths
  mkdir -p "$FR_SPECS_DIR"
  printf '# Q\n\n## Verification\n\nstrategy: candidate\n' > "$FR_SPECS_DIR/2026-11-25-q-design.md"
  run_fr out run resolve "q-$rules" --step brainstorm --state done --answered-by agent \
    --emitted spec=docs/superpowers/specs/2026-11-25-q-design.md
  require_exit 0 "$out"
  runs_dir="$FR_RUNS_DIR"
done
export FAKE_RULES=free-plan
grep -q '^cursor: plan$' "$runs_dir/q-approved.yaml" \
  || fail "enforced: the repo's fr-goal did not follow brainstorm with plan: $(cat "$runs_dir/q-approved.yaml")"
cd "$HOME/.cache/fr/worktrees/demo/feat__q-free-plan" || fail "cd feat/q-free-plan"
load_paths
grep -q '^cursor: spec-review$' "$FR_RUNS_DIR/q-free-plan.yaml" \
  || fail "unprotected: the shipped fr-goal did not follow brainstorm with spec-review: $(cat "$FR_RUNS_DIR/q-free-plan.yaml")"
cd "$HOME/.cache/fr/worktrees/demo/feat__q-approved" || fail "cd feat/q-approved"

# The walk runs .fr/candidate-install only when the forge enforces the rules (R7).
out="$(FAKE_RULES=approved fr verification walk --run q-approved --model scenario 2>&1)"; RC=$?
expect_grep 'running \.fr/ as origin/fr-config has it at [0-9a-f]+' "$out" "enforced: the walk runs the fetched tip"
expect_grep '^install: FAILED \(exit 7\)' "$out" "enforced: the candidate install ran"
log="$(printf '%s\n' "$out" | sed -n 's/^walk log: //p')"
expect_grep 'candidate-install ran from ' "$(cat "$log")" "the install's own output is in the walk log"
refuse_grep 'candidate-install ran from .*/worktrees/demo/fr-config/' "$(cat "$log")" \
  "the install never runs from the configuration checkout"
out="$(FAKE_RULES=free-plan fr verification walk --run q-approved --model scenario 2>&1)"; RC=$?
require_exit 2 "$out"
expect_grep 'refused: fr will not run the candidate install: fr-config on example-org/demo is not protected \(GitHub does not enforce rulesets on a private repository on the free plan \(HTTP 403\)\)' \
  "$out" "free plan: the walk refuses, naming why"
refuse_grep 'candidate-install ran' "$out" "free plan: nothing ran"
out="$(FAKE_RULES=unreadable fr verification walk --run q-approved --model scenario 2>&1)"; RC=$?
require_exit 2 "$out"
expect_grep 'the rules of fr-config on example-org/demo could not be read' "$out" \
  "an unreadable answer refuses, never reads as protected or unprotected"

# A change pushed straight to fr-config: the old copy lags, readers refuse naming
# `fr settings sync`, and `--yes` needs `--expect` while fr-config is unprotected (R6).
export FAKE_RULES=free-plan
edit="$world/qedit"
git clone -q -b fr-config "$qorigin" "$edit" || fail "clone fr-config"
printf '%sartifacts:\n  gates: off\n' "$QUIET" > "$edit/.fr/settings.yaml"
git -C "$edit" commit -qam "settings: gates off" && git -C "$edit" push -q origin fr-config || fail "push to fr-config"
tip="$(git --git-dir="$qorigin" rev-parse fr-config)"
git fetch -q origin || fail "fetch"
run_fr out settings show
[ "$RC" -ne 0 ] || fail "a reader did not refuse two differing switches: $out"
expect_grep 'fr settings sync' "$out" "the refusal names fr settings sync"
run_fr out settings sync
require_exit 0 "$out"
expect_grep "^tip: +$tip" "$out" "the preview names the configuration branch's tip"
expect_grep 'NOT a merge' "$out" "the preview marks a direct push"
run_fr out settings sync --yes
require_exit 2 "$out"
expect_grep 'without `--expect`' "$out" "unprotected: --yes alone refuses"
run_fr out settings sync --yes --expect "$tip"
require_exit 0 "$out"
[ "$(git --git-dir="$qorigin" show fr:settings.yaml)" = "$(git --git-dir="$qorigin" show fr-config:.fr/settings.yaml)" ] \
  || fail "sync --expect did not bring the old copy in step"
run_fr out settings show
require_exit 0 "$out"
expect_grep '^artifacts\.gates +off +quiet$' "$out" "the synced switch is read"
unset FAKE_RULES

# --- 4. stealth: <branch>-config on the tracking repo, the product file kept (R5, R10) ---
s="$world/stealthy"
sorigin="$world/stealth-remote/origin.git"   # the target dir is local--origin
track="$world/track.git"
mkdir -p "$world/stealth-remote" && git init -q --bare -b main "$sorigin" && git init -q -b main "$s" || fail "stealth product"
cd "$s" || fail "cd $s"
git remote add origin "$sorigin"
echo seed > README.md
mkdir -p docs/superpowers && printf 'opencode:\n  hard: s\n' > docs/superpowers/models.yaml
git add -A && git commit -qm seed && git push -q -u origin main || fail "seed the stealth product"
git remote set-head origin main >/dev/null
git init -q --bare -b main "$track" || fail "bare tracking repo"
seed="$world/track-seed"
git init -q -b main "$seed" && mkdir -p "$seed/local--origin" \
  && printf 'schema: 1\nplacement: stealth\n' > "$seed/local--origin/settings.yaml" \
  && git -C "$seed" add -A && git -C "$seed" commit -qm seed && git -C "$seed" push -q "$track" main \
  || fail "the pre-S1 stealth switch on the tracking main"
run_fr out isolation up --branch feat/s --stealth "$track@main"
require_exit 0 "$out"
cd "$HOME/.cache/fr/worktrees/stealthy/feat__s" || fail "no stealth workspace: $out"
head="$(git rev-parse HEAD)"
gate out acceptance status --brief
expect_grep "moved to origin/main-config and stays in the product under stealth .*git -C .* rm -- docs/superpowers/models\.yaml" \
  "$out" "stealth prints the git rm once"
[ "$(git rev-parse HEAD)" = "$head" ] || fail "stealth committed on the target's branch"
[ -f docs/superpowers/models.yaml ] || fail "stealth removed the product file"
stree="$(git --git-dir="$track" ls-tree -r --name-only main-config)"
expect_grep '^local--origin/\.fr/models\.yaml$' "$stree" "main-config holds the models file"
expect_grep '^local--origin/\.fr/settings\.yaml$' "$stree" "main-config holds the switch"
[ "$(git --git-dir="$track" show main-config:local--origin/.fr/settings.yaml)" = \
  "$(git --git-dir="$track" show main:local--origin/settings.yaml)" ] || fail "R6: the stealth copies differ"
run_fr out settings show
require_exit 0 "$out"
expect_grep '^placement +stealth +stealth$' "$out" "the stealth switch reads from main-config"
run_fr paths settings paths --shell
expect_grep '^FR_MODELS_FILE=.*/stealth--[^/]*-config/local--origin/\.fr/models\.yaml$' "$paths" \
  "stealth: models are read from the configuration clone"

# --- 5. triage state: the cache repository, the move, the tombstone (R17, R18) -----------
t="$world/triage-clone"
git init -q "$t" && cd "$t" || fail "triage clone"
scope=example-org--demo
st=".fr/triage-state/$scope"
mkdir -p "$st"
printf 'schema: 6\ntiers: [{n: 1, title: Now}]\nissues:\n  "demo#1": {tier: 1}\n' > "$st/judgements.yaml"
printf 'schema: 2\n' > "$st/origins.yaml"
printf '.fr/triage-state/\n' >> .git/info/exclude
cache="$HOME/.cache/fr/triage/$scope"
mkdir -p "$cache"
sleep 300 &
driver=$!
printf '{"pid": %s, "started": "x"}\n' "$driver" > "$cache/drive.lock"
run_fr out triage batch list --repo example-org/demo
kill "$driver" 2>/dev/null; wait "$driver" 2>/dev/null
[ "$RC" -ne 0 ] || fail "the move ran while a live driver held drive.lock: $out"
expect_grep 'stop the driver first' "$out" "a live drive.lock refuses the move"
[ -f "$st/judgements.yaml" ] || fail "the refused move touched the clone copy"
run_fr out triage batch list --repo example-org/demo
require_exit 0 "$out"
expect_grep "moved the triage state of $scope" "$out" "the move says so"
expect_grep 'restart any `fr triage batch drive`' "$out" "the move says to restart the driver"
[ -d "$cache/.git" ] || fail "the cache is not a git repository"
cmp -s "$cache/judgements.yaml" <(printf 'schema: 6\ntiers: [{n: 1, title: Now}]\nissues:\n  "demo#1": {tier: 1}\n') \
  || fail "the cache does not hold the moved judgements"
[ -f "$st" ] && [ "$(head -1 "$st")" = fr-triage-state-moved ] || fail "no tombstone at $st"
run_fr out triage batch list --repo example-org/demo
require_exit 0 "$out"
refuse_grep 'moved the triage state' "$out" "the tombstone is passed by"
echo "ok: config-homes"
