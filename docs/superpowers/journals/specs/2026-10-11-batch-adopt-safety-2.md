# Journal: 2026-10-11-batch-adopt-safety-2

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-10-11T18:48:13+00:00 input=true -->
### operator-brief · discovery · Batch adopt-safety-2 brief (#1081, #1069, #1071), verbatim

batch adopt: hold adopted agents, adopt sessions on main, better --list

Batch `adopt-safety-2` of derio-net/super-fr: 3 issues, delivered as ONE pull request.

## super-fr#1081: triage batch adopt: the R6 message sets adopted agents working; add --hold
Confirmed: the adopt message still says the session is `driven by fr triage batch drive` (`triage_batch_cmd.py:1730`) with no hold; 3 of 9 idle agents started work unasked (one pushed, one merged main).

## super-fr#1069: triage batch adopt: a session on the default branch cannot be adopted
`triage_batch_cmd.py:1581` still refuses the default branch. Held by scope `s-c8805331` (its driver stopped refreshing 2026-10-09 ~20:05 UTC; operator released these to this scope 2026-10-10) (batch `adopt-safety-and-discovery`).

## super-fr#1071: triage batch adopt --list: show branch, workspace and PR, and recognise all ref shapes
`adopt --list` found refs for 3 of 42 tabs, 2 wrong. Held by scope `s-c8805331` (its driver stopped refreshing 2026-10-09 ~20:05 UTC; operator released these to this scope 2026-10-10).

## Why these belong together
Re-run of adopt-safety, whose dispatch failed on 2026-10-11 (herdr: the brief was never submitted, no turn began). Adopt's message set idle agents working unasked.

## Delivery rules
- Work on branch `feat/batch-adopt-safety-2`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#1081
  Closes derio-net/super-fr#1069
  Closes derio-net/super-fr#1071
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

<!-- fr:journal kind=decision scope=spec id=hold-default created=2026-10-11T18:48:13+00:00 -->
### hold-default · decision · Hold is the default; --no-hold opts out

Operator chose: adopt's message always ends with an explicit hold (acknowledge only; no commits, merges, migrations, pushes or pipeline runs; wait for the operator); `--no-hold` drops it. Matches the operator's 'nothing without express confirmation' rule. (R1-R4)

<!-- fr:journal kind=decision scope=spec id=default-branch-cuts-workspace created=2026-10-11T18:48:13+00:00 -->
### default-branch-cuts-workspace · decision · A default-branch session gets a new fr workspace; dirty base clone refused

Operator chose: adopt runs the in-process `fr isolation up --branch feat/batch-<id>` from origin/<default>, binds the agent's session, and the held message names the workspace path for the agent to move to. A dirty base clone is refused; uncommitted work is never carried. (R5-R9)

<!-- fr:journal kind=decision scope=spec id=unpushed-default-refused created=2026-10-11T18:48:13+00:00 -->
### unpushed-default-refused · decision · Unpushed commits on the local default branch are refused

Operator chose: commits on local <default> that origin lacks refuse the adoption, listing them; adopt never resets or rewrites main. (R7)

<!-- fr:journal kind=decision scope=spec id=list-forge-reads created=2026-10-11T18:48:13+00:00 -->
### list-forge-reads · decision · --list reads the forge once per distinct ref and per repo+branch

Operator chose: classify each distinct ref issue-vs-PR once per listing, one open-PR lookup per session branch; a failed read prints `(?)` and the listing continues; no --offline flag. (R15-R17)

<!-- fr:journal kind=decision scope=spec id=verification-strategy created=2026-10-11T18:48:13+00:00 -->
### verification-strategy · decision · Verification: candidate scenarios + one post-merge live row

Operator chose: candidate strategy (installed build, scenarios over a fake herdr and fake gh for the held message and --list), default-branch path verified by CI unit tests over a real temp repo, plus one post-merge live row on the herdr host.
