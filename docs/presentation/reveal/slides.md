<!-- .slide: class="title" data-background-image="../diagrams/factory-line.png" data-background-size="cover" -->

<div class="topblock">

# Delivering more robust code safely using custom skills

## A personal experiment in overengineering the Superpowers skill

</div>

Note: Same chassis, three stations. Left: hand tools and taped-up notes. Middle: one robot, a half-built fence, a clipboard. Right: the full line, conveyor, scanner gate, control booth. This talk walks that floor left to right. What each station added, what failure paid for it, what it costs. Then you get the keys to run station three yourself. No superpowers knowledge assumed. Half 2, later, takes the finished car to the test track.

---

## What is this talk really about

1. **Structure and best practices** over free form discussion
2. **Agentic safety* and autonomy** towards a goal
3. **High feature throughput** in local development

Note: Three claims, increasing ambition. One: structure beats chat. A pipeline with artifacts outperforms free-form discussion every time the work outlives the session. Two: safety and autonomy together, not traded. The asterisk is honest: these are discipline backstops with documented escapes, not a security boundary. Autonomy inside the cage, never outside it. Three: throughput is the scoreboard. A thousand merged PRs in four months is what the first two buy you in local development.

---

## Agenda

- **Three stations:** just the agent and its harness / superpowers / super-fr
- **Twelve upgrades** towards fr-goal
- **Example run** — an annotated test track
- **Quickstart:** installation and your first goal
- **Discussion**

Note: Shapes first, upgrades second. The model gives each upgrade somewhere to hang. Then we get practical.

---

<!-- .slide: class="split" -->

<div class="col">
<div class="crumb"><strong>Stages</strong> &gt; Upgrades &gt; Run it</div>

## Vanilla cycle

```
prompt ──▶ plan in chat ──▶ code in base
──▶ eyeball ──▶ commit + push
```
<!-- .element: class="chain" -->

- Outcome in, approach out: explores, asks on real decisions
- Three modes: interactive, plan-to-approve, autopilot
- Validates what you name, reruns on failure
- **No plan artifact**: conventions restated every single task
- Human owns merge, secrets, production impact
</div>

<img class="side" src="../diagrams/st1-bay.png" alt="">

Note: This is the usual case, and it is already smart. Copilot plus Terra is a strong general teammate: outcome-oriented prompts, repository exploration, multi-file edits, terminal validation, three session modes up to full autopilot. Two honest limits, straight from its own description. One: no plan artifact survives the session, so every task restates conventions, checks, and constraints from scratch. Repetition is the tax. Two: it validates what you name and ships what you approve. Teammate, not owner. The merge, the secrets, the production judgment stay human, and nothing on disk records the journey. This slide is the baseline the next two stations upgrade.

---

<!-- .slide: class="split" -->

<div class="col">
<div class="crumb"><strong>Stages</strong> &gt; Upgrades &gt; Run it</div>

## Superpowers run

```
idea ──▶ brainstorm ──▶ write plan ──▶ worktree
──▶ execute plan + TDD ──▶ verify→review→fix ──▶ finish
```
<!-- .element: class="chain" -->

- Idea in, approved spec out: no code before sign-off
- Spec in, zero-context plan out, then two executor options
- Iron laws inside: failing test first, evidence before any claim
- Review is double-sided, finishing gates on green with 4 options
- **Gaps remain**: one markdown plan, session memory, opt-in fence

</div>


<img class="side" src="../diagrams/st2-cell.png" alt="">

Note: Station two, the serious version of station one. Brainstorming ends in a spec markdown and refuses code until the design is approved, with a reviewer loop on top. Writing-plans turns it into steps a fresh session could execute, then offers subagent-driven or inline execution. Inside: test-driven-development runs red-green-refactor, verification-before-completion forbids completion claims without a fresh full-command run. Reviewing is double-sided, requesting dispatches SHA-scoped reviews, receiving bans performative agreement. Finishing verifies tests first, offers exactly four options, cleans up the worktree. The honest limit, and it is the whole rest of this talk: the plan is one markdown file no tool can read, progress lives in session memory, and the worktree fence is opt-in per task. Everything after this slide is one of those three growing up.

---

<!-- .slide: class="split" -->

