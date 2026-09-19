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
| `fr isolation up` → worktree + devcontainer | Security | base repo never touched, vs. "please work in a worktree" |
| Batched Q&A — asked once, then left alone | *the contract* | — |
| Spec written, dated, committed | Continuity | — |
| Acceptance rows born and defended | Quality | — |
| Plan as a **folder** with `_meta.yaml` | Continuity | formless plan; checkboxes left unticked |
| Run cursor advances | Continuity | nothing survives the session |
| Phase executors dispatched; tier→model | Extensibility | — |
| TDD per phase; adversarial review loop | Quality | — |
| Journal findings; `check` fails on open ones | Quality | — |
| Merge → archive to `implemented/` | Continuity | specs and plans pile up undifferentiated |
| `fr isolation down` | Security | — |

The angles are deliberately **not** peers. Security bookends, Quality and
Continuity interleave densely, Extensibility surfaces once. That ranking is also
the relevance ranking for someone whose next action is one issue tomorrow.

## Time budget (49–57 min)

| # | Beat | Min |
|---|---|---|
| 1 | Hook — why your sessions go sideways | 3 |
| 2 | What a skill is, and how it gets used | 5 |
| 3 | **The run, annotated** | 28–32 |
| 4 | Was the ceremony worth it? — measured | 3 |
| 5 | Extensibility coda — shipped items only | 2 |
| 6 | Quickstart: `fr-init` on her repo, live | 8–12 |
| 7 | Discussion | — |

Beat 3 is the talk. Beats 1–2 buy the right to it; 4–6 convert it.

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

**Recording is BLOCKED on [#486](https://github.com/derio-net/super-fr/issues/486).**
The run must not be recorded until the GitLab adapter works live. This is not
caution about a broken demo — GitLab is the only forge at the audience's
employer, so **the recording's whole claim is that this works on their stack.**
A run on GitHub would prove nothing to them.

**Setup owed before recording:**

1. **Remote repointed** ✅ (2026-09-19). `origin` is now the operator's own
   fork; the team's project is kept as `upstream` with its push URL set to
   `DISABLED`, verified by dry-run. A `/fr-goal` run opens merge requests
   unattended, so an unreachable push path on another team's repo is a safety
   property, not tidiness. Issue and MR therefore land in the operator's own
   namespace.
2. `fr-init` to scaffold a Java 17 + Maven devcontainer profile. Previously
   done and then reverted, so the repo is pristine again — which conveniently
   makes it a candidate for the live `fr-init` in beat 6.
3. Declare `backend: gitlab` in `.devcontainer/fr-profiles.yaml`. Without it
   `detect_backend` resolves a self-hosted host to `"github"`.
4. Create the issue from the two chosen exercises — the fork currently has none.
5. **Pre-warm the Maven dependency cache in the image.** A first Maven build
   downloading the world would dominate the recording and measure the network,
   not the pipeline.
6. Capture apparatus per `docs/presentation/version-2/runbook.md`.

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
- Phase executors, model tiers per workload complexity, the three harnesses.

**Not claimable — different features that merely sound the same:**

- `multi-repo-spec-fanout` — automatic per-repo work-item **dispatch**.
  `not-implemented`, "fake-runner-only and operator-unobservable." A spec
  *driving* plans across repos works; a spec *fanning out* dispatch does not.
- `dispatch-unit-declared-by-shape` — selecting run- or spec-**granularity**
  for dispatch. `not-implemented`; only `unit:phase` is reachable. Authoring
  and running a shape works; choosing its dispatch granularity does not.

**GitLab — does NOT currently pass.** Tested live on 2026-09-19 against
a self-hosted GitLab (host redacted), and this is the first time the adapter
met a real instance. `list_dir` works and the issues endpoint is reachable, but:

- `file_exists` and `read_file` are **broken**. GitLab's
  `GET /projects/:id/repository/files/:path` requires a `ref` query parameter;
  `real_glabclient.py` sends none, so the API returns HTTP 400
  `{"error":"ref is missing, ref is empty"}`.
- The severity is asymmetric. `read_file` raises; `file_exists` swallows every
  `GlabError` into `False` under its documented fail-soft posture, so **a
  malformed request is indistinguishable from an absent file**. The unit suite
  mocks `_run_glab`, so the missing parameter never reached an API and the
  tests stayed green — the exact shape of defect that "unit-verified but never
  proven live" conceals.
- `_run_glab` never passes `--hostname`, and `GITLAB_HOST` appears **nowhere**
  in this repo, so there is no documented way to target a self-hosted instance.
- `_hosts.DEFAULT_HOST_BACKENDS` covers only `github.com` / `gitlab.com`, so
  a self-hosted GitLab host resolves to `"github"` unless
  `.devcontainer/fr-profiles.yaml` declares `backend: gitlab`.

**Fix is verified and small:** `?ref=HEAD` works and is branch-agnostic
(this project's default branch is `master`, not `main`). Until it lands, the
coda may not claim GitLab. Gitea stays unproven and unclaimed by agreement.

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
