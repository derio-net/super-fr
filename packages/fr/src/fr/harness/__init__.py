"""`fr.harness` — the harness-parity vocabulary, schema, and shipped matrix.

2026-09-18 harness-parity-matrix spec §3.A, Phase 1 (walking skeleton).
`parity.yaml` sits inside this package (`src/fr/harness/parity.yaml`), so
hatchling's `packages = ["src/fr"]` ships it with no manifest work — the
same trick `fr/workflows/fr-goal.yaml` already uses (spec §3.A).
`load_matrix()` resolves it via `importlib.resources`, never a
repo-relative path, so it works from an installed wheel with no checkout
present (the Phase 1 skeleton smoke: `fr harness parity` run from outside
the repo).
"""

from __future__ import annotations

import importlib.resources

from fr.harness.model import (
    HARNESSES,
    STATES,
    HarnessError,
    HarnessState,
    Matrix,
    Surface,
    parse_matrix,
)

__all__ = [
    "HARNESSES",
    "STATES",
    "TOOL_VOCABULARY",
    "HarnessError",
    "HarnessState",
    "Matrix",
    "Surface",
    "load_matrix",
    "parse_matrix",
]

TOOL_VOCABULARY: dict[str, frozenset[str]] = {
    "claude-code": frozenset(
        {
            "AskUserQuestion",
            "Agent",
            "Skill",
            "NotebookEdit",
            "WorktreeCreate",
            "WorktreeRemove",
            "MultiEdit",
        }
    ),
    # OpenCode's dispatch tool (2026-09-19 opencode-subagent-dispatch spec
    # §3.A/§3.D): input `{prompt, description, subagent_type, command}`, and
    # it resolves the agent BY NAME afterwards — so the call carries NO
    # model. That single fact is what forces one agent per tier instead of a
    # model argument at dispatch time.
    #
    # Registered as the two-word prose form, not the bare tool id `task`.
    # Spec §3.D claimed no bare `task` token existed in the skill trees; it
    # did, on `origin/main` — fr-execute and fr-plan use `task` as fr's OWN
    # plan noun (phase / task / step), and registering the id would fire on
    # that in twelve places and in every future sentence about a plan task.
    # A tripwire that flags the repo's own domain vocabulary gets appeased,
    # not obeyed. BE HONEST ABOUT THE TRADE: a leak written as a bare `task`
    # outside a scoped clause is NOT caught; "the task tool" — the way prose
    # instructing a reader actually reads — is.
    "opencode": frozenset({"tool.execute.before", "task tool"}),
    "hermes": frozenset({"delegate_task"}),
    "codex": frozenset(),
    "copilot-cli": frozenset(),
}
"""Spec §3.C: the tool names that are each harness's OWN — used by
`fr.harness.prose.scan_prose` to flag a harness-specific tool named outside
an explicitly scoped `**Harness — <topic>:**` clause. Keyed by every
member of `HARNESSES` (closed-world, same reason `Surface` requires every
harness key): `codex`/`copilot-cli` carry no tools of their own today, an
empty frozenset rather than a missing key. No name may appear under two
harnesses — checked by `test_no_tool_name_is_claimed_by_two_harnesses` —
because an ambiguous name would leave the tripwire unable to say which
harness a bare mention serves."""


def load_matrix() -> Matrix:
    """The shipped `parity.yaml`, parsed — the one matrix every render and
    check starts from.

    Reads via `importlib.resources.files("fr.harness")`, which resolves
    correctly whether `fr` is an editable checkout install or a zipped
    wheel — `fr.harness` is a real package (carries `__init__.py`), so no
    `as_file` extraction dance is needed the way `fr.workflow.resolve`
    needs one for the data-only `fr.workflows` directory."""
    text = (
        importlib.resources.files("fr.harness").joinpath("parity.yaml").read_text(encoding="utf-8")
    )
    return parse_matrix(text)