<div class="col">
<div class="crumb"><strong>Stages</strong> &gt; Upgrades &gt; Run it</div>

## fr-goal run

```
brainstorm ──▶ spec-review ──▶ plan
──▶ plan-review ──▶ implement+review ×N ──▶ deliver
```
<!-- .element: class="chain" -->

- Shape is data: `kind: cli` runs, `kind: agent` briefs, `gate` stops
- Run file on the branch, failed step holds the cursor
- Workspace first: worktree plus container, then the run

</div>


<img class="side" src="../diagrams/st3-line.png" alt="">

Note: Station three. Same silhouette as station two, new species: the pipeline is a yaml manifest that validates, the cursor is a file on your branch that survives compaction, and isolation is a mandatory cell, not a sidecar fence. Cli steps execute with exit code as verdict. Agent steps print a brief, you work, you resolve. The single operator gate is the batched question round. Everything after this slide is one super-fr addition presented as the upgrade it is: what superpowers lacked, what failure paid for it, what it costs.

---

<div class="crumb"><strong>Stages</strong> &gt; Upgrades &gt; Run it</div>

## Feature velocity

- **1000+ merged PRs** across **15 repos**, May to September 2026
- Roughly two thirds of sampled bodies carry pipeline markers
- Example: `super-fr#449` — Why, spec/plan/journal links, What ships

> Acceptance rows, verification log, journaled deviations, open findings


Note: Feature velocity, honestly labeled. A thousand merged pull requests in four months across fifteen repos of one org, and about two thirds of the bodies I sampled reference the spec, the plan, or the journal. Pull request 449 is the anatomy slide: Why, links to spec plan journal, what ships, acceptance rows all flipped to ci, verification output, deviations from the plan with journal hashes, open findings that are follow-ups not blockers, and an operator rollout phase. Caveat I will not skip: not every one of those thousand ran this pipeline. The claim is that the org ships at this rate with this workflow available, and the bodies show the discipline spreading.

---

<!-- .slide: class="divider" -->

# Upgrades, each justified

What superpowers lacked, the failure that paid, what it costs


Note: The evolutions showed the what. These next slides show the why, one upgrade at a time. Each follows the same shape: what superpowers lacked, the failure that paid for the addition, what it costs you.

---

<!-- .slide: class="split" -->

<div class="col">
<div class="crumb">Stages &gt; <strong>Upgrades</strong> &gt; Run it</div>

## Isolation

- Sidecar fence became a mandatory cell: worktree plus container
- Secrets stay outside, least-privilege profile by default
- Dead brainstorms leave the base checkout pristine

<p class="nav"><a href="#/8/1">detail ↓</a></p>
</div>

<img class="side" src="../diagrams/up-cage.png" alt="">

Note: Upgrade one, the cage. Superpowers had using-git-worktrees as an opt-in sidecar. Here isolation is mandatory: worktree plus devcontainer before anything else, every command through the exec bridge, secrets host-side per profile. A brainstorm that dies leaves the base pristine. That sentence alone is worth the profile-setup interview on first run.

--

## D1 — isolation commands

```
fr isolation up --branch feat/thing --profile dev
fr isolation exec --branch feat/thing -- uv run pytest -q
fr isolation status
fr isolation down --branch feat/thing
```

- Worktree plus container, secrets host-side per profile
- Refuses teardown while the pull request is open

<p class="nav"><a href="#/8/0">↑ back</a></p>

---

<!-- .slide: class="split" -->

<div class="col">
<div class="crumb">Stages &gt; <strong>Upgrades</strong> &gt; Run it</div>

## Pipeline as data

- Shape is an ordered list plus needs and emits per step
- `kind: cli` executes, `kind: agent` briefs, `gate` stops
- `fr workflow check` rejects bad graphs before tokens burn

<p class="nav"><a href="#/9/1">detail ↓</a></p>
</div>


<img class="side" src="../diagrams/up-recipe.png" alt="">

Note: Upgrade two, the recipe. Superpowers' pipeline lived in skill prose. Here it is data: a shape is an ordered list of steps plus what each step needs and emits. Cli steps are deterministic, nobody interprets them. Agent steps never execute inside fr, it prints a brief, you do the work, you resolve. The gate is the one promised stop. Consequence: the engine is a plain program with no path to a language model. Full file: plugins/super-fr/workflows/fr-goal.yaml, six steps plus two grouped children under implement.

