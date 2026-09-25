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
    # p1-r2: the reviewer's unwrap / prefix shapes ...
    ("Bash", "uv run fr isolation exec --branch b -- git status", "other", "vcs"),
    ("Bash", "F=docs/superpowers/plans/p/01.yaml && cat $F", "paperwork", "paper_read"),
    ("Bash", "export X=; git log", "other", "vcs"),
    (
        "Bash",
        "fr isolation exec --branch b -- bash -lc 'cat > packages/x.py <<EOF'",
        "implementation",
        "code_write",
    ),
]

UNWRAP_DEPENDENT = [
    # ... and the ones whose answer DEPENDS on it: each lands on a different rule
    # when `_unwrap` is a no-op (pinned by test_these_cases_need_the_unwrap)
    ("Bash", "uv run fr isolation exec --branch b -- git status", "other", "vcs"),
    ("Bash", "fr isolation exec --branch b -- bash -lc 'git log -1'", "other", "vcs"),
    ("Bash", "GIT_PAGER=cat git log --oneline", "other", "vcs"),
    # $VAR / ${VAR} substitution: the path lives only in the stripped value
    ("Bash", "F=docs/superpowers/plans/p/01.yaml && cat > $F <<'EOF'", "paperwork", "plan_write"),
    ("Bash", "export F=packages/fr/x.py; cat > ${F} <<'EOF'", "implementation", "code_write"),
]

CASES += UNWRAP_DEPENDENT
CASES += [
    # p1-r6: .fr-deliver/ holds deliver's tests=<log> — the suite's output, so
    # writing or reading it is verification, whichever tool touched it
    ("Bash", "uv run pytest -q > .fr-deliver/tests.log 2>&1", "implementation", "verify"),
    ("Write", "~/wt/.fr-deliver/tests.log", "implementation", "verify"),
    ("Read", ".fr-deliver/tests.log", "implementation", "verify"),
]


@pytest.mark.parametrize(("name", "target", "activity", "sub"), CASES)
def test_classify(name: str, target: str, activity: str, sub: str) -> None:
    result = classify(name, target)
    assert (result.activity, result.sub) == (activity, sub)


@pytest.mark.parametrize(("name", "target", "activity", "sub"), UNWRAP_DEPENDENT)
def test_these_cases_need_the_unwrap(
    name: str, target: str, activity: str, sub: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.usage import classify as module

    monkeypatch.setattr(module, "_unwrap", lambda command: command)
    assert classify(name, target).sub != sub


def test_no_tool_call_is_narration() -> None:
    from fr.usage.classify import NARRATION

    assert (NARRATION.activity, NARRATION.sub) == ("other", "narration")
