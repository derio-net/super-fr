# fr-goal isolation deadlocks: poisoned phase-executor dispatch & unreachable second repo

**Date:** 2026-07-26
**Status:** Approved for implementation (fr-goal run, non-interactive dispatch —
see "Decisions taken without the Q&A" below).
**Source:** derio-net/super-fr#420 and #421, both filed 2026-07-26 from one live
`/fr-goal` run in `derio-net/blog-craft` on super-fr 3.18.1.
**Target repo:** derio-net/super-fr (`plugins/super-fr/hooks/`,
`plugins/super-fr/skills/fr-goal/`, `plugins/super-fr/agents/`,
`scripts/ensure-phase-executor-allowlist.sh`).

## Problem

Two hooks each deadlock fr-goal, at different steps, for unrelated reasons.
They are separate root causes in separate files, scheduled together because
both gate fr-goal itself.

### #420 — the phase dispatch succeeds and is silently poisoned (fr-goal §6)

`agent-worktree-required.sh` (the operator-owned org hook) allows on the flag
**before** it consults its allowlist:

```bash
isolation=$(… '.tool_input.isolation // empty')
[ "$isolation" = "worktree" ] && exit 0      # ← unconditional allow
case "$subagent_type" in
  super-fr:fr-phase-executor|Explore|Plan|…) exit 0 ;;
esac
exit 2
```

So the allowlist can only ever mean *"you needn't pass the flag"* — never
*"you mustn't"*. Dispatching `super-fr:fr-phase-executor` **with**
`isolation: "worktree"` therefore succeeds, and fr-goal looks healthy, while
the executor wakes in a **separate locked worktree cut from `main`**:

1. the spec and plan live on the feature branch and are invisible, so
   `fr pickup <plan-dir>` — the dispatch contract — is unsatisfiable;
2. every Bash command is denied by `fr-isolation-guard.sh` (the agent worktree
   sits under `<base-repo>/.claude/worktrees/`, i.e. *inside* the sentinel's
   `repo_root`, and its own path is not an allowed `cd` target);
3. every Write/Edit is denied by `fr-isolation-required.sh` (a fresh checkout
   has no `.fr-isolation` marker; the hook is fail-closed);
4. the one surviving channel, `fr isolation exec`, runs in the *parent's*
   devcontainer, so any edit it makes lands unattributed to the phase.

Three things actively encourage the poisoned shape, and nothing refuses it:
the org rule `agent-worktree-default.md` instructs *"always pass
`isolation: "worktree"`"* for any subagent with Edit/Write and does not list
`fr-phase-executor`; fr-goal §3 uses the flag **correctly** for cross-repo
agents while §6 must **not**, and the skill never distinguishes them; and
`agents/fr-phase-executor.md` puts the constraint in its *body*, which only the
executor reads — the `description:`, which the orchestrator reads when
choosing, is silent.

This is the mirror image of the bug `ensure-phase-executor-allowlist.sh`
already fixed. That one degraded **silently to inline**; this one **dispatches
and is silently poisoned**.

### #421 — a session holding a pipeline in repo A cannot reach repo B (fr-goal §3)

