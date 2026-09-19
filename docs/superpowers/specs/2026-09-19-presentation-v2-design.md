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
| Recording | Real internal feature; **rendered deck is private**; source is generic and in-repo |
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

## Confidentiality contract

Carried forward from v1: **the driving model is not cleared for the operator's
board.** The ticket is never read by the authoring session; the operator briefs
it in as shape, size, and surfaces touched — never contents.

Two separable problems, resolved differently:

- **Repo hygiene** — the internal repo is never named in super-fr; casts,
  stills and rendered output live *outside* the repo, reached through an asset
  manifest.
- **Content exposure** — the real leak is the code on screen: file contents,
  function names, the business domain. No gitignore fixes that, and `sed` over a
  cast is unreliable (a name can split across write boundaries amid escape
  sequences). Resolved by scope instead: **the rendered deck is private and
  given internally only.**

This yields a clean split worth stating plainly:

> **The deck's source is public and generic. The rendered deck is private.**

Source in `docs/presentation/version-2/` is committable because it contains
prose, structure and annotation timings — no assets. The build resolves assets
from the manifest and **fails loudly when one is missing**, so a checkout that
lacks the private assets cannot silently render an incomplete deck.

## Honesty constraints on the Extensibility coda

The coda names only what an operator can reach today. Verified against
`docs/acceptance/matrix.yaml` on 2026-09-19:

- `multi-repo-spec-fanout` — **not-implemented**: "fake-runner-only and
  operator-unobservable." **Must not appear.**
- `dispatch-unit-declared-by-shape` — **not-implemented**: only `unit:phase` is
  reachable; no shipped path selects run- or spec-granularity. **Must not
  appear as an operator feature.**
- GitLab / Gitea adapters — unit-verified and reachable from `fr apply`, but
  "not yet proven against a live instance." **Name only with that caveat.**

Shipped and demonstrable, and therefore what the coda may contain: phase
executors, model tiers per workload complexity, and the three harnesses.

A talk promising "use it immediately" is destroyed by the first claim that fails
when someone tries it.

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

1. **Which feature gets recorded** — operator brief owed, at shape level only
   (size, surfaces touched, whether it has a natural failure/recovery beat).
2. **HyperFrames composition capabilities** — whether a `/slideshow` slide can
   embed the asciinema-player web component and drive it via its JS `seek()`
   API. Compositions are plain HTML with data attributes, so this is expected to
   work for the *present* path; it is unverified, and the *render-to-MP4* path
   has different determinism requirements. Verify before authoring.
3. **Workflow shape for v2** — v1 authored a repo-local
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
