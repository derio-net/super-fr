"""`fr.usage.classify` — pure `(tool name, command|path) -> activity`.

Spec 2026-09-25-lean-cost-aware-process §5.A.4, Test Plan item 2. The command
shapes are real ones from this repo's transcripts, redacted.
"""

from __future__ import annotations

import pytest
from fr.usage.classify import classify

CASES = [
    # (name, target, activity, sub)
    (
        "Bash",
        "uv run fr isolation exec --branch b -- uv run fr journal add --scope plan --kind finding",
        "paperwork",
        "journal_write",
    ),
    (
        "Bash",
        "R=run && uv run fr run resolve $R implement --outcome done",
        "paperwork",
        "run_cursor",
    ),
    ("Bash", "export VIRTUAL_ENV=; uv run fr run advance x", "paperwork", "run_cursor"),
    ("Bash", "fr plan --help", "paperwork", "fr_cli_learning"),
    (
        "Bash",
        "cd ~/.cache/fr/worktrees/x && uv run fr plan edit p --tick P1.T1.S1",
        "paperwork",
        "plan_tick",
    ),
    ("Bash", "uv run fr acceptance set-status --id a --status ci", "paperwork", "acceptance"),
    ("Bash", "uv run fr journal check --scope plan --slug s", "paperwork", "paper_check"),
    ("Bash", "uv run fr pickup docs/superpowers/plans/p --phase 1", "paperwork", "paper_read"),
    ("Read", "docs/superpowers/specs/x.md", "paperwork", "paper_read"),
    ("Read", "~/.cache/fr/worktrees/x/docs/superpowers/specs/x.md", "paperwork", "paper_read"),
    ("Write", "~/wt/docs/superpowers/specs/x-design.md", "paperwork", "spec_write"),
    ("Edit", "packages/fr/src/fr/x.py", "implementation", "code_write"),
    ("Read", "~/wt/packages/fr/src/fr/x.py", "implementation", "code_read"),
    ("Bash", "uv run pytest -q", "implementation", "verify"),
    ("Bash", "cd ~/wt && uv run ruff check packages/ tests/", "implementation", "verify"),
    (
        "Bash",
        "cat > packages/fr/src/fr/x.py <<'EOF'\nprint(1)\nEOF",
        "implementation",
        "code_write",
    ),
    ("Bash", "git status --short", "other", "vcs"),
    ("Bash", "cd ~/wt && git commit -q -m 'x'", "other", "vcs"),
    ("Agent", "", "other", "orchestration"),
    ("Task", "", "other", "orchestration"),
    ("Grep", "", "implementation", "code_read"),
    # other harnesses' tool names canonicalize to the same rules
    ("bash", "uv run pytest -q", "implementation", "verify"),
    ("read", "docs/superpowers/plans/p/01.yaml", "paperwork", "paper_read"),
    ("terminal", "uv run fr journal add --scope plan", "paperwork", "journal_write"),
    ("write_file", "packages/fr/src/fr/x.py", "implementation", "code_write"),
    ("delegate_task", "", "other", "orchestration"),
]


@pytest.mark.parametrize(("name", "target", "activity", "sub"), CASES)
def test_classify(name: str, target: str, activity: str, sub: str) -> None:
    result = classify(name, target)
    assert (result.activity, result.sub) == (activity, sub)


def test_no_tool_call_is_narration() -> None:
    from fr.usage.classify import NARRATION

    assert (NARRATION.activity, NARRATION.sub) == ("other", "narration")
