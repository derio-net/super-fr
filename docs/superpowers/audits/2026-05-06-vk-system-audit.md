# VK system audit — 2026-05-06

**Status:** Posterity record. Captures the state of the VK plugin after ~4
weeks of rapid evolution and recurring meta-fix cycles. Used as the
grounding for the single-state-machine rebuild design that follows.

**Trigger:** operator no longer trusts VK's behavior — "letting agents
change the state has introduced a lot of uncertainty." Audit was
requested before any further feature shipping.

## 1. The system, as it stands

`superpowers-for-vk` exists to marry three independent state machines:
the operator's plan files (markdown), GitHub Issues/PRs/labels, and the
VK board. So that an agent can be dispatched to a defined unit of work
and the operator can see consistent state from any context.

Surface area in this repo today:

- ~2,000 LOC across 9 command modules + 7 plan-parsing modules + a
  label registry + a `gh` wrapper + a spec-index reconciler.
- 4 user-facing skills (`vk-plan`, `vk-dispatch`, `vk-execute`,
  `vk-progress`) plus a freshly shipped `vk issue create/convert`.
- ~8,000 LOC of tests across 38 files.
- 8 design specs, 17+ archived plans.
- v1.4.5 today; the version bumped 4× in the last 10 days.

Cross-context players (not in this repo, but load-bearing):

- `willikins/scripts/vk-issue-bridge.py` — cron-driven; parses Issue
  bodies (its own parser, separate from `vk plan`), spawns subagents
  via VK's MCP server.
- VK (vibe-kanban) — separate webapp, 6-status board, exposes 33-tool
  MCP server. Does not auto-transition cards.
- Pod-side Claude Code (frank, agent-images) — runs `vk execute` with
  its own gh auth, its own filesystem, its own clock.
- GitHub itself.

## 2. Honest balance sheet

### What works

