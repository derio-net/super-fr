# Shared by placement-quiet.sh and placement-stealth.sh (sourced, never run on its own).
#
# A whole run, every step, under the workspace's placement, with real artifacts and the
# real CLI (debug journal 2026-11-13-placement-plan-paths: a live walk kept finding a
# path that assumed the repo layout one pipeline step at a time). Each step is resolved
# with the step record the shape's brief names, as fr-goal does: brainstorm writes the
# spec below FR_SPECS_DIR and its rows; `fr plan create --spec $FR_SPECS_DIR/<file>`;
# plan-review runs the real `fr plan self-review`; each phase ticks its plan and moves its
# row; journal-check and lens-review run; deliver renders its PR body, proportionality
# included, and resolves against a fake forge that serves that body back (nothing reaches
# a forge: the fake `gh` refuses every other call). Then the close-out the brief names:
# `fr push`, a merge commit on origin's default branch, `fr pickup --run` and
# `fr archive --branch` from the base clone, `fr isolation down`.

# walk_fake_forge: a `gh` first on PATH that serves $FAKE_PR_BODY for `pr view --json
# body` and refuses everything else, logging each call to $FAKE_GH_LOG.
walk_fake_forge() {
  local bin
  bin="$(mktemp -d)"
  cat > "$bin/gh" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "${FAKE_GH_LOG:-/dev/null}"
if [ "$1 $2" = "pr view" ] && printf '%s\n' "$*" | grep -q -- '--json body'; then
  cat "$FAKE_PR_BODY"; exit 0
fi
echo "fake gh: no forge here ($*)" >&2; exit 1
EOF
  chmod +x "$bin/gh"
  export PATH="$bin:$PATH" FAKE_GH_LOG="$bin/gh.log" FAKE_PR_BODY="$bin/body.md"
  : > "$FAKE_PR_BODY"
}

# walk_brief <run>: advance the run, require exit 0, and set BRIEF to the output and
# RECORD to the record path the brief names.
walk_brief() {
  run_fr BRIEF run advance "$1"
  require_exit 0 "$BRIEF"
  walk_record_of "$BRIEF"
}

