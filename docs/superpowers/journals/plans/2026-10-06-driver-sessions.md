# Journal: 2026-10-06-driver-sessions

<!-- fr:journal kind=decision scope=plan id=plan-shape created=2026-10-06T18:52:57+00:00 -->
### plan-shape · decision · Three agentic phases, one per reviewable ask; no member issue is a tracking_issue

P1 restart engine + CLI + install (skeleton,

<!-- fr:journal kind=discovery scope=plan id=herdr-agent-start-name-reuse created=2026-10-06T19:30:58+00:00 phase=1 -->
### herdr-agent-start-name-reuse · discovery · herdr accepts the pane's own agent name again right after /exit; it refuses only when another pane holds it (phase 1)

Probed live (herdr 0.9.1) in scratch tabs. After `/exit` the pane drops out of `agent list` (the name is released), and `agent start <same name> --kind claude --pane <same pane> -- --resume <id>` is ACCEPTED with the same agent_session.value and name (fixture agent-start-reuse.json). A different pane starting a name another pane holds gets `agent_name_taken` (agent-start-name-taken.json). So the named `agent start` path is primary, and `agent_name_taken` alone triggers the send-text fallback.

<!-- fr:journal kind=discovery scope=plan id=claude-agent-count-is-not-background-work created=2026-10-06T19:30:58+00:00 phase=1 -->
### claude-agent-count-is-not-background-work · discovery · `← N agent` is on every idle Claude status line, so only shells/monitors and the agent panel mean background work (phase 1)

Spec §A treats `← N agent(s)` as background-agent evidence. Live, a freshly started session with nothing running already shows `← 1 agent`, and the count did not change while a background subagent ran (the status line then also showed `2 shells, 1 monitor` and an agent panel, `⏺ main` / `◯ general-purpose ...`, while herdr reported `done`). `has_background_work` therefore counts `N shells|monitors`, a `◯` panel row, or `← N agents` with N above 1. Using the spec's literal rule would have skipped nearly every pane. The hint segments also vanish from the status line while a draft is typed, and herdr still says `idle` then.

<!-- fr:journal kind=discovery scope=plan id=pane-read-is-raw-text created=2026-10-06T19:30:58+00:00 phase=1 -->
### pane-read-is-raw-text · discovery · `herdr pane read` prints raw terminal text, not a JSON envelope (phase 1)

`_run_herdr` returns it as `{"raw": <text>}` (stripped), so the screen fixtures are that return value and restart.py reads `.get("raw")`. process-info's foreground_processes also lists non-claude processes (MCP servers; one has no `argv` key), so the claude process is found by argv[0] basename, and its cwd (not the pane's) slugs the transcript path. An extra classify reason `no-process` covers a pane with no claude in the foreground.

<!-- fr:journal kind=discovery scope=plan id=exit-dialog-not-live-captured created=2026-10-06T19:30:58+00:00 phase=1 -->
### exit-dialog-not-live-captured · discovery · Claude's exit dialog is quoted from #964, not captured (phase 1)

An unsent feedback draft is not reproducible without sending feedback, so no fixture of the dialog exists; the engine matches "unsent feedback draft" / "Enter to review & send" in the visible text and the tests use that quoted string. The fixtures README says so.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-10-06T19:30:58+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

a smoke test over captured fixtures; no production code existed to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-10-06T19:30:58+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

cli.py is 58 lines of argparse over restart_idle written once to its tests; nothing duplicated or misnamed

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-10-06T19:30:58+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

shell and test additions follow the existing atomic_symlink and stub-uv patterns; nothing to tidy

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-10-06T20:44:54+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · restart_idle classified every pane from one initial agent list, so a pane that turned working during earlier serial restarts still got /exit (phase 1)

restart_idle classified every pane from one initial agent list, so a pane that turned working during earlier serial restarts still got /exit

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-10-06T20:44:54+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · has_draft failed open when no line started exactly with the prompt glyph (phase 1)