--

## D2 — shape fragment, real file

```yaml
workflow: fr-goal
schema: 1
unit: run
requires: [git, tests, scm]
steps:
  - id: brainstorm
    kind: agent
    skill: super-fr:fr-brainstorming
    gate: operator
    emits: [spec, journal:spec]
```

- Source: `plugins/super-fr/workflows/fr-goal.yaml`
- `implement` is a grouped `for_each`, review enforced per phase

<p class="nav"><a href="#/9/0">↑ back</a></p>

---

<!-- .slide: class="split" -->

<div class="col">
<div class="crumb">Stages &gt; <strong>Upgrades</strong> &gt; Run it</div>

## Run cursor

- Run file rides the branch into the pull request
- Failed step holds position, nothing slides past
- A run is born in its workspace, never in the base

<p class="nav"><a href="#/10/1">detail ↓</a></p>
</div>


<img class="side" src="../diagrams/up-conveyor.png" alt="">

Note: Upgrade three, the conveyor. Superpowers kept position in chat and checkboxes. The run file is a cursor on your branch: advance runs cli steps and briefs agent ones, resolve is the only way past running. Start validates the shape before provisioning anything, then writes the run inside the workspace. Failure holds the cursor instead of sliding past it.

--

## D3 — run file, real run

```yaml
run: 2026-09-09-feat-presentation-showdown
workflow: presentation-showdown@1
cursor: record-compare
steps:
  outline: {state: done}
  experiment-design: {state: done}
  design-review: {state: done, exit: 0}
  instrument: {state: done}
  record-compare: {state: pending}
```

- This deck's own run, committed on its branch
- Failed steps hold the cursor, pending steps wait

<p class="nav"><a href="#/10/0">↑ back</a></p>

---

<!-- .slide: class="split" -->

<div class="col">
<div class="crumb">Stages &gt; <strong>Upgrades</strong> &gt; Run it</div>

## One batched Q&A

- Agent studies the code first, then asks once, max four
- Recommended options first, unanswered means stop
- Spec and plan reviews become fix passes, not approvals

<p class="nav"><a href="#/11/1">detail ↓</a></p>
</div>


<img class="side" src="../diagrams/up-cord.png" alt="">

Note: Upgrade four, the cord. Before: decisions arrived one at a time across days, and anything unanswered got guessed. So exploration first, then a single batched round. Four questions max forces the agent to rank what is truly operator-owned. Unanswered is a stop, never a default. After that the agent owes you no more approvals, it owes you fix passes. Post-merge test plan and model-per-tier questions ride the same round when relevant.

--

## D4 — answering the gate

```
fr run resolve 2026-09-09-feat-presentation-showdown \
  --step outline --state done \
  --emitted spec=docs/superpowers/specs/2026-09-09-design.md
```

- Emitted paths must exist and be repo-relative
- Unanswered gates stop the run, never default it

<p class="nav"><a href="#/11/0">↑ back</a></p>

---

<!-- .slide: class="split" -->

<div class="col">
<div class="crumb">Stages &gt; <strong>Upgrades</strong> &gt; Run it</div>

## Acceptance matrix

- One operator-can-X per row, born at brainstorm with defenses
- Rows flip up only on test evidence, failing blocks CI
- Phases link rows, self-review enforces it

<p class="nav"><a href="#/12/1">detail ↓</a> · <a href="#/12/2">spec diff ↓</a></p>
</div>


<img class="side" src="../diagrams/up-gate.png" alt="">

Note: Upgrade five, the gate. Before: suite green, feature not doing the thing. So acceptance rows in docs/acceptance/matrix.yaml, one operator-can-X per row, flipped up only with test evidence. Rows are presented with defenses at brainstorm close. Silent creation is not agreement on scope. The plan links phases to rows and the gate errors on unlinked test-plan specs. Debt stays visible in the pull request, embarrassing by design.

--

## D5 — matrix row anatomy

```yaml
# status: ci | scheduled | skipped | not-implemented | failing
rows:
  - id: session-workspace-binding
    capability: Isolation
    acceptance: bound workspace shown in status line
    origin: [super-fr:docs/superpowers/specs/2026-09-04-design.md]
    status: ci
```

