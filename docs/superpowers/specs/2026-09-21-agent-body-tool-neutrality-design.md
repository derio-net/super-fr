# The phase-executor agent body must be neutral, and the neutrality tripwire must see agents

- **Issue:** [#497](https://github.com/derio-net/super-fr/issues/497)
- **Date:** 2026-09-21
- **Status:** designed

## 1. Problem

`plugins/super-fr/agents/fr-phase-executor.md` names Claude Code's dispatch flag
`isolation: "worktree"` (frontmatter `description`, and body §"A second worktree" and the
"Long commands" section) and Claude Code's `Agent` tool, each as though every reader were
on Claude Code. Nothing scopes them to a harness.

Agent files sit outside the tool-neutrality tripwire: `_SKILL_TREES` in
`tests/unit/test_tripwire_skill_tool_neutrality.py` globs only `*/SKILL.md`, so
`plugins/super-fr/agents/` and `.opencode/agent/` are never scanned. It has got worse since
the issue was filed: `.opencode/agent/` is now a generated surface and
`test_opencode_agent_mirror.py` asserts the body stays canonical across all four tier
files, so the Claude-only prose is guaranteed by a passing test to reach every OpenCode
agent file. (Hermes has no agent mirror — `delegate_task` takes no agent file — so there
are two trees to cover, not three.)

Live check on the pre-fix tree: `scan_prose` already flags `Agent` (claude-code) at
canonical line 33 and line 28 of each of the four OpenCode files; the flag itself is not in
`TOOL_VOCABULARY`, so no scan sees it at all.

## 2. Design (smallest correct change)

1. **Rewrite as a scoped clause.** The "A second worktree" paragraph becomes a
   `**Harness — dispatch isolation:**` clause naming all three supported harnesses (the bar
   `fr.harness.prose` enforces): Claude Code — the flag and the `fr-phase-executor-guard.sh`
   hook that refuses it; OpenCode and Hermes — their dispatch primitive has no isolation
   argument, so there is nothing to refuse and this case cannot arise. The "no `Agent` tool /
   `task: deny`" sentence likewise moves into a `**Harness — no dispatch:**` clause. The
   "Long commands" mention is reworded neutrally ("a second worktree is forbidden by
   design"). The frontmatter `description` is reworded neutrally ("dispatch it into the
   already-active workspace, never a second worktree") — it cannot sit inside a clause, and
   it is the first thing every harness reads.
2. **One canonical source, byte-identical mirrors.** No sync-script change: the four
   OpenCode files re-generate from the edited canonical.
3. **Widen the tripwire.** `_SKILL_TREES` gains an agents companion: canonical
   `plugins/super-fr/agents/*.md` and `.opencode/agent/*.md`, scanned by the same
   `scan_prose`, with a not-empty guard per tree.
4. **Teach the scan the flag.** `scan_prose` takes an optional `extra_tools` mapping so the
   agent test can additionally flag `isolation: "worktree"` (claude-code) outside a scoped
   clause, *without* adding it to `TOOL_VOCABULARY` — registering it there would fire on
   `fr-goal` §2's legitimate cross-repo mention, which is a separate, un-scoped skill
   sentence and out of scope here.

## 3. Non-goals

- Not registering the flag in the global vocabulary, and not touching `fr-goal` §2.
- No Hermes agent mirror (there is none).
- No change to the guard hook or the OpenCode agent generator.

## 4. Known limit (stated, not hidden)

A clause is judged syntactically (names every supported harness); it cannot judge that the
clause is *useful*. Review carries that.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| agent-body-tool-neutrality | `derio-net/super-fr` | `agent-body-tool-neutrality` | — |