has_draft failed open when no line started exactly with the prompt glyph

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-10-06T20:44:54+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · only the first input line was checked, so a multi-line draft with an empty first line was missed (phase 1)

only the first input line was checked, so a multi-line draft with an empty first line was missed

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-10-06T20:44:54+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · the named relaunch did not retry agent_pane_busy like the runner does (phase 1)

the named relaunch did not retry agent_pane_busy like the runner does

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-10-06T20:44:54+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · only HerdrError was caught, so an OSError or non-dict herdr answer aborted the run and lost the resume line (phase 1)

only HerdrError was caught, so an OSError or non-dict herdr answer aborted the run and lost the resume line

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-10-06T20:44:54+00:00 phase=1 state=open review_scope=in -->
### p1-r6 · finding [open] (reviewer: in scope) · spec §A/R2 were not amended for the live discoveries (phase 1)

spec §A/R2 were not amended for the live discoveries

<!-- fr:journal kind=finding scope=plan id=p1-r7 created=2026-10-06T20:44:54+00:00 phase=1 state=open review_scope=in -->
### p1-r7 · finding [open] (reviewer: in scope) · a lone background subagent was caught only by one captured panel glyph (phase 1)

a lone background subagent was caught only by one captured panel glyph

<!-- fr:journal kind=finding scope=plan id=p1-r8 created=2026-10-06T20:44:54+00:00 phase=1 state=open review_scope=in -->
### p1-r8 · finding [open] (reviewer: in scope) · the resume confirmation could accept a stale pre-exit agent-list entry (phase 1)

the resume confirmation could accept a stale pre-exit agent-list entry

<!-- fr:journal kind=finding scope=plan id=p1-r9 created=2026-10-06T20:44:54+00:00 phase=1 state=open review_scope=in -->
### p1-r9 · finding [open] (reviewer: in scope) · the relaunch and resume line assumed the shell cwd equals the claude cwd (phase 1)

the relaunch and resume line assumed the shell cwd equals the claude cwd

<!-- fr:journal kind=finding scope=plan id=p1-r10 created=2026-10-06T20:44:54+00:00 phase=1 state=open review_scope=in -->
### p1-r10 · finding [open] (reviewer: in scope) · HERDR_PANE_ID was not recorded and the tab list shape was never captured (phase 1)

HERDR_PANE_ID was not recorded and the tab list shape was never captured

<!-- fr:journal kind=finding scope=plan id=p1-r11 created=2026-10-06T20:44:54+00:00 phase=1 state=open review_scope=in -->
### p1-r11 · finding [open] (reviewer: in scope) · install.sh passed --with-executables-from unconditionally, failing older uv (phase 1)

install.sh passed --with-executables-from unconditionally, failing older uv

<!-- fr:journal kind=discovery scope=plan id=p1-install-atomic-load-flake created=2026-10-06T20:44:54+00:00 phase=1 -->
### p1-install-atomic-load-flake · discovery · test_fr_stays_runnable_throughout_a_reinstall failed once (1/225 fr calls) under full -n auto load (phase 1)

Seen once in the fix round's first full-suite run; the fr link swap itself is unchanged by this branch (only a separate fr-herdr link is added after each fr swap). Six reruns of the file under -n 6 all passed and the final full suite was green. Recorded as a load-sensitive window in the test, not a defect of this change.

<!-- fr:journal kind=review scope=plan id=review-p1 created=2026-10-06T20:44:54+00:00 phase=1 -->
### review-p1 · review · phase 1 independent review: 11 findings, all in scope, all fixed (phase 1)

Independent reviewer (separate context) raised p1-r1..p1-r11, all in scope; each verified against the code and fixed with a test by a fix round (head 82bb4c1fd); full suite green: 9792 passed, 105 skipped (/private/tmp/claude-502/driver-sessions-p1-review-suite.log).

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-10-06T20:44:54+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: restart_idle classified every pane from one initial agent list, so a pane that turned working during earlier serial restarts still got /exit (phase 1)

