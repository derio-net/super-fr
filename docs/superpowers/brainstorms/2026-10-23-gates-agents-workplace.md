# Gates, agents and one workplace — brainstorm notes

**Date:** 2026-10-23
**Status:** brainstorm artifact, in progress. Recon and playback only; no
requirements are settled and no spec exists yet.
**Run:** `2026-10-23-feat-gates-agents-architecture` (cursor at `brainstorm`,
waiting on the operator). The operator's brief is recorded verbatim as the
spec-journal entry `brief` (`fr journal render --scope spec --slug
gates-agents-architecture`).
**Resume:** `fr pickup --run 2026-10-23-feat-gates-agents-architecture`, then
continue at [Open questions](#open-questions). The next question is Q1.

## The brief, in short

super-fr has outgrown its first shape. The operator wants:

- **gates** (Architect, Designer, Business Analyst, Developer, DevOps, Tester…)
  manned by agents or humans, fully or semi-autonomous, that take issues and
  route them dynamically;
- a **coordination agent** that moves an issue through the gates:
  brainstorm at the BA gate, plans to the Implementation gate, PRs to the Merge
  gate (DevOps) and then the QA gate (Tester), across sessions and repos;
- **workflows beyond software** (an fr grill-me, an fr deep-practical-book),
  built from the same gates, and eventually a **visual editor** for them;
- a check on whether super-fr's current shape can carry this, or whether it
  needs an architectural decomposition first, with features placed at the
  right level, not all at the skill/harness-plugin level;
- a backlog check first, so nothing duplicates or competes with what exists.

## What the operator said in conversation

These are the operator's answers. Anything marked *guess* below is the
facilitator's, not theirs.

1. **The pain is asynchrony, more than missing features.** Work "gets stuck at
   the end most of the time", but what bothers them most is overseeing many
   issues in different states across too many places: herdr sessions (OpenCode
   and Claude CLI), the Codex and Claude desktop apps, other hosts, Claude
   cloud, GitHub (issues, PRs, CI), this laptop's terminal, privileged
   environments for debugging and deploying, and ticket boards (GitHub
   dashboards, potentially Jira or VibeKanban).
2. **Wanted: one workplace** that is *encompassing, extendable, and makes it
   easy to know where I'm needed, what's unfinished, and how it all fits
   together*.
3. **The first screen is an overview:** what was done yesterday, what is due
   today, what is unfinished. It must be dynamic and configurable.
4. **It is a different product**, possibly resuming or rethinking
   agentic-stoa's cnc-fr, possibly a reimagining. **super-fr will be
   transformed by it** too.
5. **The monolith hurts.** It is hard to iterate, the operator struggles to
   support everything, and a super-fr version update while agents are still
   running older versions is a recurring annoyance.

## Playback so far (facilitator's reading, to be corrected)

- *Guess:* gates are how the workplace knows **where you're needed**. A gate is
  a queue with an owner (an agent, the operator, or both). "Needs you" is the
  set of gates the operator staffs or that escalated to them.
- *Guess:* "stuck at the end" is the post-merge stretch (merge, Tester and
  DevOps gates, close-out). Nothing pulls work forward, so it waits until the
  operator notices it somewhere.
- *Guess:* three layers, each with versioned contracts so that one can upgrade
  while another is mid-run:
  1. **Workplace**: the product. Overview, queues, "needs you", and later the
     editor.
  2. **Coordination**: a long-lived service. Gates, routing, the ledger, and
     adapters to trackers, forges, hosts and harnesses.
  3. **Harness-side discipline**: super-fr, made thinner. Skills, hooks,
     isolation, and in-session verification.

  Much of today's `fr` (the triage driver, batches, the run cursor, dispatch)
  arguably belongs in layer 2, not in a harness plugin.
- *Guess:* revive and re-scope **CNC** as layers 1 and 2. Keep **Paperclip** as
  prior art, and possibly one agent pool behind a port (#1074). Make super-fr
  layer 3, reporting to CNC through versioned contracts.

**Proposed sizing** (the facilitator's call, which the operator may override): this is
several projects. The brainstorm in progress should settle the
**architecture**, meaning the layers, what each owns, the contracts between
them, and the fate of #1074. Then the coordination and gate engine, the
workplace UI and the editor each get their own brainstorm and spec.

## Backlog check (super-fr, 2026-10-23)

84 open issues. Related:

- **#1074, fr-paperclip runner and a delegate port**, is the nearest proposal.
  A Paperclip triage agent picks up issues and runs fr-goal, fr-debugging or
  another shape. Sub-units (specs, plans, phases, reviews) are delegated to
  other agents and harnesses and awaited. It has a queue port, a delegate port
  (`fr run delegate`, `delegates.yaml`, adapters), an agent kit, and frank
  setup. The brainstorm stalled on 2026-10-06 with nothing but a run cursor on
  `feat/batch-paperclip-runner`; its outline lives only in the issue body.
  **Decide whether this work absorbs it, supersedes it, or keeps it as one
  adapter.**
- **The gate vocabulary already exists.** Exit-gates spec R2
  (`implemented/specs/2026-10-14-exit-gates-design.md`) fixes `developer`,
  `reviewer`, `tester`, `devops`, `owner`, `security`. Only `tester` and
  `devops` hold anything. They are PR-routing labels today, not staffed queues.
  A workflow step's `gate: operator` (a "step gate") is a separate concept, a
  naming collision to resolve.
- **#1108**: orchestration churn. A wave driver replaying a long transcript for
  status and HOLD decisions cost about 1.0M uncached input tokens and 22M cached
  reads with no progress. **A coordinator must be deterministic state plus
  cheap, fresh-context decisions, not an always-on LLM session.**
- **#1216**: two independent writers (drive and render) race on one state ref.
  One owner per scope, one write path.
- **#1070**: multi-repo work fits no batch. Undecided between cross-repo batches
  and `after:` links between per-repo batches.
- Also relevant: #597 (fr-goal performance), #795 (Jira and other tracker
  adapters), #611 (forge parity), #1199 (a run blocked on a gate before its PR
  exists cannot reach "Needs you · Developer").
- No prior proposal for a visual editor, non-software flows, or decomposing
  super-fr. The nearest is the 2026-06-05 seam report in this folder, about the
  VK split.

Existing machinery a design can build on: workflow manifests with `needs:`
edges and `cli`/`agent` steps (`fr run`); runners that start real separate
sessions (`fr-herdr`, `fr-claude-cloud`); the wave driver (one long-lived
process per scope); the triage board's `needs_you` view; the plan DAG; the
`fr/tracker` protocol (GitHub only).

## Prior art in sibling repos (local recon, 2026-10-23)

### CNC: agentic-stoa `cnc-fr`, `cnc-frd`, `cnc-fru`

"One server that owns the durable ledger (goals, plans, work items, runs,
budgets, audit) and reconciles it against reality" (`cnc-fr`
`docs/analysis/02-c2-architecture.md` §1).