- Schema from `docs/acceptance/matrix.yaml`, rows appended by CLI only

<p class="nav"><a href="#/12/0">↑ back</a></p>

--

## D13 — spec, superpowers vs super-fr

```
superpowers: design doc + commit, reviewer loop x3, user reads file
super-fr adds: Test Plan section (post-merge, operator-driven),
  Implementation Plans table (one row per repo),
  acceptance rows born here with one-line defenses
```

- Same path, same name form — the additions are sections, not files
- Test Plan agreed in the batched Q&A, driven together after merge

<p class="nav"><a href="#/12/0">↑ back</a></p>

---

<!-- .slide: class="split" -->

<div class="col">
<div class="crumb">Stages &gt; <strong>Upgrades</strong> &gt; Run it</div>

## Plan folders, labeled manual work

- Folder per plan: `_meta.yaml`, `_prose.md`, one file per phase
- Step ids `P1.T1.S1`, dependencies explicit
- `fr plan self-review`: cycles, hidden manual work, bad links
- Manual work ships labeled `[manual]`, never smuggled in

<p class="nav"><a href="#/13/1">detail ↓</a> · <a href="#/13/2">plan diff ↓</a></p>
</div>


<img class="side" src="../diagrams/up-bay.png" alt="">

Note: Upgrade six, the build sheet. Before: the single markdown plan, unmergeable, position kept in the model's head. Per-phase files also kill merge conflicts. Self-review runs before any token burns on implementation: dependency cycles, manual work hiding in agentic phases, unknown acceptance ids. Manual phases back-load by default, the pull request ships them unimplemented and you push to the same branch. Front-load only when agentic work genuinely depends.

--

## D6 — phase file, real plan

```yaml
schema_version: 2
phase:
  number: 2
  title: Experiment protocol and instrumentation
  tag: agentic
  depends_on: [1]
tasks:
  - number: 1
    title: Freeze protocol and capture harness
    steps:
      - {id: P2.T1.S1, text: Write seed prompt template}
```

- One file per phase, explicit dependencies, tickable steps

<p class="nav"><a href="#/13/0">↑ back</a></p>

--

## D14 — plan, superpowers vs super-fr

```
superpowers: # Feature Implementation Plan, checkbox steps,
  2-5 minute granularity, reviewer loop, then handoff choice
super-fr: folder (_meta.yaml, _prose.md, NN.yaml per phase),
  P1.T1.S1 ids, tier + acceptance per phase, self-review gate
```

- Checkboxes a session ticks became state a CLI validates
- Manual phases labeled, cross-repo refs in canonical form

<p class="nav"><a href="#/13/0">↑ back</a></p>

---

<!-- .slide: class="split" -->

<div class="col">
<div class="crumb">Stages &gt; <strong>Upgrades</strong> &gt; Run it</div>

## Phase executors, journal handoff

- One executor per phase, briefed from the journal
- Failing test, implement, refactor — the traveler gets stamped
- Tier-matched tools: light joints, light robots

<p class="nav"><a href="#/14/1">detail ↓</a></p>
</div>


<img class="side" src="../diagrams/up-robots.png" alt="">

Note: Upgrade seven, the robots. Superpowers already had subagent-driven execution and the iron TDD loop. What changed is the handoff: pickup plus spec plus journal render, discoveries stamped per phase, acceptance rows flipped only on evidence. Tiers route the model per phase, and the one hard rule is enforced by a hook: the executor never gets its own worktree, because a second worktree cannot see the spec and the run looks healthy while doing nothing.

--

## D7 — journal entry, real run

```
<!-- fr:journal kind=decision scope=spec id=293fbe90d058 -->
### 293fbe90d058 — decision — Outline gate answered

Model: OpenAI Terra default effort both runs.
Demo: details redacted (not accessed; not cleared).
```

- Machine-tagged entries, rendered raw into briefs and bodies

<p class="nav"><a href="#/14/0">↑ back</a></p>

---

<!-- .slide: class="split" -->

<div class="col">
<div class="crumb">Stages &gt; <strong>Upgrades</strong> &gt; Run it</div>

## Review loop, guarded delivery

