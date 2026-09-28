# Journal: 2026-09-28-requirements-traceability

<!-- fr:journal kind=discovery scope=spec id=input-issue-759 created=2026-09-28T06:22:57+00:00 -->
### input-issue-759 · discovery · Raw input: issue #759 title and body (verbatim)

fr-goal is a lossy relay: the brief is paraphrased into the spec, executors and reviewers never see it, and nothing checks the spec against it

## Problem

fr-goal loses the operator's requirements on the way from the brief to the code, and no stage checks the result against the brief. The pipeline works as a relay: every step works from the previous step's paraphrase.

- **brief → spec:** the orchestrator paraphrases the brief into a spec, adding its own design decisions and dropping constraints.
- **spec review:** `fr-spec-reviewer` checks the spec "against the operator's recorded decisions, against the codebase it names, and against itself" (its agent description). Not against the brief. An invented behaviour or a dropped acceptance criterion passes.
- **spec → plan:** the plan compresses the work further into steps.
- **plan → executor:** the phase executor is dispatched with the spec and plan only. It never sees the brief.
- **review-phase:** checks the code against spec + plan, so it confirms conformance to the paraphrase.
- **deliver:** gates evidence of what was *planned*: tests, reviews, acceptance rows the run wrote itself.

So fr is rigorous about "did we do what we planned", and nothing checks "did we plan what was asked". Detail an operator writes into a brief can only survive if the orchestrator happens to carry it into the spec.

## Evidence (one run; generic brief/spec lines quoted)

A feature brief with an explicit UI acceptance-criteria list, run end to end with `/fr-goal` (fr 4.28.0, OpenCode, single phase).

- **The brief:**
  > Quantities: − / + on each article card (1–20), styled like the cards; the card shows its quantity. … Every new control uses the page's colours, font and radius — no unstyled browser defaults.
- **The spec the orchestrator wrote** (`docs/superpowers/specs/…-design.md`, UI section):
  > In basket mode **cards toggle membership**, with styled minus/plus controls **(1–20)** and displayed quantity …
  - "cards toggle membership" is **invented**. The brief says nothing about card clicks.
  - "(1–20)" became a lower bound on the − control, so a quantity can't reach 0.
  - "page font / no unstyled browser defaults" is **dropped**.
- **The plan** (`01.yaml`): the whole UI is one step, "implement styled mode buttons, card quantities and number input".
- **The executor's dispatch** (task input, 1,457 characters): "read spec … and fr journal handoff … Implement basket logic, API, UI; browser-check accepted, rejected, staff check and back to article …". The brief is neither included nor referenced.
- **Transcript check:** zero parts in the executor's and the reviewer's sessions contain any of the brief's UI acceptance wording.
- **Result:** the delivered UI implements the spec faithfully, including the invented and dropped items:
  - the card click toggles the article and resets its quantity;
  - − stops at 1;
  - − / + are hidden until the card is clicked;
  - the new controls fall back to the browser's default font.

  The executor's browser check photographed the four states the *spec* listed, so it couldn't catch these.
- **Control:** a plain single-context agent given the same brief met every one of those criteria. The agent that wrote the code had read the brief. Same model.
- **Across repeated runs of the same brief,** fr's divergences cluster at the brief → spec step. It reinterprets limits, adds interaction designs, and loses constraints, while its implementation and gates are sound.

## Proposed

1. **Carry the source brief verbatim through the run.** Store it as a run artifact at `start` (the goal text the operator gave, or the issue body). Pass it in every executor and reviewer dispatch as **the source of truth**, with the spec as the design built on it.
2. **Make spec review a traceability check.** `fr-spec-reviewer` gets the brief. Every acceptance criterion / business rule in the brief must map to a spec section. Findings for **invented behaviour** (spec says X, brief doesn't) and **dropped constraints** (brief says X, spec doesn't) are in scope by default.
3. **Seed the acceptance matrix from the brief's criteria, word for word.** Seed rows from the brief's own criteria at brainstorm, so `deliver` can't pass while one is unmet or unevidenced. The rows shouldn't be only the run's own restatements.
4. **Quote acceptance criteria verbatim in the spec** (an "Acceptance criteria (from the brief)" block). Paraphrase only in the design sections.
5. **Review phases against the brief's criteria too:** review-phase's brief includes the criteria the phase claims to satisfy.

## Related

- #690: operator-gate provenance.
- #745: phase sizing. Fewer, larger phases make the plan an even lossier summary without (1).

<!-- fr:journal kind=discovery scope=spec id=input-issue-759-comment created=2026-09-28T06:22:57+00:00 -->
### input-issue-759-comment · discovery · Raw input: issue #759 follow-up comment (verbatim)

Two follow-ups to the issue text.

**1. A correction: phase count isn't the cause.** The "Related" line above says fewer, larger phases make the plan lossier. That claims more than the evidence shows.

- **Nothing in fr limits a plan's size:** no cap on phases or steps, and no truncation of the executor's handoff. The only truncation is `render.py`'s 55k budget for GitHub Issue bodies.
- **What happened was the planner's choice:** told "single phase", it compressed. The whole UI became one step ("implement styled mode buttons, card quantities and number input"; the plan had 3 tasks, 9 steps, 98 lines), and the detail lived only in the spec.
- **fr-plan's own guidance pulls both ways:** "Prefer 4–6 phases … cost grows superlinearly with phase count" sits next to "one agentic phase is first-class" and "bite-sized steps: 2–5 minutes". "Prefer 4–6" also contradicts #745's measurements (one-phase plans cheaper). Worth reconciling there.

