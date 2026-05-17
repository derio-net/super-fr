# v2 bridge rebuild

**Spec:** `docs/superpowers/specs/2026-05-17-v2-bridge-rebuild-design.md`
(merged in [#150](https://github.com/derio-net/superpowers-for-vk/pull/150),
tracking issue [#147](https://github.com/derio-net/superpowers-for-vk/issues/147))

**Closes** [#132](https://github.com/derio-net/superpowers-for-vk/issues/132)
at Phase 1 merge (cross-repo `RepoLabelEnsure`).

## What this plan delivers

The thin-wrapper bridge v2 promised but never shipped. After this plan:

- All bridge functionality lives in `vk.bridge.*` (`superpowers-for-vk`).
- The legacy 1089-LOC `agent-images/kali/scripts/vk-issue-bridge.py` and its
  194-LOC `vk_mcp_client.py` companion are **deleted**.
- The bridge daemon is invoked via a hidden `python -m vk.bridge` entry
  wrapped by a one-line shell script written by `install.sh --install-bridge`.
  No `vk bridge` public CLI verb.
- The renderer's `_lifecycle_label` knows about dependencies — labels stop
  lying. Operators reading `vk-ready` can trust it.
- Multi-repo dispatch is first-class: `RepoLabelEnsure` groups by destination
  repo; per-phase mutations route to `parse_issue_url(tracking_issue).repo`.

## Shape

Six phases. **Each phase ships as one PR** per this repo's convention. The
spec's phasing is authoritative — every BDD acceptance test in the spec
carries an `<!-- implementation: Phase N -->` annotation that pins it to a
specific phase below. Test IDs (`A1`-`I8`) reference the spec's
"Acceptance tests" section.

| # | Title | Acceptance | Version | Depends on |
|---|---|---|---|---|
| 1 | Renderer dep gating + cross-repo `RepoLabelEnsure` | A1-A6, H1-H6, H8, I7 | 2.1.6 → 2.1.7 | — |
| 2 | `vk._mcp_client` + `vk.bridge.dispatch` | B1-B4, H9 | 2.1.7 → 2.1.8 | 1 |
| 3 | Workspaces + lifecycle + PR state | C1-C5, I5 | 2.1.8 → 2.1.9 | 2 |
| 4 | Slots + dedup + metrics + prompt + config | D1-D5 | 2.1.9 → 2.1.10 | 3 |
| 5 | `vk.bridge.cli` + `__main__` + wrapper + install.sh + resilience | E1-E4, G1, G5, I1-I4, I6 | 2.1.10 → 2.1.11 | 4 |
| 6 | Cutover (delete fat bridge; end-to-end) | F1-F2, F4-F5, G2, G3, G4, H7, I8 | 2.1.11 → **2.2.0** | 5 |
| 7 | `apply_cmd` plan-propagation fix (added post-dispatch 2026-05-17) | — *(spec failure mode #4)* | 2.2.0 → 2.2.1 | 6 |

Phase 6 minor-bumps because `--install-bridge` is a user-visible install
flag and the fat-bridge retirement is a deployment-shape change.

## Why this phase split, not the obvious "extract each submodule"

A pure extraction would give one phase per `vk.bridge.*` submodule (dispatch,
workspaces, pr_state, slots, dedup, metrics, prompt, lifecycle, config — nine
PRs). We're not doing that because:

1. **Phase 1 must close `#132` end-to-end.** Cross-repo `RepoLabelEnsure` is
   a diff-layer fix; the renderer dep-gating fix is also a diff/render layer
   fix. They share `tests/unit/test_v2_diff.py`, the `v2_plan_cross_repo`
   fixture, and the `FakeGhClient` tightening. Splitting them adds churn for
   no review benefit. Both are state-machine projection fixes — that's the
   coherent unit.
2. **Phase 2 must be testable in isolation.** Moving `vk_mcp_client.py` into
   the vk package without also consolidating the duplicated dispatch
   (`sync_issue` + `_McpAdapter.create_card`) would leave Phase 2 unable to
   prove "the duplication is gone" (test B2). The MCP move alone is just a
   file copy; doing the dedup at the same time is the value.
3. **Phases 3, 4 are siblings**, both consume `vk.bridge.dispatch` from
   Phase 2. They can be reviewed in any order; we sequence 3 before 4 because
   workspace/PR-state errors are higher operational impact than slot/dedup.
4. **Phase 5 wires everything.** Until `vk.bridge.cli.main()` exists, no end
   user touches Phases 2-4's modules — the legacy bridge still calls
   `vk.bridge.tick` (which exists today). Phase 5 makes the new entry point
   usable.
5. **Phase 6 is hard-cutover.** Per spec "Out of scope §Multi-version
   coexistence" — once Phase 6 lands, only the v2 path runs. The agent-images
   sibling plan (see "Cross-repo handoff" below) cannot start until
   `superpowers-for-vk` Phase 6 tags `v2.2.0`.
6. **Phase 7 was added mid-rebuild** (2026-05-17) when this very plan's own
   dispatch hit a previously-unknown bug — `vk apply --yes` mis-rendered
   `- Blocked by #N` deps as phase numbers, the legacy bridge body-parsed
   them against unrelated old-closed Issues, and dispatched Phases 2/3/6
   ahead of Phase 1. Phase 1's renderer fix masks the dispatch damage (label
   gating becomes authoritative), but the one-line CLI fix at
   `src/vk/commands/apply_cmd.py:222` removes the latent risk entirely. It's
   in the plan, not deferred as "later" cleanup, specifically because
   "later" is where bugs go to die. See spec failure mode #4 for the full
   narrative.

## Cross-repo handoff

The cutover spans two repos. **`superpowers-for-vk` ships v2.2.0** with the
full `vk.bridge.*` surface + `install.sh --install-bridge`. Then **agent-
images** updates its Dockerfile pin, deletes the fat bridge scripts, points
cron at the wrapper, and adds the smoke test (F3).

agent-images sibling plan: `docs/superpowers/plans/2026-05-17-v2-bridge-
cutover-agent-images/` (in the agent-images repo).

The sibling plan's single phase has `depends_on: []` *within its own plan*
but cross-plan depends on `v2.2.0` being tagged. That ordering lives in this
spec's Implementation Plans table (appended by `vk plan create` automatically)
and is enforced operationally by the Dockerfile pin.

## TDD discipline

Every implementation step is preceded by a failing test step. The spec's BDD
acceptance tests ARE the failing tests for each phase's renderer/diff/dispatch
work. Phase boundaries align to test groups precisely so an implementing agent
can validate "all Group X tests green" before opening the PR.

Pre-push: `uv run ruff format src/ tests/ && uv run ruff check src/ tests/ &&
uv run mypy src/ && uv run pytest -q --no-cov` (per `CLAUDE.md`).

## Out of scope

- All "Out of scope" items from the spec carry over verbatim. Notably:
  - **Multi-version coexistence of the bridge** — hard cutover.
  - **Changes to the VK MCP wire protocol** — the Phase 2 move relocates the
    Python wrapper only.
  - **PEP 668 venv** stays in agent-images. Phase 6 changes only the package
    pin and adds the wrapper.
- The `vk-plan create` non-transactional bug (#133) — orthogonal.
- The dispatch-reachability gate (#146) — already shipped.
