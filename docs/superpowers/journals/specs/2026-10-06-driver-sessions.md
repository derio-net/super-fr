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

<!-- fr:journal kind=finding scope=spec id=sr-1 created=2026-10-06T18:49:18+00:00 state=open review_scope=in -->
### sr-1 · finding [open] (reviewer: in scope) · install.sh never puts fr-herdr on PATH: uv's entry points go to a private bin dir and only `fr` is symlinked

install.sh installs into $HOME/.local/share/fr/uv-bin and atomic_symlinks only fr onto PATH (scripts/install.sh:776-807, :856), so --with-executables-from alone leaves fr-herdr off PATH.

<!-- fr:journal kind=finding scope=spec id=sr-2 created=2026-10-06T18:49:18+00:00 state=open review_scope=in -->
### sr-2 · finding [open] (reviewer: in scope) · The draft check reads Claude's prompt-suggestion ghost text as an unsent draft

A plain pane read cannot tell Claude's prompt suggestion after an idle prompt from typed input.

<!-- fr:journal kind=finding scope=spec id=sr-3 created=2026-10-06T18:49:18+00:00 state=open review_scope=in -->
### sr-3 · finding [open] (reviewer: in scope) · The run strategy is `candidate`, but no Verification row is candidate-walked

Every Verification row was none or live, so the candidate walk verified nothing.

<!-- fr:journal kind=finding scope=spec id=sr-4 created=2026-10-06T18:49:18+00:00 state=open review_scope=in -->
### sr-4 · finding [open] (reviewer: in scope) · The Test Plan names only the live row; CI tests are missing

The spec relied on CI tests that no section listed.

<!-- fr:journal kind=finding scope=spec id=sr-5 created=2026-10-06T18:49:18+00:00 state=open review_scope=in -->
### sr-5 · finding [open] (reviewer: in scope) · The design depends on herdr surfaces the repo has never called or captured

agent list / pane read / process-info / HERDR_PANE_ID / agent start name reuse were unconfirmed.

<!-- fr:journal kind=finding scope=spec id=sr-6 created=2026-10-06T18:49:18+00:00 state=open review_scope=in -->
### sr-6 · finding [open] (reviewer: in scope) · The transcript check can pass for a session `claude --resume` cannot find from the pane's cwd

A glob across every project dir accepts a transcript the relaunch will not find, stranding the pane after /exit.

<!-- fr:journal kind=finding scope=spec id=sr-7 created=2026-10-06T18:49:18+00:00 state=open review_scope=in -->
### sr-7 · finding [open] (reviewer: in scope) · The restart runs synchronously inside each _close_out, restarting every pane k times per pass

post_merge runs per close-out, so k close-outs meant k full restarts.

<!-- fr:journal kind=finding scope=spec id=sr-8 created=2026-10-06T18:49:18+00:00 state=open review_scope=in -->
### sr-8 · finding [open] (reviewer: in scope) · 'once per dispatch' and 'once per drive' vs the warned set dying at every exec-restart

Requirements promised more than the in-memory warned set gives.

<!-- fr:journal kind=finding scope=spec id=sr-9 created=2026-10-06T18:49:18+00:00 state=open review_scope=in -->
### sr-9 · finding [open] (reviewer: in scope) · The board's `now` is ambiguous, and build_board's signature change is missing

Mixing live status with collected facts needed a stated clock.

<!-- fr:journal kind=finding scope=spec id=sr-10 created=2026-10-06T18:49:18+00:00 state=open review_scope=in -->
### sr-10 · finding [open] (reviewer: in scope) · views.needs_you labels every drive_pass warn 'failing-ci'

An idle warn reaching drive_snapshot would show as Failing CI.

<!-- fr:journal kind=finding scope=spec id=sr-11 created=2026-10-06T18:49:18+00:00 state=open review_scope=in -->
### sr-11 · finding [open] (reviewer: in scope) · The R7 focus command omits scope options

A pasted focus command may read another scope's state.

<!-- fr:journal kind=finding scope=spec id=sr-12 created=2026-10-06T18:49:18+00:00 state=open review_scope=in -->
### sr-12 · finding [open] (reviewer: in scope) · Spec names do not match code: _snapshot, FACTS Literal, test path, protocol list