Each pane's agent-list entry is re-read right before classifying it (`gone` if absent); tests test_r1_*.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-10-06T20:44:54+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: has_draft failed open when no line started exactly with the prompt glyph (phase 1)

Prompt located after stripping SGR, as the last prompt line under a rule; no prompt -> skip `no-prompt`; test_r2_*.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-10-06T20:44:54+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: only the first input line was checked, so a multi-line draft with an empty first line was missed (phase 1)

Every input-box line up to the closing rule is checked, faint state carried across lines; live-captured fixture; test_r3_*.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-10-06T20:44:54+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: the named relaunch did not retry agent_pane_busy like the runner does (phase 1)

Shared start_agent retry moved into _herdr.py, used by runner and restart; test_r4_*.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-10-06T20:44:54+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: only HerdrError was caught, so an OSError or non-dict herdr answer aborted the run and lost the resume line (phase 1)

Per-pane catches broadened to Exception mapped to fail/skip unreadable with the resume line kept; _run_herdr always returns a dict; test_r5_*.

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-10-06T20:44:54+00:00 phase=1 state=fixed resolves=p1-r6 -->
### p1-r6-resolved · finding [fixed] · resolves p1-r6: spec §A/R2 were not amended for the live discoveries (phase 1)

Spec R2, §A and Install amended: background-work rule, no-process/no-prompt/gone/unreadable skips, raw pane read, absent name, status re-read, retry, broad catch, resume process check, cwd handling, HERDR_PANE_ID, name reuse, conditional install flag.

<!-- fr:journal kind=finding scope=plan id=p1-r7-resolved created=2026-10-06T20:44:54+00:00 phase=1 state=fixed resolves=p1-r7 -->
### p1-r7-resolved · finding [fixed] · resolves p1-r7: a lone background subagent was caught only by one captured panel glyph (phase 1)

Captured a subagent-only screen in a scratch tab (fixture screen-subagent.json); herdr also reports `working` while it runs, a second guard; test_r7_*.

<!-- fr:journal kind=finding scope=plan id=p1-r8-resolved created=2026-10-06T20:44:54+00:00 phase=1 state=fixed resolves=p1-r8 -->
### p1-r8-resolved · finding [fixed] · resolves p1-r8: the resume confirmation could accept a stale pre-exit agent-list entry (phase 1)

Resume also requires a foreground claude in process-info; test_r8_*.

<!-- fr:journal kind=finding scope=plan id=p1-r9-resolved created=2026-10-06T20:44:54+00:00 phase=1 state=fixed resolves=p1-r9 -->
### p1-r9-resolved · finding [fixed] · resolves p1-r9: the relaunch and resume line assumed the shell cwd equals the claude cwd (phase 1)

Shell cwd read after exit; `cd <claude cwd>` sent before relaunch when it differs; the resume line carries the cd; test_r9_*.

<!-- fr:journal kind=finding scope=plan id=p1-r10-resolved created=2026-10-06T20:44:54+00:00 phase=1 state=fixed resolves=p1-r10 -->
### p1-r10-resolved · finding [fixed] · resolves p1-r10: HERDR_PANE_ID was not recorded and the tab list shape was never captured (phase 1)

tab list captured live and redacted (restart/tab-list.json), served by the scenario's fake herdr, labels asserted; README notes HERDR_PANE_ID; test_r10_*.

<!-- fr:journal kind=finding scope=plan id=p1-r11-resolved created=2026-10-06T20:44:54+00:00 phase=1 state=fixed resolves=p1-r11 -->
### p1-r11-resolved · finding [fixed] · resolves p1-r11: install.sh passed --with-executables-from unconditionally, failing older uv (phase 1)

Flag passed only when `uv tool install --help` lists it; fr-herdr linked from the tool env bin otherwise; tests in test_install_sh.py and candidate-install.
