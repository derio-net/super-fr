# Harness-specific arguments are vocabulary too — repairing #532 before the paid OpenCode run

- **Issue:** follow-up to [#497](https://github.com/derio-net/super-fr/issues/497) / PR
  [#532](https://github.com/derio-net/super-fr/pull/532)
- **Date:** 2026-09-22
- **Status:** designed
- **Source:** adversarial review of #532 (merged as `78aaa4be`), findings I2, I3, M1, M5;
  debug journal `2026-09-21-fr-goal-first-run-contracts` for how #532 was produced.

## 1. Problem

#532 fixed one Claude-Code-only phrase in the phase-executor agent and widened the
tool-neutrality tripwire to agent files. An independent review found the same class of
defect still live, one paragraph down, and the tripwire unable to see it.

1. **The executor's "Long commands" paragraph is Claude Code only**
   (`plugins/super-fr/agents/fr-phase-executor.md:119-122`, byte-identical in all four
   `.opencode/agent/*.md`). It says a foreground `Bash` call is moved to the background after
   120 s and to use `run_in_background`. Verified from source, 2026-09-22:
   - **OpenCode**'s bash tool takes `timeout` in ms (default 2 min, max 10 min) and **kills** the
     command on expiry; its `background` parameter was removed (changelog 2026-06-03)
     (`packages/opencode/src/tool/shell.ts`, `packages/core/src/tool/bash.ts`).
   - **Hermes** runs long commands as `terminal(command, background=true,
     notify_on_complete=true)` and manages them with `process(action=poll|wait|log|kill)`
     (hermes-agent `website/docs/reference/tools-reference.md`).

   On the paid OpenCode run the executor would be told to use an argument that does not
   exist, for the ~6-minute full suite — which OpenCode kills at 2 minutes by default.
2. **"This class cannot return" is not true.** Harness-specific *arguments* are not
   vocabulary: `isolation: "worktree"` is scanned only in agent trees (a test-local
   `extra_tools`), in one exact spelling (`isolation:"worktree"`, `isolation='worktree'`,
   `isolation="worktree"` all pass), and not at all in skills — where `fr-goal` §2 tells
   every harness to pass it. `run_in_background` is scanned nowhere.
3. **Rules are scanned by nothing.** The shipped `fr-isolation-required` rule names the flag,
   the `Agent` tool, `MultiEdit`/`NotebookEdit` and the hook matcher; its mirrors reach
   `.opencode/instructions/` and `.hermes/SOUL.d/` unchanged.
4. **The #420 description check #532 widened is loose.** Any `not`/`never`/`without` anywhere in
   the sentence satisfies it: "Dispatch it with a second worktree, not the shared one."
   passes.
5. **Stale surfaces:** the matrix row `harness-tool-neutrality` still says "No skill …";
   `AGENTS.md` still describes the tripwire as skills-only.

## 2. Decisions (operator, AskUserQuestion 2026-09-22 — spec journal)

- **q1** Shared `ARGUMENT_VOCABULARY` in `fr.harness`; `extra_tools` removed.
- **q2** Rules are in scope, with their mirrors and the repo-local `.claude/rules`.
- **q3** In the #420 check, the negation must govern the phrase.
- **q4** A separate OpenCode smoke run precedes the paid run (Test Plan, §6).
- **d-headings-exempt** (agent, within scope) Markdown heading lines are not scanned.

## 3. Design

### A. `ARGUMENT_VOCABULARY` — a closed vocabulary of harness-specific arguments

Beside `TOOL_VOCABULARY` in `packages/fr/src/fr/harness/__init__.py`: keyed by every member of
`HARNESSES` (closed-world, like its sibling), each harness mapping an argument *name* (what a
violation reports) to a compiled-at-import regex:

| harness | name | pattern (case-sensitive) |
|---|---|---|
| claude-code | `isolation: "worktree"` | `isolation["'`]?\s*[:=]\s*["'`]?worktree(?![\w-])` |
| claude-code | `run_in_background` | `\brun_in_background\b` |
| hermes | `background=true` | `\bbackground\s*[:=]\s*(?:true|True)\b` |
| hermes | `notify_on_complete` | `\bnotify_on_complete\b` |
| opencode, codex, copilot-cli | — | — |

*Amended in phase 2's review (p2r-2, p2r-3, p2r-7):* the isolation pattern also matches the
dispatch tool's own input shape (`"isolation": "worktree"`) and a backticked value, and stops
at a hyphen (`worktree-mode` is a different word); the Hermes pattern matches Python's
`background=True` and a colon form.

OpenCode's `timeout` is deliberately NOT registered: it is ordinary English and would fire on
every sentence about a timeout — the same trade `TOOL_VOCABULARY` already states for `task`.
Stated as a limit, not hidden.

`scan_prose(text)` scans tool names AND argument patterns under the same clause rules; the
`extra_tools` parameter is removed, with its callers: the agent tripwire and three unit tests in
`tests/unit/test_harness_vocabulary.py` (`test_extra_tools_*`), which are rewritten against the
vocabulary (an argument is flagged, is excused by a valid clause, matches every spelling). No name may be
claimed by two harnesses (extends `test_no_tool_name_is_claimed_by_two_harnesses`).

### B. What the scanner skips

- **Markdown headings** (`^#{1,6} `): a heading names a topic, never an instruction.
- The **frontmatter `tools:` line** of an agent — already exempt in PR #536
  (`_without_tools_allowlist`, test-side). Whichever of #536 / this PR merges second keeps it.

### C. One tripwire over every surface a reader on any harness follows

`tests/unit/test_tripwire_skill_tool_neutrality.py` scans three families, canonical plus every
generated mirror:

| family | canonical | mirrors |
|---|---|---|
| skills | `plugins/super-fr/skills/*/SKILL.md` | `.opencode/skills/`, `.hermes/skills/fr/` |
| agents | `plugins/super-fr/agents/*.md` | `.opencode/agent/*.md` |
| rules | `plugins/super-fr/rules/*.md`, `.claude/rules/*.md` | `.opencode/instructions/*.md`, `.hermes/SOUL.d/*.md` |

A not-empty guard per tree, as today.

### D. Prose

- **Executor long commands** → `**Harness — long commands:**`, three verified arms (§1.1).
  The rules that hold on every harness stay unscoped: bounded waits, nothing left polling at
  handback (#503), read the command's own exit code.
- **`fr-goal` §2** cross-repo dispatch: *corrected in phase 3's review (p3r-1)* — this spec first
  said "Claude Code keeps the flag for a fresh pipeline in another repo", repeating a long-standing
  false premise: `fr-worktree-create.sh` leaves `agent-*` worktrees at Claude's default, cut under
  the CALLER's toplevel, so the flag yields a worktree of the current repo. Every harness's agent
  enters isolation in its own repo, `fr isolation up --repo <path> --branch <b>` (a delegated agent
  inherits the parent's cwd); the scoped clause states only what the flag does and does not do.
- **Rules**: every Claude-only mention in `fr-isolation-required`, `fr-worktree-override`,
  `fr-plan-override` scoped; the hand-maintained `.claude/rules/fr-isolation-required.md` updated
  by hand (no script covers it — AGENTS.md).

### E. #420 description check

`_rules_out_a_second_worktree` requires, within one clause (split on `.;—`), a negation token
(`never|without|not|no`) followed within six words by the phrase (`second worktree` or an
`ARGUMENT_VOCABULARY` isolation match). Must fail: the review's four counterexamples. Must pass:
the shipped description and the pre-#532 literal-flag wording.

*Amended in phase 4:* a six-word window alone passes the review's third counterexample —
`Do not hesitate to pass isolation: "worktree"` puts `not` three words before the flag while
negating *hesitate*. So every word between the negation and the phrase must also be filler
(`into|in|a|an|the|any|pass|passing|use|using|with`): the negation must govern the phrase, not
merely precede it.

### F. Stale surfaces

Matrix row `harness-tool-neutrality`: acceptance sentence names skills, agents and rules, notes
record the argument vocabulary (sentence edit + `set-status --notes`, reports regenerated).
`AGENTS.md` updated in two places that say skills-only: line 93 ("the sibling tool-neutrality
scanner over skill prose") and lines 343-344 ("over the canonical skills plus both mirrors").

## 4. Non-goals

- Behaviour claims ("moved to the background after 120 seconds") cannot be scanned; scoping them
  is review's job, as §3.C.3 of the parity spec already says of clause usefulness.
- No change to the guard hook, the OpenCode agent generator, or the Hermes adapter.

## 5. Acceptance rows

- `harness-argument-neutrality` — a harness-specific argument named outside a scoped clause, in
  any skill, agent or rule (canonical or mirror), in any spelling, fails CI.
- `executor-long-commands-per-harness` — the phase executor tells a reader on each harness how to
  run a command longer than that harness's foreground limit, and to leave nothing running.
- `phase-executor-description-rules-out-second-worktree` — the #420 description check fails a
  description that merely mentions a second worktree.

## 6. Test Plan (post-merge — operator-driven)

1. Confirm the OpenCode node runs the released version that contains this PR
   (`fr --version`, and the materialised `~/.config/opencode/agent/fr-phase-executor*.md`
   carries the `Harness — long commands` clause).
2. **Smoke**: dispatch `fr-phase-executor` on OpenCode for a toy phase whose suite takes > 2 min
   (e.g. a `sleep 150` test). Pass = the executor passes an explicit `timeout` (or detaches and
   polls boundedly), the suite is not killed, and no process it started is alive at handback.
3. Only then, the paid verification run.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-09-22-harness-argument-neutrality | `derio-net/super-fr` | `2026-09-22-harness-argument-neutrality` | — |