Several names pointed at code that does not exist.

<!-- fr:journal kind=finding scope=spec id=sr-13 created=2026-10-06T18:49:18+00:00 state=open review_scope=in -->
### sr-13 · finding [open] (reviewer: in scope) · Restart preflight items unspecified; lazy import of fr_herdr.restart after post_merge mixes versions

preflight takes items; a lazy import after the env rebuild loads new restart.py beside old runner.py.

<!-- fr:journal kind=finding scope=spec id=sr-14 created=2026-10-06T18:49:18+00:00 state=open review_scope=in -->
### sr-14 · finding [open] (reviewer: in scope) · kept_args drops other launch flags silently

A resumed session could quietly lose --add-dir, --settings, --mcp-config...

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-10-06T18:49:18+00:00 -->
### spec-review-1 · review · independent spec review: 14 findings

fr-spec-reviewer (separate context) raised sr-1..sr-14, all in scope; all fixed in the spec. Decisions q1-q5 honoured; q6 was partly honoured (sr-3), now fixed.

<!-- fr:journal kind=finding scope=spec id=sr-1-resolved created=2026-10-06T18:49:18+00:00 state=fixed resolves=sr-1 -->
### sr-1-resolved · finding [fixed] · resolves sr-1: install.sh never puts fr-herdr on PATH: uv's entry points go to a private bin dir and only `fr` is symlinked

Spec §A Install: install.sh manages a second fr-herdr link beside fr's through the staged rebuild (gh#938); drift guards in tests/integration/test_install_sh.py; R5 states the outcome (on PATH beside fr).

<!-- fr:journal kind=finding scope=spec id=sr-2-resolved created=2026-10-06T18:49:18+00:00 state=fixed resolves=sr-2 -->
### sr-2-resolved · finding [fixed] · resolves sr-2: The draft check reads Claude's prompt-suggestion ghost text as an unsent draft

Verified live: `pane read --ansi` shows the suggestion as `❯\xa0\x1b[0m\x1b[2m<text>` (SGR 2 faint). Spec §A Draft now means non-faint text after the prompt on the ANSI screen; fixtures hold suggestion, draft and empty prompt; R2 says a suggestion is not a draft.

<!-- fr:journal kind=finding scope=spec id=sr-3-resolved created=2026-10-06T18:49:18+00:00 state=fixed resolves=sr-3 -->
### sr-3-resolved · finding [fixed] · resolves sr-3: The run strategy is `candidate`, but no Verification row is candidate-walked

Added `herdr-restart-idle: candidate` with scenario tests/scenarios/herdr-restart-idle.sh against a fake herdr (dry-run lines, skips, exit codes, refusal).

<!-- fr:journal kind=finding scope=spec id=sr-4-resolved created=2026-10-06T18:49:18+00:00 state=fixed resolves=sr-4 -->
### sr-4-resolved · finding [fixed] · resolves sr-4: The Test Plan names only the live row; CI tests are missing

Added a `## Testing` section mapping R1-R9 and the facts bump to their tests. The Test Plan stays post-merge-only, as fr-goal's brainstorm contract requires (the Test Plan holds only rows no pre-merge strategy can exercise), and now says so.

<!-- fr:journal kind=finding scope=spec id=sr-5-resolved created=2026-10-06T18:49:18+00:00 state=fixed resolves=sr-5 -->
### sr-5-resolved · finding [fixed] · resolves sr-5: The design depends on herdr surfaces the repo has never called or captured

Seen live while revising (agent list fields incl. name/agent_session, process-info foreground argv, pane read --ansi, HERDR_PANE_ID in the pane env); spec §A requires live captures under tests/fixtures/herdr/restart/ with READMEs, quotes the exit-dialog text from #964's live report, and specifies the name-collision fallback to send-text, probed live in a scratch tab and pinned by fixture.

<!-- fr:journal kind=finding scope=spec id=sr-6-resolved created=2026-10-06T18:49:18+00:00 state=fixed resolves=sr-6 -->
### sr-6-resolved · finding [fixed] · resolves sr-6: The transcript check can pass for a session `claude --resume` cannot find from the pane's cwd