`fr-isolation-guard.sh` is correctly repo-scoped (line 37 engages only when the
cwd resolves inside the sentinel's `repo_root`). But the harness's Bash tool
reports the **session** cwd as `.cwd` regardless of any inline `cd`, so for a
pipeline session `rcwd` is always the base repo, the guard always engages, and
everything hinges on two escapes — **neither of which can reach a second
repo, and which cannot be composed**:

- the `cd` transition allowance (`:51-72`) accepts only
  `FR_CD_ALLOW_PREFIXES`, defaulting to `$HOME/.cache/fr/worktrees:/tmp:$TMPDIR`
  — another repo is never an allowed target;
- the `fr isolation …` allowance (`:84`) is start-anchored
  (`^[[:space:]]*fr[[:space:]]+isolation`), so a command that must lead with
  `cd <other-repo>` to be in the right place starts with `cd`, not `fr`.

You can lead with `cd`, or you can start with `fr isolation`, but not both.
The guard's own remedy text recommends `fr isolation up` — which is itself
denied. The `:101-107` self-heal does not help: it fires only when the sentinel
has outlived *all* linked worktrees, and here the pipeline's worktree is alive.

The consequence is not cosmetic: **fr-goal §3 dispatches one agent per repo for
a cross-repo spec**, and those agents inherit the same session sentinel and the
same base-repo cwd. The multi-repo story is unreachable from the flow that
defines it.

## Decisions taken without the Q&A

This run is a non-interactive dispatch with no `AskUserQuestion` tool, so
fr-goal §1's single operator touchpoint could not execute. Both issues carry
recommended options (#421 lists them "in increasing order of ambition" and
names the first as minimal and obviously correct; #420 carries a follow-up
comment that explicitly settles its delivery question), so the four
operator-owned decisions were taken explicitly rather than blocking. Each is a
`decision` entry in the spec journal
(`docs/superpowers/journals/specs/2026-07-26-fr-goal-isolation-deadlocks.md`)
and is called out in the PR body for override.

1. **The #420 backstop ships as a super-fr plugin hook, not an org-hook
   mutation.** The issue's comment argues the fix must ride a universally
   reachable, *versioned* lever, and rejects prose precisely because
   `agent-worktree-default.md` "has no canonical copy in any repo".
   `plugins/super-fr/hooks/hooks.json` satisfies that reasoning strictly better
   than mutating `~/.claude/hooks/agent-worktree-required.sh`: it is versioned
   in-repo, unit-testable, and already the delivery path that puts
   `fr-isolation-guard.sh` and `fr-isolation-required.sh` on every host. Claude
   Code runs **every** matching PreToolUse hook and a `deny` wins, so a
   super-fr-owned refusal overrides the org hook's early `exit 0` without
   editing a file super-fr does not own. The org hook still receives the
   checklist's stderr repair through `ensure-phase-executor-allowlist.sh`.
2. **The refusal is unconditional, not gated on a live pipeline sentinel.**
   #420's checklist says "while a pipeline sentinel is live", but
   `fr-pipeline-sentinel.sh` deliberately writes **no** sentinel when the
   session cwd is a linked worktree ("this IS the isolation workspace") —
   which is exactly where an fr-goal session lives after §1. A sentinel-gated
   backstop would stay silent for worktree-launched fr-goal runs, reproducing
   the silent poisoning it exists to stop. `super-fr:fr-phase-executor` +
   `isolation == worktree` is never a valid combination, so no gate is needed.
3. **#421's chained-`cd` circumvention is blessed, not closed.**
   `cd /tmp && cd <other-repo> && …` is the same shape an existing test already
   blesses by name — `test_cd_then_back_into_repo_allowed_by_design`, whose
   docstring cites the guard's own axiom, *"discipline backstop, not a security
   boundary"*. Closing it would flip that test and re-characterise the hook.
   Per-repo sentinels are declined: #421 itself flags a multi-repo fr workspace
   as desired-but-not-designed and warns against scope creep.
4. **Version bump: minor.** Per AGENTS.md, minor covers "user-visible workflow
   additions (new subcommand/skill/**mandatory behavior**)". This ships a new
   hook that refuses a previously-succeeding dispatch plus a new allowance in
   an existing hook.

## Design

### A. `fr-phase-executor-guard.sh` — a new PreToolUse(Agent) refusal

A new hook at `plugins/super-fr/hooks/fr-phase-executor-guard.sh`, registered
in `plugins/super-fr/hooks/hooks.json` under a `PreToolUse` matcher for
`Agent`, mirroring the existing `Bash` and `Edit|Write|…` entries.

Contract, in order:

1. `tool_name != "Agent"` → `exit 0`.
2. `subagent_type` is neither `super-fr:fr-phase-executor` nor the bare
   `fr-phase-executor` → `exit 0`. (Both spellings, for the same reason
   `ensure-phase-executor-allowlist.sh` documents: Claude Code sends the
   plugin-qualified id, but a locally-installed copy sends the bare name.)
3. `isolation != "worktree"` → `exit 0` — **the correct dispatch shape**.
4. Otherwise emit `permissionDecision: "deny"` with a reason that names the
   deadlock and the fix.

The reason text must state the remedy — *re-dispatch without
`isolation: "worktree"`* — and say **why**: fr's worktree already **is** the
isolation, and the two mechanisms are mutually exclusive, not composable. A
soft warning is explicitly rejected: it reproduces today's silent failure.

Failure posture matches the sibling hooks: `set -eu`, `jq` for parsing, and
`exit 0` on anything unrecognised (fail-open on shape, deny only on a positive
match).

**Delivery needs no new install step.** `scripts/install.sh` populates
`$MARKETPLACE_DIR` with `rsync -a --delete` of the whole repo root, and
`hooks.json`'s `${CLAUDE_PLUGIN_ROOT}` resolves inside it — so a hook that is
registered and executable ships automatically. Two existing tests must be
extended rather than left to fail:
`test_plugin_hooks.py::test_hooks_json_parses` asserts the **exact** set of
`PreToolUse` matchers (`{"Bash", "Edit|Write|MultiEdit|NotebookEdit"}`) and
will break on the new `Agent` entry; `test_registered_scripts_exist_and_are_executable`
already covers the executable bit generically and needs no change.

**Hermes needs no mirror.** Its harness dispatches subagents via
`delegate_task(goal, context)` (fr-goal §6), which has no `isolation`
parameter, so the poisoned shape is unrepresentable there. Nothing is added to
`plugins/super-fr/hooks/hermes/` or `.hermes/config.snippet.yaml`.

### B. Prose that stops instructing the poisoned shape

- **`plugins/super-fr/skills/fr-goal/SKILL.md` §6** states explicitly:
  dispatch the phase-executor **without** `isolation: "worktree"` — fr's
  worktree *is* the isolation — and contrasts that against §3, whose use of the
  flag is correct *because* those agents each start a fresh pipeline in a
  different repo. Without the contrast, §3 reads as precedent for §6.
- **`plugins/super-fr/agents/fr-phase-executor.md`** moves the constraint from
  the body into `description:` — the field the orchestrator reads when
  choosing an agent.
Only the **skill** has generated mirrors — `.opencode/skills/fr-goal/SKILL.md`
and `.hermes/skills/fr-goal/SKILL.md`, regenerated by
`scripts/sync-opencode.py` and `scripts/sync-hermes.py`, with tripwires failing
on drift. Neither `.opencode/` nor `.hermes/` carries an `agents/` tree, so
`agents/fr-phase-executor.md` has no mirror to regenerate.

### C. `ensure-phase-executor-allowlist.sh` — repair the stale stderr message

The org hook carries a `>&2` message enumerating the pre-fix five allowed types
(`Explore, Plan, claude-code-guide, statusline-setup,
hookify:conversation-analyzer`), so after the script edits the `case` arm three
lines above, the message contradicts it. The script gains a second, idempotent
`sed` that inserts `super-fr:fr-phase-executor` into that human-readable list
when it is present. It stays a **no-op** when the message is absent or already
correct — the org hook's shape is not super-fr's to depend on, so unlike the
`case` anchor this one must **not** fail loud on absence.

Note the existing idempotence lesson recorded in that file: a `grep -q` probe on
a substring a stale entry also satisfies reports "already done" forever. The
message repair is probed on its own text, independently of the `case` probe, so
a hook already carrying the qualified name in its `case` still gets its message
fixed.

### D. `fr-isolation-guard.sh` — make a second repo reachable

Two changes inside the existing leading-`cd` transition allowance, keeping its
current structure:

1. **Scope the deny by target, not only by cwd — and key the allowance on
   *isolation*, not on *repo identity*.** When the `cd` target lies outside
   `repo_root`, this pipeline's gate does not apply — its stated purpose is
   "commands whose cwd resolves inside **the pipeline's base repo**". But *"not
   this pipeline's business"* is **not** *"anything goes"*.

   The first cut allowed any *different git repo*. That reads harmless until
   you notice **`$HOME` is a git repo on any machine with a dotfiles repo** —
   at which point `~/.ssh` has a git toplevel, is not fr-enabled, and sails
   straight through. A fix for a deadlock must not widen reach to a private
   key as a side effect.

   So the destination must be a **genuine fr isolation workspace** — a valid
   `.fr-isolation` marker, this repo's worktree or another repo's — via a new
   `fr_isolation_marker_valid` in `hooks/lib/fr-isolation-decision.sh`. Note
   this is deliberately *stricter* than the lib's existing
   `fr_isolation_decide_cwd`, which answers "allowed" for any non-fr repo:
   correct for the edit gate (no business in a repo that never opted into fr),
   wrong as a *destination* test for exactly the dotfiles reason above.

   Everything else falls through, where the allowed-prefix loop still admits fr
   worktrees and temp dirs, and the `fr …` allowances still fire — so
   `cd <repo-B> && fr isolation up` works. **Reaching repo B's isolation is
   #421's entire ask**, and it never required repo B's base clone to be usable.
   The deny is a discipline, not a deadlock. `FR_BASE_OK=1` remains the
   one-shot escape.

   Two consequences worth stating:

   - A `cd` into another repo suppresses the sentinel retirement, so
     `cd <other-repo> && fr isolation down` cannot end *this* session's
     pipeline by action-at-a-distance.
   - That hop gets its **own** deny reason naming the target repo. Emitting
     repo A's "pipeline active" text there would point at the wrong worktree —
     the same misleading-remedy failure #421 was filed about.

   Resolution is by real path with a trailing slash, matching the existing
   prefix logic, so `repo` vs `repo-other` cannot collide.

2. **Make the `fr isolation` allowance composable.** The start-anchored match is
   evaluated against the command **with a leading `cd <dir> &&` stripped**, so
   `cd <other-repo> && fr isolation up --branch x` matches. The same stripping
   applies to the `fr init` / `fr skills` / `fr --version` bootstrap allowance,
   which has the identical composition problem. Stripping is *only* of a
   leading `cd`, so `echo x && fr isolation up` remains denied exactly as
   `test_non_leading_cd_denied` requires.

   Ordering matters: change 1 is evaluated first (it is the broader allowance),
   and change 2 is evaluated after, so a `cd` into a *sibling directory of the
   base repo that is not a git repo* still reaches the `fr isolation` check
   rather than falling straight to the deny.

3. **The chained-`cd` shape is blessed in place.** `cd /tmp && cd <other> && …`
   satisfies the allowance on its first segment. That is the documented
   consequence of evaluating only the leading `cd`, already pinned by
   `test_cd_then_back_into_repo_allowed_by_design`. The guard's comment says so
   in as many words, and a named test records it as intentional so it is not
   rediscovered under pressure.

The deny message gains one clause naming the new escape ("working in a
*different* repo? lead with `cd <other-repo> && …`"), because a message that
recommends `fr isolation up` while denying it is the specific trap #421
reports.

**The Hermes sibling is already immune and is not touched.**
`plugins/super-fr/hooks/hermes/fr-isolation-guard.sh` is marker-based rather
than sentinel-based, already evaluates a leading `cd` into an `effective_dir`,
and delegates to `fr_isolation_decide_cwd`, which allows any non-fr repo
outright. #421 is a Claude-Code-only defect.

### E. Tripwire

`tests/unit/test_tripwire_phase_executor_worktree.py`, in the style of
`test_tripwire_claude_p.py`: static assertions over the shipped surfaces so the
convention cannot silently regress —

- `hooks.json` registers `fr-phase-executor-guard.sh` under an `Agent` matcher;
- the hook file exists and is executable;
- `agents/fr-phase-executor.md`'s `description:` carries the constraint;
- `skills/fr-goal/SKILL.md` §6 says "without" alongside `isolation: "worktree"`;
- no shipped skill/agent instructs dispatching this agent *with* the flag.

Behavioural coverage (the hook actually denying / allowing) lives beside the
other hook tests in `tests/unit/test_hooks_guard.py`'s style, as
`tests/unit/test_hooks_phase_executor_guard.py`.

## Non-goals

- **Per-repo sentinels** (a set rather than a scalar `repo_root`). #421 names
  this as the shape a real multi-repo workspace wants and simultaneously notes
  such a workspace is not yet designed.
- **Bringing `agent-worktree-default.md` / `agent-worktree-required.sh` under
  version control.** #420's revised cross-repo item; it is a different repo's
  decision and no such file exists on any machine this run can reach.
- **Making the guard a security boundary.** It is a discipline backstop; §D.3
  is a deliberate reaffirmation of that, not an oversight.
- **Teaching `fr-isolation-required.sh` about agent worktrees.** With the
  poisoned dispatch refused, no agent wakes in a marker-less checkout.

## Test Plan

Post-merge, operator-driven — these verify the *delivery* of hooks to a live
host, which no in-repo test can assert.

1. Re-run `scripts/install.sh` on a host that already has super-fr installed.
   Confirm `~/.claude/plugins/marketplaces/derio-net--super-fr/…/hooks/`
   contains `fr-phase-executor-guard.sh` and that it is executable.
2. In any repo, dispatch `super-fr:fr-phase-executor` **with**
   `isolation: "worktree"`. Confirm the tool call is **denied** and the reason
   names the re-dispatch remedy. (Before this PR the dispatch succeeded.)
3. Dispatch the same agent **without** the flag. Confirm it is allowed and that
   the org hook's allowlist entry still admits it (i.e. the two hooks compose).
4. On a host that has `~/.claude/hooks/agent-worktree-required.sh`, re-run
   `install.sh` and confirm its stderr allowlist message now names
   `super-fr:fr-phase-executor` and no longer contradicts its own `case` arm.
5. From a session with a live fr pipeline in repo A, run
   `cd <repo-B> && fr isolation status` and then
   `cd <repo-B> && fr isolation up --branch test/reachability`. Confirm both are
   allowed. (Before this PR both were denied.)
6. From that same session, confirm `git status` in repo A is **still denied** —
   the guard's discipline in its own repo is unchanged.
7. From the same session run `cd <repo-B> && git commit -am x` against a repo
   B that is **not** isolated. Confirm it is **denied**, and that the reason
   names *repo B* and `fr isolation up` — not repo A's pipeline. Then run
   `cd <repo-B> && fr isolation up --branch test/x`, confirm it is allowed, and
   confirm work in the worktree it creates is allowed: the deny is a
   discipline, not a deadlock.
8. **Sensitive-path check.** On a machine where `$HOME` is a git repo (a
   dotfiles repo — `git -C ~ rev-parse --show-toplevel` succeeds), run
   `cd ~/.ssh && ls` from a session with a live pipeline elsewhere. Confirm it
   is **denied**. Repeat with `$HOME` not a git repo; also denied.
9. **Rider check** (added at review — this is the form that actually changed).
   From the same session run
   `cd ~/.ssh && fr isolation status && cat id_ed25519`. Confirm it is
   **denied**: an allowed `fr …` command must not launder a rider into a path
   that is denied without it. For contrast, `fr isolation status && cat
   ~/.ssh/id_ed25519` (no leading `cd`) **is** allowed — a deliberate, recorded
   boundary, since closing it would reject `fr isolation exec -- 'a && b'`.
10. **Retirement-aim check** (added at review). With a live pipeline in repo A,
    run `fr isolation down --repo <repo-B>`, then `cd $UNSET_VAR && fr isolation
    down`, then a heredoc whose body merely contains the words `fr isolation
    down`. After each, confirm repo A's pipeline is **still live** (the next
    `git status` in repo A is still denied). Then run a plain `fr isolation
    down` and confirm it *does* end the pipeline.

## Implementation Plans

| Plan | Repo | File | Depends on |
|---|---|---|---|
| 2026-07-26-fr-goal-isolation-deadlocks | `derio-net/super-fr` | `2026-07-26-fr-goal-isolation-deadlocks` | — |

## References

- `plugins/super-fr/hooks/fr-isolation-guard.sh` — the #421 subject; `:51-72`
  transition allowance, `:84` `fr isolation` allowance, `:101-107` self-heal.
- `plugins/super-fr/hooks/fr-pipeline-sentinel.sh` — writes no sentinel for a
  linked worktree, the fact that decides Decision 2.
- `scripts/ensure-phase-executor-allowlist.sh` + its test — the prior half of
  #420 and the source of the idempotence-probe lesson.
- `docs/superpowers/implemented/specs/2026-07-22-fr-goal-subagent-execution-design.md`
  §B.1 — why phase subagents run serially in the shared workspace and therefore
  must not get a private worktree.
- `tests/unit/test_hooks_guard.py::TestCdTransitionAllowance` — the behaviour
  §D must extend without regressing.
- `tests/unit/test_tripwire_claude_p.py` — the tripwire style §E follows.