- Per-phase review, findings fixed with tests or formally refuted
- Draft PR first, ready only when green, never self-merged
- Verify arrival on main before archive and teardown

<p class="nav"><a href="#/15/1">detail ↓</a> · <a href="#/15/2">deviations ↓</a></p>
</div>


<img class="side" src="../diagrams/up-audit.png" alt="">

Note: Upgrade eight, the audit. Two lessons in one slide. Fixes pushed after a premature merge landed on dead branches, so now draft first and the push guard refuses merged-branch pushes. And the healthy-looking run that did nothing: a phase executor in a second worktree cut from main cannot see the spec, so the no-worktree carve-out is enforced by a hook, not by prose. Review findings are fixed with tests or refuted with reasoning, recorded open, fixed, or refuted. The pull request body is rendered from that list.

--

## D8 — acceptance evidence, PR 449

```
Six rows born with the spec, all now ci:
session-workspace-binding, statusline-shows-bound-workspace, ...
fr acceptance check: 99 rows OK.
pytest: 2685 passed, 84 skipped. ruff clean.
```

- Source: `derio-net/super-fr#449`, the annotated example

<p class="nav"><a href="#/15/0">↑ back</a></p>

--

## D9 — deviations, PR 449

```
Deviations from the plan text (all journaled):
- down runs detach_all after teardown, not before (7656ab55c62c)
- Acceptance levels are unit|api|int|ui (62c39ba6fb84)
Open findings (follow-ups, not blockers):
- d028f3cc945a Hermes has no session bind transport yet.
```

- Drift disclosed with hashes, never silently absorbed

<p class="nav"><a href="#/15/0">↑ back</a></p>

---

<!-- .slide: class="split" -->

<div class="col">
<div class="crumb">Stages &gt; <strong>Upgrades</strong> &gt; Run it</div>

## PR bodies from the journal

- Bodies rendered from the journal, not written freehand
- Findings, refutations, manual work, test plan, debt — all aboard
- Comments are explicit mutations, drift rewrites the body

</div>


<img class="side" src="../diagrams/up-paperwork.png" alt="">

Note: Upgrade nine, the paperwork. A vanilla agent writes whatever summary occurs to it. Superpowers fixed the template. Here the body is rendered from durable lists: findings and refutations, manual phases marked unimplemented, the test plan verbatim, acceptance debt with defenses. Tracking issues get the same treatment: bodies re-rendered on drift, comments only as explicit mutations like dispatched-in-error. Nothing narrates itself.

---

<!-- .slide: class="split" -->

<div class="col">
<div class="crumb">Stages &gt; <strong>Upgrades</strong> &gt; Run it</div>

## Git backends, harness ports

- `gh`, `glab`, `tea` behind one backend switch
- Dry-run by default, reachability gate on `origin/HEAD`
- Claude, OpenCode, Hermes drive the same `fr run` surface

<p class="nav"><a href="#/17/1">detail ↓</a></p>
</div>


<img class="side" src="../diagrams/up-docks.png" alt="">

Note: Upgrade ten, the docks. One backend switch instead of a rewrite per forge, dry-run default so every mutation previews first, labels projecting issue state. Harnesses are the sister plants: Claude is the reference with full hook surface, OpenCode ports the edit guard with a documented bash gap, Hermes carries the brief in delegate context. Same CLI everywhere.

--

## D10 — docks in two commands

```
fr apply docs/superpowers/plans/2026-09-09-x          # dry-run preview
fr apply docs/superpowers/plans/2026-09-09-x --to vk --yes
```

- Backend resolves per repo: config key, remote host, default
- Labels: `fr:ready` to `fr:pr-ready`, `manual` never routed

<p class="nav"><a href="#/17/0">↑ back</a></p>

---

<!-- .slide: class="split" -->

<div class="col">
<div class="crumb">Stages &gt; <strong>Upgrades</strong> &gt; Run it</div>

## Multi-repo specs

- Coordinating spec names one plan per repo (`owner/repo:path`)
- This line builds one repo, each other repo gets its own agent
- Cross-repo deps live in the spec and PR order, never in wiring
- Remote phases readable from here, journals stay home

<p class="nav"><a href="#/18/1">detail ↓</a></p>
</div>


<img class="side" src="../diagrams/up-crossplant.png" alt="">

