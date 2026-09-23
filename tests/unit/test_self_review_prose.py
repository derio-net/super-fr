"""Spec 2026-09-14-ste-output-tone §5.C: self-review warns on long prose."""

from __future__ import annotations

from pathlib import Path

from fr.cli import app
from fr.parser import parse as parse_plan
from fr.plan_ops import self_review
from typer.testing import CliRunner

from tests.unit.test_plan_acceptance_links import _create_plan, _repo, _spec

LONG = " ".join(["word"] * 30) + "."


def _prose_warnings(plan_dir: Path) -> list[str]:
    issues = self_review(parse_plan(plan_dir))
    return [
        i.message for i in issues if i.severity == "warn" and i.message.startswith("prose lint")
    ]


def _plan(tmp_path: Path) -> Path:
    repo = _repo(tmp_path, matrix=False)
    _spec(repo, test_plan=False)
    return _create_plan(repo)


def test_a_clean_plan_has_no_prose_warning(tmp_path: Path) -> None:
    assert _prose_warnings(_plan(tmp_path)) == []


def test_a_pending_step_with_a_long_sentence_warns(tmp_path: Path) -> None:
    plan_dir = _plan(tmp_path)
    phase = plan_dir / "01.yaml"
    text = phase.read_text()
    first_text = text.index("text:")
    phase.write_text(
        text[:first_text] + f"text: {LONG}\n" + text[text.index("\n", first_text) + 1 :]
    )
    warnings = _prose_warnings(plan_dir)
    assert any("step P1.T1.S1" in w and "sentence of 30 words" in w for w in warnings), warnings


def test_the_plan_prose_warns(tmp_path: Path) -> None:
    plan_dir = _plan(tmp_path)
    (plan_dir / "_prose.md").write_text(f"# Plan\n\n{LONG}\n")
    assert any("_prose.md" in w for w in _prose_warnings(plan_dir))


def test_the_spec_warns(tmp_path: Path) -> None:
    plan_dir = _plan(tmp_path)
    spec = tmp_path / "docs/superpowers/specs/2026-07-04-toy.md"
    spec.write_text(spec.read_text() + f"\n{LONG}\n")
    label = "spec docs/superpowers/specs/2026-07-04-toy.md"
    assert any(w.startswith(f"prose lint — {label}") for w in _prose_warnings(plan_dir))


def test_one_source_shows_two_excerpts_then_a_count(tmp_path: Path) -> None:
    """Four issues in one source stay on one line: two excerpts, then the rest
    as a count (phase 7 review, finding I2)."""
    plan_dir = _plan(tmp_path)
    (plan_dir / "_prose.md").write_text("# Plan\n\n" + "\n\n".join([LONG] * 4) + "\n")
    warning = next(w for w in _prose_warnings(plan_dir) if "_prose.md" in w)
    assert "4 issue(s)" in warning
    assert warning.count("sentence of 30 words") == 2
    assert warning.endswith("(+2 more)")


def test_each_prose_warning_prints_on_one_line(tmp_path: Path) -> None:
    """Rich wrapped each warn issue over 3-6 physical lines (phase 7 review, I2)."""
    plan_dir = _plan(tmp_path)
    (plan_dir / "_prose.md").write_text(f"# Plan\n\n{LONG}\n")
    result = CliRunner().invoke(app, ["plan", "self-review", str(plan_dir)])
    printed = [line for line in result.output.splitlines() if line.strip()]
    issues = self_review(parse_plan(plan_dir))
    assert len(printed) == len(issues), printed


def test_prose_warnings_do_not_change_the_exit_code(tmp_path: Path) -> None:
    """The fixture plan has a non-prose error (no skeleton marker), so compare
    against the clean plan's exit code instead of asserting 0."""
    plan_dir = _plan(tmp_path)
    runner = CliRunner()
    baseline = runner.invoke(app, ["plan", "self-review", str(plan_dir)])
    (plan_dir / "_prose.md").write_text(f"# Plan\n\n{LONG}\n")
    result = runner.invoke(app, ["plan", "self-review", str(plan_dir)])
    assert "prose lint" not in baseline.output
    assert "prose lint" in result.output
    assert result.exit_code == baseline.exit_code, result.output


def test_markup_like_prose_does_not_crash_self_review(tmp_path: Path) -> None:
    """Rich reads '[/tmp]' as a closing tag and raises MarkupError, unless the
    CLI prints issues with markup off (phase 6 review, finding I6)."""
    plan_dir = _plan(tmp_path)
    # No period after "(x.md)": the bracket text must land inside the one
    # long sentence that gets flagged, not in a short sentence of its own
    # (see journal discovery r7-sentence-split-excerpt).
    (plan_dir / "_prose.md").write_text(f"# Plan\n\nSee [/tmp] and [the spec](x.md) {LONG}\n")
    result = CliRunner().invoke(app, ["plan", "self-review", str(plan_dir)])
    assert not isinstance(result.exception, Exception) or isinstance(
        result.exception, SystemExit
    ), result.output
    assert "[/tmp]" in result.output
    assert "[warn]" in result.output
