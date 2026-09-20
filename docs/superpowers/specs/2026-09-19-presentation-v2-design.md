# 2026-09-19 presentation v2 — one run, four angles, one next action

Supersedes `2026-09-09-presentation-showdown-design.md`, whose deck is parked
and post-mortemed at `docs/presentation/version-1/README.md`. v1 failed for a
reason no slide edit could fix: no clear goal, no defined audience. This spec
fixes both before anything else is decided.

## Goal

A 45–60 minute internal talk. The listener is **one person, named precisely**:
a developer who already uses an agentic coding harness daily (Claude Code,
OpenCode, Copilot) and has never seen super-fr. She knows what an agent is. She
has felt a long session lose the thread.

She leaves with two things:

1. **Why this is useful for her** — not what super-fr contains.
2. **The ability to run `/fr-goal` on a real issue of her own**, tomorrow.

**Success is behavioural, not rhetorical:** she runs `/fr-goal` on one real
issue within a day. Anything in the deck that does not serve that is cut.

## The correction to v1

v1 grew outward from the subject — fourteen upgrades in the order they were
built. v2 grows inward from the goal. The structural device that makes this
possible:

**One real recorded `/fr-goal` run is the spine. The four angles are
annotations on it, not sections beside it.**

That converts a catalogue into a narrative, and makes "you can do this
tomorrow" literal — she watched the whole thing happen once.

## Decisions (outline gate, 2026-09-19)

| Decision | Value |
|---|---|
| Audience | One primary, no secondary: daily agentic-coding user, new to super-fr |
| Walk-out action | Run `/fr-goal` on one real issue, devcontainer on-ramp via `fr-init` |
| Length | 45–60 min |
| Renderer | HyperFrames `/slideshow` — navigable deck, presenter mode. reveal.js retired with v1 |
| Narrative shape | Recorded run is the spine; angles annotate it |
| Angles | Security, Quality, **Continuity**, + Extensibility as closing coda |
| Recording | Internal **Java training** project (identity redacted); **rendered deck is private**; source is generic and in-repo; **no binaries committed, ever** |
| Harness | `opencode --auto`, `github-copilot/gpt-5.6-terra`, default effort — same as bc88 |
| Playback | asciinema-player embedded, 1.5–2×, paused at each annotation moment |
| Evidence | The measured bc88 comparison, as a 2–3 min beat *after* the run |
| superpowers contrast | Secondary. Attached to specific moments only; never its own section |

### Why "Continuity" and not "Documentation and Structure"

The items are the run cursor, plans-as-folders, the journal, and archiving.
What binds them is not that they are documents — it is that **they outlive the
session**. Named for the pain this audience has actually felt: the long run that
lost its place. The cursor knows where you were, the journal knows what is still
open, the archive knows what already shipped.

"Structure" describes the artifacts' shape; "Continuity" names what they buy
her. "Traceability" is the manager's word, and we did not pick the manager.
"Memory" collides with context windows and RAG, which is the wrong idea.

## The spine, and where each angle attaches

A `/fr-goal` run already visits the angles in order. This is the talk's outline.

| Moment in the run | Angle | superpowers contrast |
|---|---|---|
| **`fr-init` scans the repo and interviews** | *the contract (1 of 2)* | — |
| **profile scaffolded, `backend: gitlab` declared** | Security · Extensibility | — |
| `fr isolation up` → worktree + devcontainer | Security | base repo never touched, vs. "please work in a worktree" |
| Batched Q&A — asked once, then left alone | *the contract (2 of 2)* | — |
| Spec written, dated, committed | Continuity | — |
| Acceptance rows born and defended | Quality | — |
| Plan as a **folder** with `_meta.yaml` | Continuity | formless plan; checkboxes left unticked |
| Run cursor advances | Continuity | nothing survives the session |
| Phase executor dispatched as a subagent; tier→model | Extensibility | — |
| TDD per phase; adversarial review loop | Quality | — |
| Journal findings; `check` fails on open ones | Quality | — |
| Merge → archive to `implemented/` | Continuity | specs and plans pile up undifferentiated |
| `fr isolation down` | Security | — |

The angles are deliberately **not** peers. Security bookends, Quality and
Continuity interleave densely, Extensibility surfaces once. That ranking is also
the relevance ranking for someone whose next action is one issue tomorrow.

## The recording starts from a pristine repo

**Decided 2026-09-19.** `fr-init` is *inside* the recording, not setup done
beforehand. The run is end-to-end from a repo with no `.devcontainer`, because
that is the state the listener's own repo is in. A demo that begins after setup
teaches the half she has already got.

Three consequences.

