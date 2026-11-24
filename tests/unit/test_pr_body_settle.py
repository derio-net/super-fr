"""The PR body's `## PR settle` section (spec 2026-11-23-pr-readiness-wait R7, Test Plan 6):
each key's effective mode and its source, each override's reason, and a required heading."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fr.record.pr_body import REQUIRED_SECTIONS, missing_sections, render_pr_body

from tests.unit.settings_repo import land_on_main, make_repo
from tests.unit.test_deliver_pr_body import live

pytestmark = pytest.mark.own_artifacts

__all__ = ["live"]

HEADING = "## PR settle"
SPEC = "docs/superpowers/specs/2026-11-23-x-design.md"


def _state(spec: str | None = SPEC) -> SimpleNamespace:
    steps = {"brainstorm": SimpleNamespace(emitted={"spec": spec} if spec else None, units=None)}
    return SimpleNamespace(run="r1", steps=steps, workflow="fr-goal@1")


def _section(root: Path, state: SimpleNamespace) -> str:
    body = render_pr_body(root, state)  # type: ignore[arg-type]
    assert HEADING in body, body
    return body.split(HEADING, 1)[1].split("\n## ", 1)[0].strip()


@pytest.fixture
def root(tmp_path: Path) -> Path:
    repo = make_repo(tmp_path)
    land_on_main(repo, "git:\n  settle:\n    conflicts: report\n")
    (repo / SPEC).parent.mkdir(parents=True)
    (repo / SPEC).write_text("# X\n\n## Verification\n\nstrategy: candidate\n")
    return repo


def test_the_section_names_each_mode_and_source_and_says_the_setting_applies(
    root: Path,
) -> None:
    section = _section(root, _state())

    assert "`git.settle.conflicts`: `report` (repo setting)" in section
    assert "`git.settle.ci`: `fix` (default)" in section
    assert "The repo setting applies." in section


def test_an_override_is_named_with_its_source_and_reason(root: Path) -> None:
    (root / SPEC).write_text(
        "# X\n\n## Verification\n\nsettle.ci: off — the forge has no runners this week\n"
    )

    section = _section(root, _state())

    assert "`git.settle.ci`: `off` (spec override: the forge has no runners this week)" in section
    assert "`git.settle.conflicts`: `report` (repo setting)" in section
    assert "The repo setting applies." not in section


def test_a_malformed_override_refuses_the_render_with_its_remedy(root: Path) -> None:
    """Review l-errors-r8: an unreadable override is a refusal, never text in the body."""
    from fr.record.pr_body import PrBodyRefused

    (root / SPEC).write_text("# X\n\n## Verification\n\nsettle.ci: off\n")

    with pytest.raises(PrBodyRefused) as e:
        render_pr_body(root, _state())  # type: ignore[arg-type]

    assert "settle.ci: off" in str(e.value)
    assert "## Verification" in str(e.value) and "reason" in str(e.value)


def test_deliver_refuses_a_malformed_override_and_keeps_the_cursor(
    tmp_path: Path, live: dict[str, str]
) -> None:
    """l-tests-r3: the run's spec `settle.ci: report` with no reason refuses `deliver`."""
    from tests.unit.record_support import RUN, commit_all
    from tests.unit.test_deliver_pr_body import _at_deliver, _deliver

    root = _at_deliver(tmp_path)
    spec = root / "docs" / "spec.md"
    spec.write_text(spec.read_text() + "\n## Verification\n\nsettle.ci: report\n")
    commit_all(root, "bad override")
    (root / "suite.log").write_text("n passed\n")
    cursor = root / "docs" / "superpowers" / "runs" / f"{RUN}.yaml"
    before = cursor.read_bytes()

    _rec, out = _deliver(root)

    assert out.exit_code == 2, out.output
    assert "settle.ci: report" in out.output
    assert cursor.read_bytes() == before


def test_the_heading_is_required_and_a_body_without_it_is_refused() -> None:
    assert HEADING in REQUIRED_SECTIONS
    body = "\n\n".join(h for h in REQUIRED_SECTIONS if h != HEADING)

    assert missing_sections(body) == [HEADING]


def test_the_section_renders_in_required_order(root: Path) -> None:
    body = render_pr_body(root, _state())  # type: ignore[arg-type]

    positions = [body.index(h) for h in REQUIRED_SECTIONS]
    assert positions == sorted(positions)


def test_under_minimal_the_section_is_in_the_durable_render(
    tmp_path: Path, live: dict[str, str]
) -> None:
    from fr.run.model import load_run_state

    from tests.unit.test_deliver_pr_body import RUN, _at_deliver, _deliver
    from tests.unit.test_forge_quiet_pr_body import PLAIN, _durable, _land_policy

    root = _at_deliver(tmp_path)
    _land_policy(root, "forge:\n  pr_body: minimal\n")
    live["body"] = PLAIN

    _rec, out = _deliver(root)

    assert out.exit_code == 0, out.output
    assert load_run_state(root, RUN).steps["deliver"].state == "done"
    assert HEADING in _durable(root).read_text()
    assert HEADING not in live["body"]