walk_record_of() {
  RECORD="$(printf '%s\n' "$1" | sed -n 's/.*"record": {"in_progress": null, "path": "\([^"]*\)".*/\1/p' | tail -1)"
  [ -n "$RECORD" ] || fail "the brief names no record: $1"
}

# walk_expect <step>: the brief the last resolve advanced to is <step>'s (a resolve
# advances the cursor itself, running any `kind: cli` step on the way).
walk_expect() {
  expect_grep "\"step\": \"$1\"" "$BRIEF" "the next brief is $1's"
  walk_record_of "$BRIEF"
}

# walk_resolve <run> <step> [<item>]: resolve with the record on stdin, written where the
# brief named it.
walk_resolve() {
  mkdir -p "$(dirname "$RECORD")"
  cat > "$RECORD"
  local item=()
  [ -n "${3:-}" ] && item=(--item "$3")
  run_fr out run resolve "$1" --step "$2" "${item[@]}" --record "$RECORD"
  require_exit 0 "$out"
  BRIEF="$out"
  refuse_grep 'features/[^ ]*/docs/superpowers/specs' "$out" "$2 names a spec by its fr-worktree path"
}

# walk_run <shape> <branch> <slug> <run> <phases>: from the feature workspace (cwd), a
# whole <shape> run with a <phases>-phase plan, through deliver.
walk_run() {
  local shape="$1" branch="$2" slug="$3" run="$4" phases="$5" n spec ident repo_id rows splits
  WALK_TMP="$(mktemp -d)"   # scratch outside every checkout
  local tag="${slug//-/_}_"   # this run's own file names: a later branch holds the earlier's
  run_fr out run start "$shape" --branch "$branch" --run-id "$run"
  require_exit 0 "$out"
  run_fr paths settings paths --shell
  require_exit 0 "$paths"
  eval "$paths"
  spec="$slug-design.md"
  mkdir -p "$FR_SPECS_DIR"
  {
    printf '# %s\n\n## Requirements\n\n' "$slug"
    for n in $(seq 1 "$phases"); do printf 'R%s. Requirement %s holds.\n' "$n" "$n"; done
    printf '\n## Test Plan\n\n- unit: every requirement has a test.\n\n## Verification\n\nstrategy: none\n'
    for n in $(seq 1 "$phases"); do printf -- '- %s-r%s: none — proven by its unit test\n' "$slug" "$n"; done
  } > "$FR_SPECS_DIR/$spec"

  # brainstorm: the spec, a decision, one row per requirement (logical origins, R18).
  walk_brief "$run"
  walk_expect brainstorm
  rows="" splits=""
  local cite
  for n in $(seq 1 "$phases"); do
    # Row 1 cites the spec by its file's whole stem, as the 7.0.0rc5 stealth walk's agent
    # did (debug journal 2026-11-14-placement-repair-and-design-slug); it is stored in the
    # one spelling, `spec:<stem minus -design>`, in the run's own fragment.
    cite="$slug"; [ "$n" = 1 ] && cite="$slug-design"
    rows="$rows  - {id: $slug-r$n, capability: c$n, acceptance: requirement $n holds, origin: ['spec:$cite#R$n'], status: not-implemented}
"
    [ "$n" -gt 1 ] && splits="$splits  - {kind: decision, id: phase-split-$slug-p$n, title: 'ask: phase $n serves R$n'}
"
  done
  walk_resolve "$run" brainstorm <<EOF
schema_version: 12
run: $run
step: brainstorm
outcome: done
journal:
  - {kind: decision, id: d-scope, title: the scope is the requirements}
$splits
acceptance:
$rows
emitted:
  spec: $FR_SPECS_DIR/$spec
evidence:
  answered_by: agent
EOF
  grep -q "spec: docs/superpowers/specs/$spec" "$FR_RUNS_DIR/$run.yaml" \
    || fail "the cursor does not record the spec below the feature root: $(cat "$FR_RUNS_DIR/$run.yaml")"
  [ ! -e "$FR_ACCEPTANCE_FRAGMENTS_DIR/$slug-design.yaml" ] \
    || fail "a -design spelled origin filed its row in a fragment of its own"
  expect_grep "spec:$slug#R1" "$(cat "$FR_ACCEPTANCE_FRAGMENTS_DIR/$slug.yaml")" \
    "a -design spelled origin is stored in its one spelling"
  ident="$(sed -n 's/^repo: //p' "$FR_ACCEPTANCE_FRAGMENTS_DIR/$slug.yaml")"
  repo_id="${ident#*/}"
  [ -n "$repo_id" ] || fail "the brainstorm fragment names no repo"

  if [ "$shape" = fr-goal ]; then
    walk_expect spec-review
    walk_resolve "$run" spec-review <<EOF
schema_version: 12
run: $run
step: spec-review
outcome: done
journal:
  - {kind: review, id: spec-rev, title: independent spec review, body: no findings}
evidence:
  review: spec-rev
  reviewer: spec-reviewer-1
EOF
  fi

  # plan: `fr plan create --spec $FR_SPECS_DIR/<file>` stores the bare file name, and the
  # real self-review passes a plan whose rows cite the spec logically.
  walk_expect plan
  {
    for n in $(seq 1 "$phases"); do
      cat <<EOF
- number: $n
  title: Requirement $n
  tag: agentic
  tier: mechanical
  skeleton: $([ "$n" = 1 ] && [ "$phases" -gt 1 ] && echo true || echo false)
  depends_on: [$([ "$n" -gt 1 ] && echo $((n - 1)))]
  acceptance: [$slug-r$n]
  files: [$slug-$n.txt, tests/test_$tag$n.py]
  estimate_lines: 3
  tasks:
    - number: 1
      title: build requirement $n
      steps:
        - {id: P$n.T1.S1, text: Write $slug-$n.txt and its test}
EOF
    done
  } > "$WALK_TMP/$run-phases.yaml"
  run_fr out plan create --slug "$slug" --target-repo "derio-net/$repo_id" \
    --spec "$FR_SPECS_DIR/$spec" --workflow "$shape" --phases-file "$WALK_TMP/$run-phases.yaml"
  require_exit 0 "$out"
  grep -qx "spec: $spec" "$FR_PLANS_DIR/$slug/_meta.yaml" \
    || fail "_meta.yaml does not name the bare spec file: $(cat "$FR_PLANS_DIR/$slug/_meta.yaml")"
  run_fr out plan self-review "$FR_PLANS_DIR/$slug"
  require_exit 0 "$out"
  refuse_grep 'serves no ask|no matrix row citing|unknown acceptance row|features/' "$out" \
    "self-review reads the plan where it lives"
  # A plan 7.0.0rc4's `plan create` left: an absolute spec path in _meta.yaml, committed
  # where the plan lives. Self-review passes it, and `fr repair --yes` (whose dirty guard
  # asked the product checkout's git, exit 128) rewrites it to the bare file name.
  local meta="$FR_PLANS_DIR/$slug/_meta.yaml" holder
  holder="$(git -C "$FR_PLANS_DIR" rev-parse --show-toplevel)"
  sed "s|^spec: .*|spec: $FR_SPECS_DIR/$spec|" "$meta" > "$WALK_TMP/meta" && cp "$WALK_TMP/meta" "$meta"
  git -C "$holder" add -A -- "$meta" && git -C "$holder" commit -qm "a stale absolute spec ref" \
    || fail "commit the stale spec ref"
  run_fr out plan self-review "$FR_PLANS_DIR/$slug"
  require_exit 0 "$out"
  run_fr out repair
  require_exit 0 "$out"
  expect_grep "would repair: _meta.yaml.* spec: .*$spec" "$(printf '%s' "$out" | tr -d '\n')" \
    "repair plans the rewrite"
  run_fr out repair --yes
  require_exit 0 "$out"
  refuse_grep 'Traceback|CalledProcessError' "$out" "repair --yes runs its guard where the plan lives"
  grep -qx "spec: $spec" "$meta" || fail "repair did not restore the bare spec file: $(cat "$meta")"
  git -C "$holder" add -A -- "$meta" && git -C "$holder" commit -qm "fr repair" \
    || fail "commit the repair"
  run_fr out plan self-review "$FR_PLANS_DIR/$slug"
  require_exit 0 "$out"
  walk_resolve "$run" plan <<EOF
schema_version: 12
run: $run
step: plan
outcome: done
journal:
  - {kind: decision, id: d-plan, title: one phase per requirement, global: true}
emitted:
  plan: $FR_PLANS_DIR/$slug
EOF
  grep -q "plan: docs/superpowers/plans/$slug" "$FR_RUNS_DIR/$run.yaml" \
    || fail "the cursor does not record the plan below the feature root"

  if [ "$shape" = fr-goal-light ]; then
    walk_expect spec-plan-review
    walk_resolve "$run" spec-plan-review <<EOF
schema_version: 12
run: $run
step: spec-plan-review
outcome: done
journal:
  - {kind: review, id: spec-plan-rev, title: independent spec and plan review, body: no findings}
evidence:
  review: spec-plan-rev
  reviewer: spec-reviewer-1
EOF
  fi

  # plan-review (cli: the real self-review) runs on the advance that briefs phase 1.
  for n in $(seq 1 "$phases"); do
    walk_expect implement-phase
    expect_grep "\"item\": \"phase/$n\"" "$BRIEF" "the brief is phase $n's"
    if [ "$n" = 1 ]; then expect_grep 'plan-review: done' "$BRIEF" "plan-review ran the self-review"; fi
    run_fr out pickup "$FR_PLANS_DIR/$slug" --phase "$n"
    require_exit 0 "$out"
    expect_grep "P$n.T1.S1" "$out" "fr pickup names phase $n's step"
    echo "r$n" > "$slug-$n.txt" && mkdir -p tests && printf 'def test_%s():\n    assert True\n' "$n" > "tests/test_$tag$n.py"
    git add -A && git commit -qm "feat($slug): requirement $n" || fail "code commit $n"
    walk_resolve "$run" implement-phase "phase/$n" <<EOF
schema_version: 12
run: $run
step: implement-phase
item: phase/$n
outcome: done
ticks: [P$n.T1.S1]
journal:
  - {kind: discovery, id: disc-p$n, title: requirement $n was direct, phase: $n}
EOF
    grep -q 'state: x' "$FR_PLANS_DIR/$slug/0$n.yaml" || fail "phase $n's step is not ticked"
    run_fr out acceptance set-status --id "$slug-r$n" --status unwired --notes "its unit test landed" \
      --level "unit=$repo_id:tests/test_$tag$n.py#test_$n"
    require_exit 0 "$out"
    walk_expect review-phase
    walk_resolve "$run" review-phase "phase/$n" <<EOF
schema_version: 12
run: $run
step: review-phase
item: phase/$n
outcome: done
journal:
  - {kind: review, id: rev-p$n, title: phase $n review, body: no findings, phase: $n}
evidence:
  review: rev-p$n
  reviewer: reviewer-$n
EOF
  done

  # A caller's extra bookkeeping before the run's checks (an amendment, say).
  "${WALK_HOOK:-:}"

  # journal-check (cli) runs on the advance that briefs lens-review; the set is empty.
  walk_expect lens-review
  expect_grep 'journal-check: done' "$BRIEF" "journal-check ran"
  expect_grep 'no lens is in this feature' "$BRIEF" "the lens set is computed"
  walk_resolve "$run" lens-review <<EOF
schema_version: 12
run: $run
step: lens-review
outcome: done
EOF

  # deliver: each row is gated for a live walk (the rows are unwired), the first
  # resolve renders the PR body and stops at the forge, the fake forge serves it back.
  walk_expect deliver
  for n in $(seq 1 "$phases"); do
    run_fr out verification set --run "$run" --row "$slug-r$n" --gate tester --reason "a live walk"
    require_exit 0 "$out"
  done
  run_fr out acceptance check
  require_exit 0 "$out"
  echo "$phases passed" > "$WALK_TMP/$run-suite.log"
  local deliver_record
  deliver_record="$(cat <<EOF
schema_version: 12
run: $run
step: deliver
outcome: done
emitted:
  pr: https://github.com/derio-net/$repo_id/pull/1
evidence:
  tests: $WALK_TMP/$run-suite.log
EOF
)"
  mkdir -p "$(dirname "$RECORD")" && printf '%s\n' "$deliver_record" > "$RECORD"
  : > "$FAKE_PR_BODY"   # no PR body yet: an earlier run's must not stand in for this one's
  : > "$FAKE_GH_LOG"
  run_fr out run resolve "$run" --step deliver --record "$RECORD"
  local body
  if [ "$FR_PLACEMENT" = stealth ]; then
    # R24: the live PR is plain (forge.pr_body: minimal), so there is nothing to check
    # it against; the full render is kept beside the cursor, in the tracking clone.
    require_exit 0 "$out"
    body="$FR_RUNS_DIR/$run.pr-body.md"
  else
    [ "$RC" -eq 2 ] || fail "deliver did not stop at the forge (exit $RC): $out"
    body="$FR_RUNS_DIR/$run.records/pr-body.md"
  fi
  [ -f "$body" ] || fail "deliver rendered no PR body below the feature root: $out"
  expect_grep "serves? $phases of $phases requirements" "$(cat "$body")" \
    "proportionality reads the plan and spec at their own HEAD"
  refuse_grep 'features/|is not in the subpath' "$(cat "$body")" "the PR body names no fr-worktree path"
  if [ "$FR_PLACEMENT" != stealth ]; then
    cp "$body" "$FAKE_PR_BODY"
    printf '%s\n' "$deliver_record" > "$RECORD"
    run_fr out run resolve "$run" --step deliver --record "$RECORD"
    require_exit 0 "$out"
  fi
  expect_grep "fr pickup --run $run" "$out" "deliver names the close-out"
  # The forge was asked exactly what the fake serves, the PR's body (R24 lets a stealth
  # run read its target's forge, never write it), and nothing a swallowed failure would
  # hide.
  local calls stray
  calls="$(cat "$FAKE_GH_LOG")"
  [ -n "$calls" ] || fail "deliver never read the PR body back from the forge"
  stray="$(printf '%s\n' "$calls" | grep -Ev '^pr view .*--json body' || true)"
  [ -z "$stray" ] || fail "deliver asked the forge something else: $stray"
  local sha
  sha="$(printf '%s\n' "$out" | sed -n 's/^cursor committed as \([0-9a-f]*\).*/\1/p')"
  [ -n "$sha" ] && git -C "$FR_ARTIFACT_ROOT" cat-file -e "$sha^{commit}" \
    || fail "'cursor committed as' does not name the commit holding the cursor: $out"
  run_fr out push
  require_exit 0 "$out"
}

# walk_closeout <base clone> <origin> <branch> <run>: merge the branch on origin's default
# branch with a merge commit, then the close-out the brief names, from the base clone.
walk_closeout() {
  local base="$1" origin_dir="$2" branch="$3" run="$4" here
  here="$(pwd -P)"
  ( cd "$base" && git fetch -q origin && git merge -q --no-ff -m "Merge $branch" "origin/$branch" \
      && git push -q origin HEAD ) || fail "merge $branch on origin"
  # Under quiet the base clone reads the `fr` branch; under stealth only the workspace
  # names its tracking repo (R24), so its close-out runs there.
  [ "$FR_PLACEMENT" = stealth ] || cd "$base" || fail "cd $base"
  run_fr out pickup --run "$run"
  require_exit 0 "$out"
  expect_grep "Run this from $( [ "$FR_PLACEMENT" = stealth ] && echo "$here" || echo "$(cd "$base" && pwd -P)" )" \
    "$(printf '%s' "$out" | tr '\n' ' ')" "the brief names where to run the close-out"
  expect_grep "run the spec's Test Plan: docs/superpowers/specs/" "$out" "the brief reads the spec where it lives"
  expect_grep "fr archive --branch $branch" "$out" "the brief archives the branch"
  refuse_grep 'housekeeping|git add -A|isolation up --branch chore/' "$out" \
    "the brief brings up no housekeeping workspace or PR under this placement"
  run_fr out closeout outcome --run "$run" --step 1 --ran --evidence "the unit tests pass"
  require_exit 0 "$out"
  run_fr out archive --branch "$branch"
  require_exit 0 "$out"
  expect_grep "recorded: $branch merged at" "$out" "archive records the merge (R25)"
  # ...and pushed it: the remote state branch holds the feature's merged record.
  # WALK_STATE = "<bare git dir> <branch> <prefix>" (quiet: origin's `fr`; stealth: the
  # tracking repo's branch below the target's directory).
  local state_git state_ref state_prefix
  read -r state_git state_ref state_prefix <<<"$WALK_STATE"
  git --git-dir="$state_git" cat-file -e \
    "$state_ref:${state_prefix}features/${branch//\//__}/merged.yaml" \
    || fail "the remote $state_ref has no merged record for $branch"
  cd "$base" || fail "cd $base"
  run_fr out isolation down --branch "$branch"
  require_exit 0 "$out"
}