**The arc is now complete**: pristine repo → `fr-init` → isolation →
`/fr-goal` → merge request. Nothing is assumed into existence off-screen.

**The contract beat happens twice, and that is the honest message.** `fr-init`
interviews, then `/fr-goal` batches its own questions. "You are asked once" was
never quite true; "you are asked once to set the repo up — ever — and once per
feature after that" is true, and still small enough to be the selling point.

**`backend: gitlab` is now made on camera.** `fr init scaffold --backend gitlab`
both installs a versioned `glab` in the container and records the key
`detect_backend` reads. That is precisely the key whose absence made fr silently
assume GitHub, so the moment the interview asks it is the moment the GitLab
story becomes visible rather than asserted.

### The waits are real, and get shown as waits

A devcontainer build (base image, Java 17 + Maven, a `glab` install) and a first
Maven dependency resolution are minutes, not seconds. Two temptations to refuse:

- **Do not pre-build the image and cut to a warm container.** That hides the
  single biggest cost of adoption and the demo becomes a lie she discovers on
  her own machine an hour later.
- **Do not play them in full either.** Nobody learns from watching a progress
  bar at 1.5×.

Resolution: **compress hard and label the compression on screen** — the same
posture the privacy rule takes on redaction, that stating it beats hiding it.
Pre-pulling *base image layers* is legitimate and needs no label; we are not
demonstrating a registry's bandwidth. Everything fr itself does is shown.

## What this harness costs the recording

`fr harness parity` on 2026-09-19, read before recording rather than after.
Two rows change the plan.

### ~~`subagent-dispatch / opencode: absent`~~ — **resolved, verified 2026-09-20**

