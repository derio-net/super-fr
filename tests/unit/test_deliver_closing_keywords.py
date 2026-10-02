"""`deliver` refuses a PR body that shares one closing keyword across several
issue references (gh#821): on GitHub `Closes #a and #b` closes only `#a`, so
`#b` stays open after its fix ships (#544 did)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.run.model import load_run_state

from tests.unit.test_deliver_pr_body import RUN, _at_deliver, _body, _deliver, live

__all__ = ["live"]  # the fixture, re-exported so pytest finds it here


@pytest.mark.parametrize(
    "line",
    [
        "Closes #1 and #2",
        "Closes #1, #2",
        "fixes: #1 #2",
        "Resolves derio-net/super-fr#1 and derio-net/super-fr#2",
        "Closes https://github.com/o/r/issues/1, https://github.com/o/r/issues/2",
        "Fixes #1 (follow-up to #2)",
    ],
)
def test_a_line_sharing_one_keyword_is_reported(line: str) -> None:
    from fr.record.pr_body import shared_closing_keywords

    assert [bad for bad, _fixed in shared_closing_keywords(f"## Summary\n\n{line}\n")] == [line]


@pytest.mark.parametrize(
    "body",
    [
        "Closes #1\nCloses #2\n",
        "Closes #1 and closes #2\n",
        "Fixes: #1, Resolves #2\n",
        "Fixed derio-net/super-fr#821\n",
        "See #1 and #2 for context\n",  # no closing keyword: mentions, not closes
        "The fix landed after the closed PR\n",  # keywords, but no reference
        "```\nCloses #1 and #2\n```\n",  # GitHub ignores keywords in code
        "Quoting the bug: `Closes #1 and #2` closes only the first\n",
        "Fixes the parser in docs/spec.md\n",
    ],
)
def test_one_keyword_per_reference_passes(body: str) -> None:
    from fr.record.pr_body import shared_closing_keywords

    assert shared_closing_keywords(body) == []


def test_the_fix_puts_every_reference_on_its_own_line_with_the_keyword_as_written() -> None:
    from fr.record.pr_body import shared_closing_keywords

    [(_, fixed)] = shared_closing_keywords("Closes #1, derio-net/super-fr#2 and #3\n")

    assert fixed == ["Closes #1", "Closes derio-net/super-fr#2", "Closes #3"]


def test_deliver_refuses_a_shared_keyword_and_prints_the_corrected_lines(
    tmp_path: Path, live: dict[str, str]
) -> None:
    root = _at_deliver(tmp_path)
    live["body"] = "never read before the render"
    _deliver(root)  # renders pr-body.md
    rendered = _body(root).read_text()
    live["body"] = f"Closes #821 and #822\n\n{rendered}"

    rec, out = _deliver(root)

    assert out.exit_code == 2, out.output
    assert "Closes #821 and #822" in out.output
    assert "Closes #821\n" in out.output and "Closes #822\n" in out.output
    assert load_run_state(root, RUN).steps["deliver"].state == "running"
    assert rec.exists()

    live["body"] = f"Closes #821\nCloses #822\n\n{rendered}"
    rec, out = _deliver(root)

    assert out.exit_code == 0, out.output
    assert load_run_state(root, RUN).steps["deliver"].state == "done"