- `cnc-frd` is the Go and Postgres control plane `cncd`. It has about 65 REST
  paths (`/v1/goals`, `/v1/plans`, `/v1/work-items`, `/v1/queue`,
  `/v1/gates/{id}/{verb}`, `/v1/agents`, `/v1/wakes`, `/v1/runs`, `/v1/events`,
  `/v1/rooms`, `/v1/money`, …) and 39 tables. Every mutation is audited. "Files
  win": git bundle files are canonical, and events signal that something
  changed rather than carrying state.
- `cnc-fru` is the React UI: CnC overview with a **NEEDS-YOU queue** and
  command palette, Board, Queue, Tickets, Sessions with a terminal via runs-fr,
  Agents with roles, Workspaces, Org, Memory, Rooms (ICM stage machines),
  Runners.
- `cnc-fr` is the umbrella repo: compose stack, analysis docs 01–23, specs and
  the acceptance matrix.
- Link to super-fr: `packages/fr-cncd` POSTs plan folders to `/v1/ingest`.
  cncd ports fr's plan-folder v2 schema to Go and tests it against shared
  parity fixtures.
- State: cncd 0.18.0 and cnc-fru 0.7.5 are on frank staging. Prod has never
  deployed (an ArgoCD PreSync ordering problem). Spec d is half merged; spec e
  (the fr-epic loop, to be built in super-fr) and the `SessionAdapter` seam are
  not started.
