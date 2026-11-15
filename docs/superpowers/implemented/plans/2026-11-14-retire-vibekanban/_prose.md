# Retire VibeKanban support: plan

Spec: `docs/superpowers/specs/2026-11-14-retire-vibekanban-design.md` (issue #1459).

There are three agentic phases, in order:

1. **Delete** (skeleton). It removes the package and the workspace entries, the runner lists
   (`RUNNER_PACKAGES`, `.fr/candidate-install`, this repo's two profiles), the VK tests and
   their durations, and the acceptance rows that cite them. These go together, because a test
   that imports `fr_vk` cannot outlive the package, and a row citing a deleted test fails
   `fr acceptance check`.
2. **Behaviour.** It adds the one new refusal (`_devcontainer_up` refuses a profile that
   installs `packages/fr-vk`) and the installer cleanup (`cleanup_vk_residue`, and
   `--install-bridge` refuses).
3. **Wording and guard.** It deletes the `fr-runner` skill and fixes the dispatch plugin,
   kept-code comments and docs. The R10 tripwire lands red first and ends green, with an
   allowlist of (file, line regex) pairs that fails on dead entries.

Tests are classified by what they exercise, never by filename: `test_bridge_prompt.py`
tests the kept `fr_dispatch.prompt`. Captured fixtures (`tests/fixtures/github_rest/`,
`tests/scenarios/fixtures/`, `tests/fixtures/transcripts/`) stay byte-identical. No member
issue is a phase `tracking_issue`.
