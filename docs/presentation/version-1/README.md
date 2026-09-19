# Presentation, version 1 — abandoned

Shown to one real person in draft. **It does not work, and the reason is not
fixable by editing slides: it has no clear goal and no defined audience.**
Parked here intact so the next attempt can take what is useful.

A new presentation will be planned from scratch, starting from those two
questions rather than from the material.

## What went wrong

The deck grew outward from the *subject* — everything super-fr does, in the
order it was built — instead of inward from a goal. Fourteen upgrades, each
honestly earned, and no answer to "who is listening, and what should change for
them afterwards?" Symptoms, all downstream of that:

- Three stations plus fourteen upgrades plus detours: a tour, not an argument.
- The comparison ends open by design, so a listener is handed evidence and no
  conclusion — fine for a memo, weak for a talk.
- The audience shifts between slides: a teammate who has never seen the tool,
  a maintainer who wants the mechanism, and an operator who wants the commands.

## What is worth reusing

- **`reveal/`** — the deck: `slides.md` is the source, `index.html` is generated
  by `build.py`, guarded by `tests/unit/test_tripwire_deck_fresh.py`. The
  authoring setup is sound and reusable; the narrative is what failed.
- **`diagrams/`** — 17 rendered factory-metaphor images plus
  `image-prompts.md`. The metaphor is the strongest thing here.
- **`experiment/`** — two measured comparisons of the same feature built with
  and without the pipeline:
  - `comparison.md` (super-fr #429, three arms) — including the run that
    corrupted a CI-gated file its own check then rejected.
  - `bc88/comparison.md` (blog-craft #88, two arms) — closer to a fair fight:
    both arms reached green, one by correcting a fixture, one by adding a
    version bump and a changelog entry.
  - `run-metrics.csv` — per-session cost, tokens and duration for every arm.
  - `runbook.md`, `bc88/runbook.md` — the method, and the clean-room setup that
    took two attempts to get right (git identity, `gh` auth, config isolation).

The evidence is reusable as-is. It was gathered to answer "is the ceremony
worth it?", which is a better question than the deck ever put to its audience.

## Known loose ends

- `up-interview.png` and `up-jig.png` are referenced by the last two upgrade
  slides but were never generated; prompts are in `image-prompts.md`.
- `super-fr-showdown.html` / `.pptx` are the dead Marp originals, gitignored.