- **Why it went quiet (2026-07-23), per its doc 23:** tooling debt, chiefly
  *fr version pins blocking fr commands* and a pins robot using up the
  commit-status budget, plus sessions blocked on operator questions and a stale
  roadmap. The version skew named in answer 5 has already stalled one product.

**Already models:** the ledger, a unified needs-you queue (approvals, stage
advances, budget, memory), human and agent work on one board, agents with roles
(security, qa, devops, pm, engineer…), harness-agnostic delivery adapters,
non-software Rooms with stage gates.

**Gaps against the brief:**

- It sees only sessions it dispatched itself, so herdr, the desktop apps, cloud
  and other hosts are invisible.
- It ingests no GitHub issues, PRs or CI.
- It has no Jira or VibeKanban adapter.
- It has no yesterday / today / unfinished digest.
- Its gates are derived from other records, not configurable entities, and not
  routed by role.

**Explicit CNC decisions that contradict the brief, to revisit deliberately:**
"not a workflow builder", state machines defined in files rather than a graph
editor, "files win", single operator on a single laptop, and herdr *ruled out*
as a session backend (2026-09-14; ACP or OpenHands was left open).

### Others

- **Paperclip** (derio-net fork of the open-source `paperclipai/paperclip`,
  essentially upstream): "orchestration for zero-human companies". It has
  agents with roles and an org tree, approvals, heartbeat runs and wakeup
  requests, budgets, a built-in issue tracker, a dashboard, and many harness
  adapters. The overlap is large, but it is shaped around a company and its own
  tracker, not federation across forges and trackers. *Guess:* use it as prior
  art, or one agent pool behind a port, not as the foundation.
- **sessions-fr** (`harness-session-wrapper`, dormant since 2026-07): a
  harness-agnostic ACP (Agent Client Protocol) client UI with a host
  abstraction (`Locus`: local or devcontainer; SSH and cloud deferred). It
  drives one session at a time.
- **runs-fr**: a k8s web-shell gateway that attaches to live run pods
  (`fr.run/*` labels). CNC uses it for its terminal. The STOA checkout is a
  stale clone of the same remote.
- **icm-fr**, **optionality-fr**: the only non-software workflows. One is built
  from stage contracts with human review between stages; the other is
  generate → evaluate → package → validate behind an orchestrator skill. Both
  are file-based, with no runtime or UI.
- **agnostic-fr**: finished. It produces one `AGENTS.md` plus a shim file per
  harness, and models nothing workplace-shaped.

**Gaps no repo fills:**

- discovering sessions that were started outside the system;
- a federated feed of forges and trackers;
- gates staffed by a human or an agent and routed by role across systems;
- one overview across hosts, forges and trackers;
- versioned contracts between decomposed parts. CNC's parity fixtures are the
  one example, and its CLI pin on `fr` is the counterexample that stalled it.

## Open questions

Asked in order, one at a time. Q1 was pending when the session paused.

1. **Of CNC's original choices (one ledger, files win, single operator, not a
   workflow builder, herdr ruled out), which no longer feel right, and why?**
2. What "stuck at the end" looked like the last time: who or what was it
   waiting on?
3. Session discovery: must the workplace *see* sessions it did not start (a
   herdr tab, a desktop-app chat, a cloud session), or only ones it launched?
4. Where does the coordinator's judgement live? A deterministic router with
   LLM calls only at real decisions (#1108), or a resident agent?
5. Which product owns the ledger: CNC (Postgres), git files, or the forge?
   ("files win" against live routing.)
6. Contracts: what is the versioned surface between layers (HTTP API, event
   schema, file schema), and which side may upgrade while the other runs?
7. #1074: absorb, supersede, or keep as one adapter?
8. Non-software flows: is the first non-software flow (grill-me,
   deep-practical-book) part of the architecture's acceptance, or a later
   project?
9. The standing verification question, once a spec exists: how will this be
   verified before it merges?
