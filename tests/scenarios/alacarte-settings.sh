#!/usr/bin/env bash
# Rows s2-workflows-disabled, s2-pr-sections, s2-stealth-confirm (spec
# 2026-11-28-alacarte-settings R1-R9). A fixture repo with a local bare origin commits a
# schema-3 `.fr/settings.yaml` that disables fr-goal-light and turns the Cost and
# Proportionality sections off: `fr run start fr-goal-light` refuses naming
# `workflows.disabled` while `fr settings show --json` reports both keys, and a fixture
# run's PR body renders without the two sections. Then a stealth workspace over a separate
# local bare tracking repo: `git.push` and `git.pr` read `ask` with source `stealth`, and
# `fr push` prints an approval request for an unpushed code commit and `nothing to push`
# (no request) when the branch is already on the remote. Nothing reaches a forge.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
. "$here/_ask_approve.sh"
scenario_require_fresh_repo

HOME="$(mktemp -d)" && export HOME
export FR_ISOLATION_TARGET=worktree
base="$(mktemp -d)"
origin="$base/origin.git"
git init -q --bare -b main "$origin" || fail "bare origin"
git symbolic-ref HEAD refs/heads/main || fail "branch main"
git remote add origin "$origin"
echo seed > README.md
mkdir -p .fr
cat > .fr/settings.yaml <<'YAML'
schema: 3
workflows:
  disabled: [fr-goal-light]
forge:
  pr_sections:
    cost: "off"
    proportionality: "off"
YAML
git add -A && git commit -qm seed || fail "seed commit"
git push -q -u origin main || fail "seed push"
git remote set-head origin main >/dev/null
target="$(git rev-parse --show-toplevel)"
repo="$(basename "$target")"

# --- s2-workflows-disabled ------------------------------------------------------------
run_fr out settings show --json
require_exit 0 "$out"
expect_grep '"workflows\.disabled": \{"value": \["fr-goal-light"\], "source": "repo"\}' "$out" \
  "show reports workflows.disabled from the repo file"
expect_grep '"forge\.pr_sections\.cost": \{"value": "off", "source": "repo"\}' "$out" \
  "show reports forge.pr_sections.cost from the repo file"
run_fr out settings check
require_exit 0 "$out"
run_fr out run start fr-goal-light --branch feat/x
require_exit 2 "$out"
flat="$(printf '%s' "$out" | tr '\n' ' ')"
expect_grep 'workflow fr-goal-light is disabled' "$flat" "run start refuses the disabled shape"
expect_grep 'workflows\.disabled' "$flat" "the refusal names the setting"
expect_grep 'available: .*fr-goal' "$flat" "the refusal names what is still available"
[ -z "$(git worktree list | sed -n 2p)" ] || fail "a refused start left a worktree: $(git worktree list)"
# Only the listed shape is withdrawn: a shape left available still starts a run.
run_fr out run start fr-goal --branch feat/y --run-id r-y
require_exit 0 "$out"
[ -f "$HOME/.cache/fr/worktrees/$repo/feat__y/docs/superpowers/runs/r-y.yaml" ] \
  || fail "an available shape started no run: $out"

# --- s2-pr-sections ---------------------------------------------------------------------
py="$(candidate_python)"
body="$("$py" -P - "$target" <<'PY'
import sys
from pathlib import Path
from types import SimpleNamespace

from fr.record.pr_body import render_pr_body

root = Path(sys.argv[1])
steps = {"brainstorm": SimpleNamespace(emitted=None, units=None)}
print(render_pr_body(root, SimpleNamespace(run="r1", steps=steps, workflow="fr-goal@1")))
PY
)" || fail "render the fixture run's PR body: $body"
expect_grep '^## Findings$' "$body" "the body still carries a required section"
expect_grep '^## PR settle$' "$body" "a section left on is rendered"
refuse_grep '^## Cost$' "$body" "cost: off renders no Cost section"
refuse_grep '^## Proportionality$' "$body" "proportionality: off renders no Proportionality section"

# --- s2-stealth-confirm -----------------------------------------------------------------
track="$base/track.git"
git init -q --bare -b main "$track" || fail "bare tracking repo"
seed="$base/track-seed"
git init -q -b main "$seed" && echo tracking > "$seed/README.md" \
  && git -C "$seed" add -A && git -C "$seed" commit -qm seed \
  && git -C "$seed" push -q "$track" main || fail "seed the tracking repo"
run_fr out settings init --stealth "$track@main"
require_exit 0 "$out"
run_fr out isolation up --branch fix/s --stealth "$track@main"
require_exit 0 "$out"
wt="$HOME/.cache/fr/worktrees/$repo/fix__s"
cd "$wt" || fail "no stealth workspace: $out"

run_fr out settings show --json
require_exit 0 "$out"
expect_grep '"git\.push": \{"value": "ask", "source": "stealth"\}' "$out" "stealth forces git.push: ask"
expect_grep '"git\.pr": \{"value": "ask", "source": "stealth"\}' "$out" "stealth forces git.pr: ask"

run_fr out journal add --scope debug --slug 2026-11-28-s --kind discovery --title cause --body x
require_exit 0 "$out"
git push -q origin fix/s || fail "put the branch on the target's remote"
requests="$(git rev-parse --absolute-git-dir)/fr/requests"
run_fr out push
require_exit 0 "$out"
expect_grep 'nothing to push' "$out" "no code pending: fr push pushes nothing"
[ ! -d "$requests" ] || fail "fr push with nothing to push wrote a request: $(ls "$requests")"

echo code > code.txt
git add code.txt && git commit -qm "fix(s): a code change" || fail "code commit"
before="$(git --git-dir="$origin" rev-parse fix/s)"
run_fr out push
require_exit 2 "$out"
expect_grep 'git\.push: ask' "$(printf '%s' "$out" | tr '\n' ' ')" "a code push asks for approval"
[ -f "$requests/push-fix-s.json" ] || fail "the code push stored no request"
[ "$(git --git-dir="$origin" rev-parse fix/s)" = "$before" ] || fail "an unapproved push moved the target"
# The operator approves (fr verifies it in the session's transcript): the code lands, and the
# next code push asks again for its own approval (R9).
fr_approved out push
require_exit 0 "$out"
[ "$(git --git-dir="$origin" rev-parse fix/s)" = "$(git rev-parse HEAD)" ] || fail "the approved push did not land: $out"
echo more > more.txt
git add more.txt && git commit -qm "fix(s): a follow-up" || fail "second code commit"
run_fr out push
require_exit 2 "$out"
expect_grep 'git\.push: ask' "$(printf '%s' "$out" | tr '\n' ' ')" "the next code push asks again"
echo "ok: alacarte-settings"
