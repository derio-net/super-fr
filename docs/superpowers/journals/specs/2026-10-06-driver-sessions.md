# Journal: 2026-10-06-driver-sessions

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-10-06T18:40:21+00:00 input=true -->
### operator-brief · discovery · Operator brief (batch driver-sessions), verbatim

/fr-goal Driver sessions stay current and portable: idle sessions restart on new plugins, and the driver runs outside herdr

Batch `driver-sessions` of derio-net/super-fr: 3 issues, delivered as ONE pull request.

## super-fr#964: fr-herdr: restart idle Claude sessions in place so they load new plugins (wave driver post_merge)
Long drives leave running Claude sessions on the plugins they started with; post_merge installs a new fr they never load.
Note: Herdr runner reliability, see the pattern.

## super-fr#878: herdr runner only dispatches inside a herdr session, so `fr triage batch drive` inherits that
The herdr runner's preflight needs `HERDR_ENV`/`HERDR_WORKSPACE_ID`, so the driver can only run inside a herdr session.

## super-fr#1029: Drive: report a batch or close-out session idle with no progress past a threshold
The driver never reports a batch or close-out session that stays idle with no progress; #1028 fixed the unsubmitted brief, this is #956's second half.
Note: Split from super-fr#956. Batch driver-sessions.

## Why these belong together
Wave 9 feature 1: stale sessions after post_merge cost hand-offs all of 2026-10-06. After drive-board-lows (same driver files).

## Delivery rules
- Work on branch `feat/batch-driver-sessions`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#964
  Closes derio-net/super-fr#878
  Closes derio-net/super-fr#1029
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

<!-- fr:journal kind=decision scope=spec id=q1-outside-herdr created=2026-10-06T18:40:21+00:00 -->
### q1-outside-herdr · decision · #878: document only

Operator chose to keep the herdr runner's inside-herdr refusal and document it (refusal text + fr-triage skill), over accepting a reachable server or an explicit-session opt-in.

<!-- fr:journal kind=decision scope=spec id=q2-restart-scope created=2026-10-06T18:40:21+00:00 -->
### q2-restart-scope · decision · #964: restart every idle Claude pane

The restart covers every idle/done claude pane in herdr (the operator's other sessions too), minus drafts, dialogs, background work, no transcript and the caller's pane.

<!-- fr:journal kind=decision scope=spec id=q3-restart-verb created=2026-10-06T18:40:21+00:00 -->
### q3-restart-verb · decision · #964: fr-herdr console script

The operator-facing verb is a console script, fr-herdr restart-idle, shipped by the fr-herdr package; the driver reaches the same engine through an optional runner protocol.

<!-- fr:journal kind=decision scope=spec id=q4-driver-opt-in created=2026-10-06T18:40:21+00:00 -->
### q4-driver-opt-in · decision · #964: post_merge_restart config key

The wave driver opts in through .fr/triage.yaml post_merge_restart: idle (default none); super-fr's own config turns it on.

<!-- fr:journal kind=decision scope=spec id=q5-idle-threshold created=2026-10-06T18:40:21+00:00 -->
### q5-idle-threshold · decision · #1029: 60-minute default threshold

Stateless rule (runner says idle/done, event older than threshold, no PR / no archive PR), reported once and shown on the board; default idle_session_minutes 60, configurable per repo.

<!-- fr:journal kind=decision scope=spec id=q6-verification created=2026-10-06T18:40:21+00:00 -->
### q6-verification · decision · Verification: candidate + live rows

Run strategy candidate (walk with a fake herdr); the live in-place restart row is verify live, walked by the operator after merge.
