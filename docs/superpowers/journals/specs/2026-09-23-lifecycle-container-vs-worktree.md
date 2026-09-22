# Journal: 2026-09-23-lifecycle-container-vs-worktree

<!-- fr:journal kind=decision scope=spec id=d1 created=2026-09-23T00:55:25 -->
### d1 · decision · #575: preserved cursor restores automatically on the next up --branch

Operator batch Q1: auto-restore on the up that re-creates the worktree (absent files only, never overwrite), over an explicit fr run restore verb or message-only.

<!-- fr:journal kind=decision scope=spec id=d2 created=2026-09-23T00:55:25 -->
### d2 · decision · #471: exec auto-resumes a stopped container via devcontainer up

Operator batch Q2: resume (with stderr notice, re-runs postStart) over refusing with the resume command. gc --stop-idle deferred per the goal statement.

<!-- fr:journal kind=decision scope=spec id=d3 created=2026-09-23T00:55:26 -->
### d3 · decision · #577: new verb fr isolation rebuild

Operator batch Q3: a distinct verb over restart --rebuild; restart keeps its install-preserving meaning.

<!-- fr:journal kind=decision scope=spec id=d4 created=2026-09-23T00:55:26 -->
### d4 · decision · #438: diverged local/remote keeps local with a warning; remote-only reuses; --base + origin/<B> refuses

Operator batch Q4: keep local and name both tips, over refusing divergence.

<!-- fr:journal kind=decision scope=spec id=d5 created=2026-09-23T00:55:26 -->
### d5 · decision · Model tiers: claude-code tiers already bound to claude-opus-5-5

fr models resolve --harness claude-code returns claude-opus-5-5 for mechanical/standard/hard/orchestrator; no change needed. OpenCode tiers left alone: claude-opus-5-5 is not an OpenCode model id and this run is on Claude Code.
