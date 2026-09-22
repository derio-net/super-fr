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
import re

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
    "ARGUMENT_VOCABULARY",
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

ARGUMENT_VOCABULARY: dict[str, dict[str, re.Pattern[str]]] = {
    "claude-code": {
        'isolation: "worktree"': re.compile(r"""isolation\s*[:=]\s*["']?worktree\b"""),
        "run_in_background": re.compile(r"\brun_in_background\b"),
    },
    # OpenCode's `timeout` is deliberately NOT registered (spec §3.A): it is
    # ordinary English and would fire on every sentence about a timeout — the
    # same trade TOOL_VOCABULARY states for `task`. A limit, not an oversight.
    "opencode": {},
    "hermes": {
        "background=true": re.compile(r"\bbackground\s*=\s*true\b"),
        "notify_on_complete": re.compile(r"\bnotify_on_complete\b"),
    },
    "codex": {},
    "copilot-cli": {},
}
"""2026-09-22 harness-argument-neutrality spec §3.A. `TOOL_VOCABULARY`'s
sibling, over a different kind of harness-specific name: not a tool a skill
invokes (`Agent`, `delegate_task`), but an ARGUMENT a skill passes one — a
flag or field name that means something only on its own harness (Claude
Code's `isolation: "worktree"` dispatch flag, Hermes's `background=true`).
Same closed-world rule, keyed by every member of `HARNESSES`. Each harness
maps an argument name (what a violation reports) to a compiled-at-import
regex rather than a bare string, because an argument can be spelled several
ways in prose (`isolation: "worktree"` vs. `isolation="worktree"`) where a
tool name is one literal token. Patterns are case-sensitive and are the
spec §3.A table verbatim. `scan_prose` scans them under exactly the same
clause rules as `TOOL_VOCABULARY`, and no name may be claimed by two
harnesses across the two vocabularies together
(`test_no_name_is_claimed_by_two_harnesses_across_both_vocabularies`)."""


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