Note: Upgrade eleven, the group order. A feature touching three repos gets one coordinating spec with an Implementation Plans table, and one plan, branch, and pull request per repo. This session owns its repo outright. Each other repo gets a dispatched agent with its own worktree running the same pipeline from planning onward. Dependencies between plants live in the spec and the merge order, never in a phase's local wiring. Read-only reach extends here too: remote phase files resolve for status, while each repo's journal stays in its own building. Dispatch of cross-repo phases is explicitly not yet wired, and the tool says so instead of pretending.

--

## D11 — cross-repo table, real spec

```
| Plan | Repo | File | Depends on |
|---|---|---|---|
| 2026-09-09-presentation-showdown | `derio-net/super-fr` | `2026-09-09-presentation-showdown` | — |
```

- Cross-repo form: `owner/repo:path`, one plan per repo

<p class="nav"><a href="#/18/0">↑ back</a></p>

---

<!-- .slide: class="split" -->

<div class="col">
<div class="crumb">Stages &gt; <strong>Upgrades</strong> &gt; Run it</div>

## Archiving

- Gated mover: only complete phases leave the work queue
- Plans, journals, runs file together under `implemented/`
- Content-matched GC reaps merged workspaces, never open ones

<p class="nav"><a href="#/19/1">detail ↓</a></p>
</div>


<img class="side" src="../diagrams/up-archive.png" alt="">

Note: Upgrade twelve, the vault. At this org's volume the plans folder is a work queue, not history. Archive refuses incomplete work and dirty trees, moves plan plus journal plus run as one unit, sweeps fully-implemented specs. Garbage collection is content-matched: merged workspaces reap, open ones stay, unattended runners never leak. Done means archived.

--

## D12 — the vault, real contents

```
docs/superpowers/implemented/
  audits/ journals/ plans/ specs/
  plans/2026-04-12-vk-cli-p2-dispatch ...
```

- Gated mover only: complete phases, clean tree, one unit

<p class="nav"><a href="#/19/0">↑ back</a></p>

---

<!-- .slide: class="divider" -->

# Run it

From zero to first reviewed pull request


Note: Theory over. This part is a checklist you can follow Monday. Four moves plus pointers.

---

<!-- .slide: class="split" -->

<div class="col">
<div class="crumb">Stages &gt; Upgrades &gt; <strong>Run it</strong></div>

## First goal in four moves

```
curl -fsSL .../bootstrap.sh | bash   # install
fr-init                               # profile interview
/fr-goal <want>                       # answer once, watch
fr acceptance status                  # flip rows on evidence
```

- Standalone when small: `fr-brainstorming`, `fr-debugging`, `fr-plan`
- Custom pipeline: your own `workflows/<name>.yaml`, validated by check
- Scale out: `fr apply --to <runner>` fans merged phases to agents

</div>


<img class="side" src="../diagrams/crib.png" alt="">

Note: Move one installs everything and wires the harness you have. Move two is the only interview in the system and it exists because isolation without a profile is a hard stop, not a degraded mode. Move three is the whole talk in one command. Answer the round, then the shape drives. Move four keeps you honest. Standalone skills cover the small jobs. A custom shape is a yaml file plus check. Dispatch is for merged plans with per-phase pull requests. Repos resolve runners and git hosts the same way everywhere, one CLI surface per harness.

---

<!-- .slide: class="split" -->

<div class="col">
<div class="crumb">Stages &gt; Upgrades &gt; <strong>Run it</strong></div>

## Takeaways

1. **Pipeline is data** — shapes validate, resolve, and re-run
2. **Progress is a file** — cursor on the branch, failure holds still
3. **Work is isolated** — worktree plus container, no fallback
4. **Done means proven** — acceptance rows plus review findings

<p class="closer">Next: the test track — one annotated fr-goal run, narrated live</p>
</div>


<img class="side" src="../diagrams/testtrack.png" alt="">

Note: Four sentences to carry out. If you remember nothing else: data, file, isolation, proof. My position, stated plainly: the ceremony earns its keep. Each row of ceremony exists because the un-ceremonied version failed on a real feature. Half 2 is the test track: one annotated fr-goal run, narrated over the recording. Thank you. Questions, then your first goal whenever you are ready.