**2. A reframing: the spec IS the requirements carrier.** In general the input isn't a carefully written brief. It can be a user's one-line request. So "carry the brief verbatim" (proposal 1) can't be the main fix. The spec has to capture the requirements, and the defect this run shows is that nothing checks the capture:

- **Invented requirements pass silently.** The spec introduced user-visible behaviour nobody asked for ("cards toggle membership") and reinterpreted a stated range (1–20 as a lower bound on −). Those are design decisions dressed as requirements.
- **Dropped requirements pass silently.** A stated constraint ("no unstyled browser defaults") vanished between input and spec.
- **Spec review can't see either.** It checks the spec against itself, the codebase, and the recorded answers, but not against what the operator actually said.

Directions that work whatever the input's quality:

- **Split the spec into Requirements and Design.** *Requirements, as captured* holds each item traced to its source: the goal text or issue, or an answered question. *Design* holds fr's own decisions. Any user-visible behaviour in Design that no requirement asks for gets surfaced as a question in the (single) question round, or flagged as an assumption in the PR, never silently promoted.
- **Spec review traces Requirements back to the raw input,** however short. Its findings: each input statement is covered or explicitly deferred; every requirement has a source. This is the one place the original wording is needed. It stays a review input, not something dispatched downstream.
- **Seed acceptance rows from Requirements,** so `deliver` gates on the captured requirements rather than the plan's restatement of them.

With that in place, executors and reviewers working from the spec is fine, because the spec is checked to be a faithful capture.

<!-- fr:journal kind=decision scope=spec id=d0-spec-is-the-carrier created=2026-09-28T06:22:57+00:00 -->
### d0-spec-is-the-carrier · decision · The raw input is not carried downstream; improve spec creation and review instead

Operator: the input has no quality control (one line to spec-shaped), brainstorming may depart from it for good reason, and carrying it to executors/reviewers would confuse them. Proposals 1 and 5 of #759 are dropped; the spec is the requirements carrier, checked once against the input.

<!-- fr:journal kind=decision scope=spec id=d1-input-in-spec-journal created=2026-09-28T06:22:57+00:00 -->
### d1-input-in-spec-journal · decision · Raw input preserved verbatim as a spec-journal entry

Chosen over a verbatim spec section (every executor would read it) and a sibling run file (no run id for standalone brainstorms). The reviewer already reads the spec journal; executors never get it.

<!-- fr:journal kind=decision scope=spec id=d2-always-ask created=2026-09-28T06:22:57+00:00 -->
### d2-always-ask · decision · Unasked user-visible behaviour is always a round question

Chosen over 'ask or list as assumption' and 'always assumption'. Also covers every ambiguous input statement. No assumption list at brainstorm time.

<!-- fr:journal kind=decision scope=spec id=d3-late-unconfirmed created=2026-09-28T06:22:57+00:00 -->
### d3-late-unconfirmed · decision · Late spec-review findings of invented behaviour are kept and flagged in the PR

Chosen over reopening the gate and over stripping to a minimal reading. Resolved 'unconfirmed', rendered under 'Built without operator confirmation'.

<!-- fr:journal kind=decision scope=spec id=d4-structural-gate created=2026-09-28T06:22:57+00:00 -->
### d4-structural-gate · decision · Structural gate plus reviewer judgement

fr machine-checks Requirements form, sources, quotes and row citations as derived evidence; coverage stays with fr-spec-reviewer.

<!-- fr:journal kind=decision scope=spec id=d5-rows-gate-deliver created=2026-09-28T06:22:57+00:00 -->
### d5-rows-gate-deliver · decision · Every requirement cited by a row; deliver refuses not-implemented rows

Chosen over report-only and rows-by-judgement. skipped passes.

<!-- fr:journal kind=decision scope=spec id=d6-approach-a created=2026-09-28T06:22:57+00:00 -->
### d6-approach-a · decision · Requirements as a spec section with a fixed grammar, parsed by fr/requirements.py

Chosen over a YAML sidecar (new artifact kind) and front matter.

<!-- fr:journal kind=decision scope=spec id=d7-requirements-table created=2026-09-28T06:22:57+00:00 -->
### d7-requirements-table · decision · Requirements and Deferred from input are Markdown tables

Operator at spec review: the Requirements section should be a table, like Decisions. Sources in one cell, separated by <br>; a literal | is escaped as \|.

<!-- fr:journal kind=discovery scope=spec id=gate-opened-after-answers created=2026-09-28T06:22:57+00:00 -->
### gate-opened-after-answers · discovery · Design answers d0-d7 predate the brainstorm gate opening

Standalone fr-brainstorming: the cursor was started at section 0 but `fr run advance` (which opens the operator gate) ran only after the operator had answered the five design questions and reviewed the spec. The gate is cleared by the operator's answer to the gate-clearing question itself; d0-d7 were decided interactively before it. Skill gap filed separately.