| Win | Evidence |
|---|---|
| Phase-structured plan grammar parses when the parser doesn't trip on its own examples | `tests/unit/test_plan_parser.py` — 421 LOC, broad coverage |
| Dispatch is idempotent (skip-if-tracked) | `_get_already_tracked` + tracking-comment injection in `dispatch_cmd.py:77,89` |
| Label registry is centralized and color-coded | `src/vk/labels.py:36-47` — single source of truth, post-`label-lifecycle-fix` |
| Plan-rework convention codified | `vk plan rework` captures the "PR review surfaced new items" pattern without reopening completed plans |
| Cross-repo dispatch works for Issues (label bootstrap per-repo) | `dispatch_cmd.py:579` |
| Test coverage is real — TDD discipline observable | 38 test files, ~8K LOC |
| Spec-index reconciliation now path-based, prose-preserving | Post-`vk-spec-index-hygiene` (PR #82-84, merged 2026-04-29) |

### What doesn't work, and is a recurring source of pain

| Failure | Frequency | Evidence |
|---|---|---|
| Plan parser eats its own examples | 6+ fix commits in 4 weeks | `df68d68 fix(parser): strip fenced regions in _parse_steps` |
| Two paths writing the same spec-index table with different mental models | Until last week — fixed in vk-spec-index-hygiene, but it was a *3-phase plan* to repair | Spec body, `2026-04-29-vk-cli-hygiene-and-issue-authoring-design.md:60-76` |
| Stale-open Issues downstream | Every audit on `derio-net/frank` — most recent 4-of-15 (2026-05-03) | The conversation that started this session |
| Label state drift between Issue lifecycle and actual workflow | Label-lifecycle-fix took 3 sequential plans + 9 sub-phases | `2026-04-27-label-lifecycle-fix-design.md` |
| Install pipeline silently keeps stale cached plugin | Repeated bites; CLAUDE.md documents this explicitly | "PR #21 and #22 both merged without a bump" |
| Dispatch hard-fails on repos lacking pre-existing labels | One-time fix v1.1.1, but spent weeks shipping silently-partial dispatches first | `b1a0eed fix(dispatch): ensure required labels exist` |
| Bridge parser ↔ VK plan parser drift (two parsers, two repos) | Bridge had to learn `superpowers-for-vk:` prefix as a separate fix | `willikins/session-summaries/2026-04-09-vk-bridge-fixes-plan-dispatch.md` |
| PR title/phase metadata is parseable but never enforced | PR titles follow `[<repo>] <slug> · Phase N/M · <subject>` by convention only | No validator anywhere |

## 3. Recurring bug families — root causes

Three patterns explain ~80% of fixes. None is "we had a bug in line X."
They are architectural shapes that *generate* bugs.

### Family A — "Two paths derive the same fact, no canonical reconciler"

| Fact | Path A | Path B | What broke | Fixed how |
|---|---|---|---|---|
| Spec-index row identity | `e.plan` (title) | `e.file` (path) | Title rename → duplicate row | `vk-spec-index-hygiene` — switched to path-based |
| Spec-index row contents | Hardcoded `IndexEntry(repo="", depends_on="—")` | Operator-edited cells | Sync wiped operator data | `vk-spec-index-hygiene` — read-modify-write |
| Issue lifecycle state | GH labels | Actual workflow stage | Labels documented but unwired (`in-progress` was a phantom) | `label-lifecycle-fix` — three plans |
| Issue↔PR linkage (downstream) | `Closes #N` keyword | `vk execute pr-opened` label flip | Stale-open Issues on frank | **Unfixed** — the original brainstorm |
| Plan completion | Plan checkboxes | `**Status:**` header | Drifts unless `vk progress sync` runs | `vk progress sync` |
| Phase→Issue mapping | Plan tracking comment | Issue's `plan:`/`phase:` labels | Drifts if either side edited manually | **No reconciler** |

**Why it keeps happening:** every new state surface is added as a
*parallel* representation of an existing fact, but the new representation
is added *without* a designated reconciler. The reconciler isn't built
until the drift is felt as pain. By then it's a multi-phase fix.

### Family B — "The parser scans free-form markdown that humans + agents author"

The plan parser is the most-fixed component in the repo:

- `e0bdca9` — fence-aware header-divider detection
- `0ac60fa` — fail-loud on misplaced `**Depends on:**`
- `5a5f3d8` — body validator hard-rejects undashed `Blocked by #N`
- `6b1f8fd` — dedent step bodies on parse to preserve fence alignment
- `50d77d2` — preserve step bodies, file-mention verbs, preamble, dot-prefixed
- `df68d68` — strip fenced regions in `_parse_steps` (most embarrassing:
  VK could not correctly read plans that documented the VK plan format)

**Why it keeps happening:** the plan format isn't a grammar with a
parser — it's a markdown convention with a regex-based scraper. Each new
plan style discovers a corner. The parser cannot make a closed-world
claim about what a valid plan is.

### Family C — "Cross-context players each have their own view of the truth"

State lives in 5+ places:

1. Plan file (operator + agent + `vk` CLI may all write)
2. Spec-index table (operator + `vk progress sync`)
3. GH Issue body & labels (operator + `vk dispatch` + `vk execute` + bridge)
4. PR body (operator + agent, with `Closes #N` optional)
5. VK board card status (operator clicks + bridge `poll_pr_status` + manual)
6. Local plan checkboxes vs pod-side plan checkboxes (different
   filesystems, no merge protocol)

Cross-context drift modes observed:

- Bridge parser learned `superpowers-for-vk:` prefix as a *separate*
  code change from the dispatch parser learning it.
- Dispatch silently created Issues without required labels until v1.1.1.
- The PR-status poller in the bridge transitions VK cards based on PR
  state — but if a PR is opened in a *cross-repo* implementation, the
  poller may not connect them.
- Pod-side Claude Code's `vk execute` runs against a different gh auth
  and a different cloned plan file than the operator's local copy.

## 4. The agent-discretion seams

Specific seams where an agent's *judgment* gets imported into the
system's *state*:

| Seam | Agent decision | What gets mutated | Failure mode |
|---|---|---|---|
| **Phase completion** | "I think this step is done" | Plan checkbox `[x]` → triggers `_compute_status` | Premature tick → cascade: status flips to Complete → sync archives plan → spec-index marks done → Issue would close → PR may not even exist |
| **PR body construction** | "Should I include `Closes #N`?" | PR body | Skip `vk execute pr-body` → no auto-close keyword → stale-open Issue |
| **Issue claim** | "Is this mine to pick up?" | `vk-ready` → `in-progress` label | Skip `vk execute claim` → label stays `vk-ready` while work happens → board lies |
| **Plan editing during execution** | "I need to add a step I forgot" | Plan file body | New unticked checkboxes → status reverts to `In Progress` → confusion |
| **Spec-index row authoring** | "What goes in the Repo column?" | Spec table cell | Until last week, sync would silently overwrite |
| **Bridge skill resolution** | "What skill does the Issue body say to invoke?" | VK board status, workspace creation | Body parse error → workspace not created → `PARSE ERROR` on every 2-min tick |
| **Manual phase completion** | "Have I actually done the runbook?" | Checkboxes (no PR exists) | Operator runs commands ad-hoc, forgets to tick → manual phase Issues stay open forever |

Every one is a place where a deterministic function *could* compute the
right answer but the system delegates to an agent's read of the
situation.

## 5. The state-surface inventory

8 axes of state. 4 reconcilers. **4 unreconciled axes that drift.**

### File-side mutations

| Surface | Mutators | Reconciler |
|---|---|---|
| Plan `## Phase N:` headers | operator | — (immutable post-authoring) |
| Plan `**Status:**` header | operator + `vk progress sync` + `vk progress transition` + agent | `_compute_status` from checkboxes |
| Plan `**Depends on:**` lines | operator | parser fails-loud on misplacement |
| Plan `<!-- Tracking: URL -->` | `vk dispatch create` | none — silent if hand-edited |
| Plan checkboxes `- [x]` | operator + `vk execute check-step` + agent direct edit | `_compute_status` |
| Plan archival (git mv) | `vk progress sync` on Complete | none |
| Spec `## Implementation Plans` table | operator + `vk progress sync._reconcile_spec_index` + `vk plan spec-index` | path-based now (post-fix) |

### GitHub-side mutations

| Surface | Mutators | Reconciler |
|---|---|---|
| Issue creation | `vk dispatch create` + `vk issue create` + operator | none |
| Issue body | `vk dispatch create` + `vk dispatch migrate` + `vk issue convert` + operator | none |
| Issue labels (lifecycle) | `vk dispatch create` + `vk execute claim` + `vk execute pr-opened` + operator + bridge | label-state machine in `vk-execute` |
| Issue labels (taxonomy) | `vk dispatch create` + `vk dispatch migrate` + operator | `vk admin labels-sync` |
| Issue close/reopen | operator + `gh pr merge` (only when `Closes #N`) | **none — original brainstorm topic** |
| PR creation | agent + operator | none |
| PR body | agent + operator | none |
| Repo label inventory | `vk dispatch ensure_labels` + `vk admin labels-sync` | `vk admin labels-sync` |

### VK board mutations

| Surface | Mutators | Reconciler |
|---|---|---|
| Card creation | bridge cron tick | dedup by title in bridge |
| Card status | bridge `poll_pr_status` + operator clicks | bridge polls every 2 min |
| Workspace lifecycle | bridge spawns subagent | none — workspace count is the canary |

## 6. Why it has felt worse over time

Three compounding effects:

1. **The reconciler-to-state ratio is decreasing.** Every new feature
   adds a state surface. Reconcilers come later, when drift is noticed.
   The gap between "feature ships" and "reconciler ships" is where the
   operator-attention tax accrues.
2. **The plan parser is asked to do more.** From `## Phase N`/`### Task
   N`/`- [ ] Step N` to also parsing `**Depends on:**`, `**Target
   repo:**`, `<!-- Tracking: URL -->`, fenced-block context, rework
   `Origin` tables, `[manual]`/`[agentic]` tags, dot-prefixed step-body
   verbs. Each addition is a regex; each regex assumes the others.
3. **Cross-context fan-out is increasing.** Originally operator + bridge.
   Now operator + bridge + pod-side execute + bridge-spawned subagent +
   general-purpose subagent + inline-execution session. Coordination is
   by file convention, not message-passing.

## 7. The keep / rebuild / fork question

### Keep as-is
Real value, real tests, v1.4.5 most stable. But continued
operator-attention tax and continued state drift in unreconciled axes.

### Rebuild around a single state machine
Name the canonical state and let everything else derive from it. Plan
file is the source of truth; commit fully. Replace the regex parser
with a strict grammar. Compile state into all derived surfaces from one
rendering function. Drift detected by re-rendering and diffing.

### Fork — replace VK plugin with a thinner tool
~500 LOC. No VK board integration, no MCP server, no bridge. Single
CLI: `dispatch`, `claim`, `complete`. But loses the cross-context
spawn-and-dispatch pattern.

### Recommendation: rebuild around a single state machine

Why:
1. **The bugs are not random.** They share a single shape (Family A).
   A rebuild that addresses *that shape* will retire the drift-prone
   axes by construction.
2. **Plan-file-as-source-of-truth is already true in spirit, false in
   mechanics.** Pick one.
3. **The parser problem is solvable but only by replacing it.** Strict
   grammar (or YAML for structured fields + thin markdown body for
   prose) so the closed-world claim becomes true.
4. **Keep-running migration is achievable.** New plan format ships
   behind a v2 marker; old plans frozen but readable; v1 retired once
   no active plans use it.
5. **A thinner fork is tempting** but loses the genuinely-useful
   cross-context dispatch.

### What "behave more mechanically" means concretely

1. **No agent decides whether state has changed.** State changes are
   observed (file diff, GH event, label diff) and *named* by the
   system, not asserted by the agent.
2. **Every state surface has exactly one writer**, or it has a
   reconciler that runs on every read.
3. **The parser has a closed-world grammar.** Anything that doesn't
   parse fails loud at authoring time.
4. **Cross-context coordination is explicit.** One parser library, one
   renderer library, both contexts import.
5. **Labels are observable, not authoritative.** Issue lifecycle stage
   is a function of `(plan checkbox state, PR state)`. Labels are
   *derived* and refreshed.
6. **Renaming/moving things is cheap.** Path-based identity. Every
   existing rename-bug was a name-based-identity bug.

## 8. Final note for posterity

The audit doesn't say "VK was a mistake." VK solved a real problem
(cross-context dispatch, board visibility, agent pickup). The audit
says: VK accreted state surfaces faster than it accreted reconcilers,
and the parser-as-regex-scraper model cannot scale to its current
footprint. The single-state-machine rebuild design that follows is
the response.
