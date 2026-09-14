# Journal: 2026-09-14-statusline-session-branch

<!-- fr:journal kind=decision scope=spec id=d1-location created=2026-09-14T19:11:37 -->
### d1-location · decision · d1 Location: super-fr segment + local wiring, versions for every supported harness

Operator: option 1 (super-fr segment prints branch/worktree rows, golden tests, skill wiring, acceptance row; operator statusline.sh rewired post-merge), plus ship versions for all supported harnesses (claude-code, opencode, hermes).

<!-- fr:journal kind=decision scope=spec id=d2-layout created=2026-09-14T19:11:53 -->
### d2-layout · decision · d2 Layout: line 2 'branch: <b> | ~/cwd', line 3 'worktree: <path>' or 'no fr-isolation'

Operator chose the recommended layout. The 'iso: ?' hint and the other-worktrees gauge are removed.

<!-- fr:journal kind=decision scope=spec id=d3-branch created=2026-09-14T19:12:08 -->
### d3-branch · decision · d3 Branch: bound workspace branch, else cwd branch, else 'no branch'; purple unbound, green fr

Operator: option 1 with colour: purple (ANSI 35) when not fr-bound, green (ANSI 32) when fr-bound. Detached HEAD / non-repo -> 'no branch'.

<!-- fr:journal kind=decision scope=spec id=d4-worktree created=2026-09-14T19:12:24 -->
### d4-worktree · decision · d4 Worktree: session binding, or cwd toplevel is an fr workspace; colour rule applies

Operator: option 1 and the same colour rule. Native .claude/worktrees/agent-* and plain git worktrees show 'no fr-isolation'.

<!-- fr:journal kind=decision scope=spec id=d5-harness-reality created=2026-09-14T19:12:40 -->
### d5-harness-reality · decision · d5 Harness versions: neutral core + Claude Code wiring; Hermes one-line adapter pending hermes-agent#109596; OpenCode documented gap

Research 2026-09-14: OpenCode has no status-line hook (anomalyco/opencode#37464, #30295 open; ocstatusline has no command widget). Hermes custom status-bar command is PR NousResearch/hermes-agent#109596, open, first line only, 40 chars. Decision (agent, flagged to operator): ship the harness-neutral segment with a oneline format, a Claude Code reference status line, a Hermes adapter documented against the pending key without writing it into config.snippet.yaml, and document the OpenCode gap with the upstream issue.
