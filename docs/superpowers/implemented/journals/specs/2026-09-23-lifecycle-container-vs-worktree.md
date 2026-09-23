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

<!-- fr:journal kind=review scope=spec id=r1 created=2026-09-23T01:03:58 -->
### r1 · review · Spec review r1 (independent reviewer): 24 findings, 23 fixed in spec, 1 refuted

Fixed: restore overwrites on base-blob match (committed-then-advanced cursor); runs filtered by branch; #354 invariant for ls-remote probe + explicit refspec for single-branch clones; behind/ahead local rows; run named in every refusal incl. --all --force preview; raw-YAML run discovery never raises; preserve stored under git common dir (repo-scoped, not basename); -z porcelain with rename/delete; two-phase tombstone after verified removal; --no-preserve escape; Target protocol + TeardownReport listed; journal-loader claim dropped; explain_missing at CLI layer, live-workspace first; not-found hint lists run ids; rebuild reclaims superseded <none> image on success only; exec refuses absent/dead (build != resume), unpause paused, FileNotFoundError caught; _devcontainer_up(worktree, profile); up keeps sessions/created_at; up output to stderr; descendant guard on restore; shared --force sentence updated; SKILL profile-switch line; rebuild reads branch's own config. #471 closes per operator's 'PR closes all four' with gc --stop-idle deferral recorded + follow-up issue. Refuted: 'acceptance rows missing' — 5 rows committed with the spec in 053c706e (fr acceptance check green).
