# Journal: 2026-07-22-fr-goal-subagent-execution

<!-- fr:journal kind=finding scope=plan id=review-f1-render-markup created=2026-07-23T15:28:50 phase=2 state=fixed -->
### review-f1-render-markup · finding [fixed] · render used a Rich console — bracketed PR-body text was mangled (phase 2)

fr journal render fed console.print (markup on), so a finding body with [links] or [PR #12] lost the brackets. Fixed: render now emits raw via typer.echo. Test: test_render_emits_brackets_verbatim.

<!-- fr:journal kind=finding scope=plan id=review-f3-id-whitespace created=2026-07-23T15:28:51 phase=1 state=fixed -->
### review-f3-id-whitespace · finding [fixed] · whitespace in a journal id corrupts the space-delimited header (phase 1)

The delimiter header is space-separated key=value; an id with a space breaks parsing. Fixed: JournalEntry validator rejects whitespace/empty ids. Test: test_id_rejects_whitespace.

<!-- fr:journal kind=finding scope=plan id=review-f2-body-heading created=2026-07-23T15:28:53 phase=1 state=refuted -->
### review-f2-body-heading · finding [refuted] · suspected: a body starting with a heading loses its first line on parse (phase 1)

Refuted: the parser pops exactly ONE heading line (the auto-heading), so a body whose first line is a markdown heading round-trips intact. Documented by test_body_starting_with_heading_round_trips.

<!-- fr:journal kind=discovery scope=plan id=p7-agent-delivery created=2026-07-23T15:30:19 phase=7 -->
### p7-agent-delivery · discovery · fr-phase-executor ships via the plugin cache rsync, no separate install copy (phase 7)

install.sh section 4 rsyncs the whole plugin dir to the cache, so agents/ rides along automatically (unlike rules, which copy to ~/.claude/rules). P7.T2's planned test_install_copies_agents would be redundant; agent presence is already guarded by test_phase_executor_agent.py.
