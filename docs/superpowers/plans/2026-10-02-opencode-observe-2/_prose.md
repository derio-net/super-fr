# fr observes OpenCode sessions — batch opencode-observe-2

Spec: `docs/superpowers/specs/2026-10-02-opencode-observe-2-design.md`.

**Porting rule (d-salvage).** Much of phases 1–2 already exists on
`origin/feat/batch-opencode-observe` (closed draft PR #837). Steps name the
salvage commit to port from. New modules and tests come over close to verbatim
(`git show <sha> -- <path>`). Hunks in `commands/run_cmd.py`, `run/telemetry.py`
and other files `main` has moved are **re-applied onto current main as fresh edits**,
never cherry-picked: `main` moved ~1,100 lines under `run_cmd.py` since #837's
base. Salvage commit `9689ee7a` (the input-coverage comparison) and every
coverage mention are dropped: #851 removed that block. #837's fixture builder is
not copied over `main`'s: the run tree is added beside it (spec §H).

- **Phase 1 (skeleton, hard)** — the identity plumbing every later gate
  stands on: the `ObservedSession` protocol, both backends, the run session
  recorded on OpenCode (plugin `shell.env` export, `run_session` root walk),
  gates routed through the protocol, the phase `tests=` witness, and #848's
  positive-evidence attribution.
- **Phase 2 (hard)** — #816: reviewer identity, holder fill, and the
  `review-findings` return check, plus the brief key that carries it.
- **Phase 3 (standard)** — #809, #797, #561: question rounds from opencode.db,
  no `answered_by` default, honest gates wording, the visual witness, parity
  rows, skill prose + both mirror syncs, and the published explainer.

Suite: `uv run pytest -q --no-cov -n auto`; lint `uv run ruff check packages/ tests/`
and `uv run ruff format packages/ tests/`; types per AGENTS.md; plugin
`bun test` in `packages/fr-opencode-plugin`.