Shipped in [#494](https://github.com/derio-net/super-fr/issues/494)/PR #495 and
re-verified here against the installed binary, not the PR narrative:

- All four shipped agents are installed and visible to `opencode agent list`:
  `fr-phase-executor` plus `-hard`, `-mechanical`, `-standard`.
- A task-tool dispatch to `fr-phase-executor-hard` produced a **genuine child
  session** — parented, `agent = fr-phase-executor-hard`, its own cost ($0.0253)
  and tokens (10098 in / 8 out). Real context isolation, not role-play.
- `fr harness parity --check` agrees; the row is now `enforced` on all three
  harnesses. `sync-opencode.py --check` is clean and the new tripwires pass.

The prose that would have silently defeated it was fixed too. SKILL.md:92 now
reads: *"OpenCode dispatches the same brief, serially, through its task tool as
`subagent_type: fr-phase-executor-<tier>` … the call carries no model, so the
agent NAME is the only place a tier can live."* That constraint is why there are
tier variants rather than one agent with a model argument.

**So the Extensibility beat returns to the spine, and it is now the strongest
one available** — a phase handed to a separate agent with its own context
window, visible in the transcript, on a harness where this did not exist a day
ago.

### But the tiering is currently nominal — fix before recording

`install.sh` resolves each tier's model from `fr models` and injects it into the
installed agent. On this machine all three tiers resolve to the **same** model:

```
opencode:
  hard: github-copilot/gpt-5.6-terra
  mechanical: github-copilot/gpt-5.6-terra
  standard: github-copilot/gpt-5.6-terra
```

So the three agents differ by name only. Filming that would show three labels
bound to one model and prove nothing — the opposite of the point.

Differentiate the bindings and re-run `install.sh` before recording. Available
today include `github-copilot/claude-haiku-4.5` and `gemini-3.8-flash` for
mechanical work, against `gpt-5.6-terra` or `claude-opus-5` for hard.

This may also **defuse the cost objection**. The $7.59 figure was 13 subagents
all on one model; putting mechanical phases on a cheap one is exactly what
tiering is for. Unmeasured, so treat it as a reason to measure, not a claim.

### `operator-gate / opencode: advisory` — the contract beat can silently not fire

> no operator-question tool exists on OpenCode — the gate cannot mechanically
> block; the measured failure of #436 instance 2.

**This is the single highest-risk moment in the recording.** "Asked once, then
left alone" is the heart of the pitch, and on this harness nothing enforces it:
the skill prose asks the model to batch its questions and end the turn, and a
model that ignores it simply proceeds. That is not hypothetical — v1's arm A is
the measured case where it never asked anything at all.

Both question gates are affected: `fr-init`'s interview and `/fr-goal`'s batch.

Mitigated by this being a recording, not a live demo — a bad take is re-recorded.
But that only works if the take is *checked*, which is why the criterion below
is a gate and not a hope.

## Recording acceptance — when a take is usable

Checked before anything is torn down, because the evidence is perishable.

1. **Both question gates fired.** `fr-init` interviewed, and `/fr-goal` asked its
   batch and ended the turn. If either did not, the take is discarded.
2. **The cursor records a human answered** — `answered_by: operator`, not the
   agent clearing its own gate.
3. **A check genuinely failed and was recovered.** This is why those two
   exercises were chosen; a clean run is a weaker take, not a luckier one.
4. **At least one phase was dispatched to a subagent** — a `session` row with
   `parent_id` set and `agent = fr-phase-executor*`. This is also #494's own
   acceptance, and the Extensibility beat exists on camera only if it holds.
5. **The merge request exists** on the operator's fork.
6. **Annotation offsets were noted live**, not reconstructed afterwards.

## Time budget (51–59 min)

| # | Beat | Min |
|---|---|---|
| 1 | Hook — why your sessions go sideways | 3 |
| 2 | What a skill is, and how it gets used | 5 |
| 3 | **The run, annotated** — from pristine repo through `fr-init` to the MR | 30–34 |
| 4 | Was the ceremony worth it? — measured | 3 |
| 5 | Extensibility coda — shipped items only | 2 |
| 6 | **Hands-on: she runs it on her own repo** | 8–12 |
| 7 | Discussion | — |

Beat 3 is the talk. Beats 1–2 buy the right to it; 4–6 convert it.

Beat 6 changed character when `fr-init` moved into the recording. It is no
longer a demonstration — she has just watched one — so it becomes the room
doing it: `fr-init` on their own repos, with help on hand. The walk-out action
is "run `/fr-goal` on one real issue", and this is the only beat that actually
starts it.

## Feature selection — a runtime constraint, not just a credibility one

Measured from v1's own experiments (`version-1/experiment/run-metrics.csv`):

- **Bounded issue (blog-craft #88), OpenCode:** 17.0 min, $1.19, 4 questions,
  emitting spec + 4-phase plan + 2 journals + run cursor.
- **Unbounded issue (super-fr #429):** 56.2 min on Claude with 14 subagents;
  105.2 min on arm C.

At 1.5–2× a 17-minute cast is 9–11 minutes of screen time, which fits beat 3
with room to stop and annotate. **A #429-shaped feature does not fit and would
force excerpting**, which forfeits the "you watched the whole thing" proof that
makes the walk-out action credible.

Selection criteria for the recorded feature:

1. Bounded to a **15–25 minute** run.
2. Touches **more than one surface** — ideally code + tests + a gate — so the
   Quality angle has something real to point at.
3. Has at least one **genuine failure and recovery** (a check that fails, a
   review finding that gets fixed). A clean run proves less than a corrected one.
4. Its **contents are briefable at the level of shape**, not code.

## The recorded feature

An **internal Java training project** — course material, not product code.
Java 17 + Maven; default branch `master`. Its identity (host, group, project,
namespace) is third-party and stays out of this repo per
`.claude/rules/third-party-privacy.md`; the operator holds it in an untracked
local env file beside the recording assets. `docs/presentation/version-2/runbook.md`
carries the shape and reads every identity from that file.

**Why the subject is safe to record at all.** It is a teaching exercise with a
generic technical core, not proprietary product logic. What must not appear is
the instance, the namespace and the project — none of which the talk needs.

Its README defines four exercises. Recommended issue composition:

| Exercise | Use | Why |
|---|---|---|
| Fix three deliberately-failing tests | **Include** | Supplies the failure-and-recovery beat. A corrected run proves more than a clean one. |
| Write unit tests for a class that has none | **Include** | Gives the Quality angle real material; edge cases are natural TDD material. |
| Refactor an awkward class | **Optional** | Adds a third surface. Include only if sizing allows. |
| Explain a complex class | **Exclude** | Conversational; produces no deliverable and therefore no PR. |

The first two satisfy all four selection criteria: bounded, multi-surface, with
a built-in failure to recover from, and describable without naming anything.

**Invoked as `/fr-goal <text>`, with no tracker issue** (operator decision,
2026-09-19). The brief is composed from those two exercises and passed inline.
That removes a setup step and a dependency, and it matches what the listener
will actually type — she has a task in her head, not a ticket.

It also narrows, precisely, which GitLab surface the recording exercises. A
`/fr-goal` run produces a spec, a plan and a **merge request**; it does not
create or label tracker issues, because that is the *dispatch* path
(`fr apply --to <runner>`), which is a different feature. So:

- The recording proves the **MR** half of GitLab, live, on the audience's own
  forge.
- The **issue rendering / labelling / diffing** half is already proven — it was
  PR #487's own live walk, and is what moved `multibackend-gitlab-tracking` to
  `skipped` with a live-verified note. It does not need redoing here.

Stated because the two are easy to conflate: an earlier note in this session
claimed the demo run *was* the outstanding `fr apply` exercise. It is not.

The brief's text names classes and files in a third-party repo, so like every
other identity it lives in the operator-local file outside this repo, not here.

**UNBLOCKED 2026-09-19** — [#486](https://github.com/derio-net/super-fr/issues/486)
is fixed (PR #487) and independently re-verified live. With `backend: gitlab`
declared and no `GITLAB_HOST` exported, `detect_backend` resolves `gitlab`,
`file_exists` is `True` for files that exist and `False` only for ones that do
not, `list_dir` and `read_file` both work, and `file_exists` against an
unreachable host now **raises** instead of reporting absence.

**Preconditions before recording** — note how few remain, now that `fr-init`
and the backend declaration happen on camera:

1. **Remote repointed** ✅ (2026-09-19). `origin` is the operator's own fork;
   the team's project is kept as `upstream` with its push URL `DISABLED`,
   verified by dry-run. A `/fr-goal` run opens merge requests unattended, so an
   unreachable push path on another team's repo is a safety property, not
   tidiness. The MR lands in the operator's own namespace.
2. **The repo must be PRISTINE** ✅ (2026-09-19). No `.devcontainer`, clean
   working tree. This is now a precondition rather than a setup step — it is
   the state the recording has to start from. A `fr-profiles.yaml` written by
   hand during verification earlier in this session has been removed for
   exactly that reason.
3. **Pre-pull the devcontainer base image layers.** Legitimate and unlabelled:
   the talk is not demonstrating a registry's bandwidth. Everything `fr` itself
   does stays on screen, including the build it drives.
4. **Prepare the brief text** in the operator-local file, composed from the two
   chosen exercises.
5. **Capture apparatus** per `docs/presentation/version-2/runbook.md`.

Deliberately *not* on this list any more: scaffolding the profile, declaring
`backend: gitlab`, and creating a tracker issue. The first two are now the
recording's opening beats; the third no longer exists.

## Confidentiality contract

**Superseded from v1, deliberately.** v1 recorded that the driving session was
not cleared for the operator's board and must never read the ticket. That
constraint no longer binds: the chosen subject is **course material, not a
product ticket**, and the operator has explicitly permitted reusing parts of its
README to construct the `/fr-goal` prompt. Recorded here rather than silently
dropped, because a constraint that quietly disappears is indistinguishable from
one that was forgotten.

What still binds, and why:

- **Repo hygiene** — the GitLab host, group, project and username are never
  named in super-fr. This is now a standing repo rule, not a judgement call:
  `.claude/rules/third-party-privacy.md` (2026-09-19).
- **Content exposure** — much reduced, but not nil. The exercise's technical
  core is generic, but a terminal recording shows the instance, namespace and
  project in prompts, git output and MR URLs. Resolved by scope: **the rendered
  deck is private and given internally only.** `sed` over a cast would not have
  been a reliable alternative anyway — a name can split across write boundaries
  amid escape sequences.

This yields a clean split worth stating plainly:

> **The deck's source is public and generic. The rendered deck is private.**

**No binaries in this repo — ever.** Casts, rendered video and stills live
*outside* the repo, not merely gitignored. Privacy is the lesser reason; the
load-bearing one is that **super-fr is itself a Skill, cloned onto every
consumer's machine** by the marketplace rsync. A committed binary inflates every
install forever and cannot be removed from history without a rewrite. Assets are
reached through a manifest of paths plus checksums.

> **Pre-existing violation, flagged:** `docs/presentation/version-1/diagrams/`
> already holds 17 committed PNGs. They predate this rule and are inherited
> weight in every clone. v2 must not add to it; removing them is a separate
> decision, since reclaiming the bytes needs a history rewrite.

Source in `docs/presentation/version-2/` is committable because it contains
prose, structure and annotation timings — no assets. The build resolves assets
from the manifest and **fails loudly when one is missing**, so a checkout that
lacks the private assets cannot silently render an incomplete deck.

## Honesty constraints on the Extensibility coda

Corrected 2026-09-19 after the operator challenged an earlier, wrong
restriction. Two pairs of claims that look alike and are not.

**Claimable — verified shipped and operator-reachable:**

- **Multi-repo plans from a single spec.** `fr.spec`'s rollup explicitly
  handles *"the normal multi-repo shape"*: a plan folder that doesn't resolve
  locally is read through the contents API and given identical phase/step
  arithmetic, counting toward `plans_complete`, degrading to `Unreachable`
  rather than passing silently.
- **Custom shapes.** `fr.workflow.resolve` resolves
  `docs/superpowers/workflows/<name>.yaml` **wholesale** over shipped. v1
  authored and ran `presentation-showdown` through exactly that path, so the
  talk can demonstrate it from its own history.
- Phase executors and model tiers per workload complexity — **shown, not
  told**, as of #494. See the verification note below.
- The three harnesses.
- **GitLab**, including self-hosted — see below.

**Not claimable — different features that merely sound the same:**

- `multi-repo-spec-fanout` — automatic per-repo work-item **dispatch**.
  `not-implemented`, "fake-runner-only and operator-unobservable." A spec
  *driving* plans across repos works; a spec *fanning out* dispatch does not.
- `dispatch-unit-declared-by-shape` — selecting run- or spec-**granularity**
  for dispatch. `not-implemented`; only `unit:phase` is reachable. Authoring
  and running a shape works; choosing its dispatch granularity does not.

**GitLab — now claimable, live-verified 2026-09-19.** It did not pass when this
spec was written, and the story is worth the coda's time on its own. The adapter
had never met a real instance. One check found the contents endpoint omitting
GitLab's mandatory `ref`; the fix's own live walk then found three more, the
worst being that GitLab returns `web_url` as `/-/work_items/N`, which `fr` stored
and then could not parse — crashing `observe` on every re-apply, **on gitlab.com
identically**. So `fr apply` against any GitLab repo worked exactly once.

`multibackend-gitlab-tracking` had been `status: ci` — green — throughout, for a
capability broken four independent ways, because every unit mock discarded the
request. It now sits at `skipped` with a live-verified note, which is the honest
level: live verification cannot run in CI.

Gitea stays unproven and unclaimed by agreement.

## Non-goals

- Not a tour of all fourteen upgrades. That was v1, and it is why v1 failed.
- Not ending on an open question. v1 closed on "is the ceremony worth it?" and
  handed the listener evidence with no conclusion. v2 ends on an action.
- Not externally publishable. The rendered artefact is internal by construction.
- Not a superpowers takedown. The contrast is secondary and lands only where a
  concrete moment in the run earns it.

## Reused from v1

- `version-1/experiment/bc88/comparison.md` + `run-metrics.csv` — beat 4, as-is.
- `version-1/diagrams/` — 17 rendered factory-metaphor images. Reusable where a
  moment wants a visual; the metaphor no longer drives the structure.
- The **discipline** of v1's reveal setup — generated output, guarded by a
  tripwire — carried over to the HyperFrames build and asset manifest. The
  authoring setup was the sound part; the narrative was what failed.

## Implementation Plans

| Plan | Repo | File | Depends on |
|---|---|---|---|
| 2026-09-19-presentation-v2 | `derio-net/super-fr` | `2026-09-19-presentation-v2` | — |

## Open items

1. **Sizing the recorded run.** Tasks 2 + 4 in a Java/Maven devcontainer are
   unmeasured. Dry-run once and time it against the 15–25 min budget before
   committing to the composition; drop Task 3 if it is included and overruns.
2. **The GitLab fix must land before the coda can claim GitLab.** One-line
   `?ref=HEAD` on two methods, plus a decision on whether `file_exists` should
   keep swallowing malformed-request errors into `False`. Worth a separate
   issue — it is an `fr` defect, not presentation work.
3. **HyperFrames composition capabilities** — whether a `/slideshow` slide can
   embed the asciinema-player web component and drive its JS `seek()` API.
   Compositions are plain HTML with data attributes, so this is expected to work
   for the *present* path; it is unverified, and the *render-to-MP4* path has
   different determinism requirements. Verify before authoring.
4. **Workflow shape for v2** — v1 authored a repo-local
   `docs/superpowers/workflows/presentation-showdown.yaml`. v2's steps differ
   (no experiment to design; it is already run and reusable). Decide in `fr-plan`
   whether to author `presentation-v2.yaml` or drive the existing cursor.

## Acceptance rows

**None — deliberately, following v1's precedent** (a grep of `matrix.yaml` for
the v1 presentation work returns nothing).

`docs/acceptance/matrix.yaml` is a registry of business-level acceptance tests
for **fr's own capabilities**. A talk is not an fr capability, and rows asserting
"the deck renders" would dilute a matrix whose value is that every row pins a
claim about the tool. v1 shipped a deck with a real gate —
`tests/unit/test_tripwire_deck_fresh.py` — and correctly added no matrix row for
it.

v2 inherits that shape: the build's guarantees (source is current with rendered
output; every manifest asset resolves; a missing asset fails loudly) are pinned
by a **tripwire test**, not a matrix row.