Transcript is looked up only under the project dir derived from the pane's foreground claude cwd; every failure after /exit prints `resume by hand: claude <kept> --resume <id>`; exit timeout is `fail exit-timeout` with no further keys (R2, R3, §A).

<!-- fr:journal kind=finding scope=spec id=sr-7-resolved created=2026-10-06T18:49:18+00:00 state=fixed resolves=sr-7 -->
### sr-7-resolved · finding [fixed] · resolves sr-7: The restart runs synchronously inside each _close_out, restarting every pane k times per pass

_close_out only records the runner; the driver restarts once per recorded runner at the end of run_pass, after the close-outs (fresh sessions already load the merged plugins); bound stated (panes x 120 s per pass) (R6, §B).

<!-- fr:journal kind=finding scope=spec id=sr-8-resolved created=2026-10-06T18:49:18+00:00 state=fixed resolves=sr-8 -->
### sr-8-resolved · finding [fixed] · resolves sr-8: 'once per dispatch' and 'once per drive' vs the warned set dying at every exec-restart

R6 and R7 now say once per driver process, matching §D and Not in scope.

<!-- fr:journal kind=finding scope=spec id=sr-9-resolved created=2026-10-06T18:49:18+00:00 state=fixed resolves=sr-9 -->
### sr-9-resolved · finding [fixed] · resolves sr-9: The board's `now` is ambiguous, and build_board's signature change is missing

§D Board: build_board and _card gain `now`; write_board passes the wall clock; the threshold comes from facts.config_for in _card; the card states `no PR as of <collected_at>` so the stale-facts window is visible; --watch recollect narrows it.

<!-- fr:journal kind=finding scope=spec id=sr-10-resolved created=2026-10-06T18:49:18+00:00 state=fixed resolves=sr-10 -->
### sr-10-resolved · finding [fixed] · resolves sr-10: views.needs_you labels every drive_pass warn 'failing-ci'

Snapshot.idle defaults to (); views.drive_snapshot never fills it; a test pins drive_snapshot(...).idle == (); R8 states the needs-you list never shows an idle session as failing CI.

<!-- fr:journal kind=finding scope=spec id=sr-11-resolved created=2026-10-06T18:49:18+00:00 state=fixed resolves=sr-11 -->
### sr-11-resolved · finding [fixed] · resolves sr-11: The R7 focus command omits scope options

The command is shlex.join of `fr triage batch focus <batch> [--closeout]` plus self.scope_args, as dedupe_command does (R7, §D).

<!-- fr:journal kind=finding scope=spec id=sr-12-resolved created=2026-10-06T18:49:18+00:00 state=fixed resolves=sr-12 -->
### sr-12-resolved · finding [fixed] · resolves sr-12: Spec names do not match code: _snapshot, FACTS Literal, test path, protocol list

Fixed: `_Driver.snapshot`; Facts.schema_ Literal and default widen with FACTS_SCHEMA 6; tests/integration/test_install_sh.py; SessionFocuser added to the protocol list.

<!-- fr:journal kind=finding scope=spec id=sr-13-resolved created=2026-10-06T18:49:18+00:00 state=fixed resolves=sr-13 -->
### sr-13-resolved · finding [fixed] · resolves sr-13: Restart preflight items unspecified; lazy import of fr_herdr.restart after post_merge mixes versions

Preflight uses probe_item(repo, batch, closeout=True, prefix=...); runner.py imports fr_herdr.restart at module top level (§A, §B).

<!-- fr:journal kind=finding scope=spec id=sr-14-resolved created=2026-10-06T18:49:18+00:00 state=fixed resolves=sr-14 -->
### sr-14-resolved · finding [fixed] · resolves sr-14: kept_args drops other launch flags silently

kept_args keeps --model, --permission-mode, --dangerously-skip-permissions, --add-dir, --settings, --mcp-config, --plugin-dir, --agent; drops only resume/continue/session-id; any other flag or positional makes the pane `skip unknown-flag <flag>` (R2, R3, §A).
