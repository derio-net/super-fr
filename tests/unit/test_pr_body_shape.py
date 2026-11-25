"""The PR's `## Shape of the change` and `deliver`'s shape refusals (spec
2026-11-24-show-me-visuals R9-R11, R18): a required section whose body is the run's
shape file, or one line saying why there is none; `deliver` refuses a run that owes a
shape file and has none, or an invalid one, and a run whose spec cannot be read."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fr.record.pr_body import REQUIRED_SECTIONS, missing_sections, render_pr_body
from fr.run.model import StepRecord, load_run_state
from fr.shape import TWO_FORMS, deliver_shape_refusal, shape_path

from tests.unit.lens_repo import lens_repo
from tests.unit.record_support import RUN, commit_all
from tests.unit.test_deliver_pr_body import _at_deliver, _body, _deliver, live

pytestmark = pytest.mark.own_artifacts

__all__ = ["live"]

HEADING = "## Shape of the change"
SPEC_REL = "docs/spec.md"
WITH_SECTION = "# spec\n\n## Design shape\n\n```\nfr/\n  widget.py\n```\n\n## Other\n"
WITHOUT_SECTION = "# spec\n\n## Design\n\nProse.\n"
SHAPE = "```diff\n fr/\n+  widget.py   # the widget\n```\n"


def _flat(text: str) -> str:
    return " ".join(text.split())


def _state(spec_rel: str | None) -> SimpleNamespace:
    steps: dict[str, object] = {}
    if spec_rel is not None:
        steps["brainstorm"] = StepRecord(state="done", emitted={"spec": spec_rel})
    return SimpleNamespace(run=RUN, steps=steps, workflow="fr-goal@1")


def _section(root: Path, state: SimpleNamespace) -> str:
    body = render_pr_body(root, state)  # type: ignore[arg-type]
    assert HEADING in body, body
    return body.split(HEADING, 1)[1].split("\n## ", 1)[0].strip()


def _repo(tmp_path: Path, spec: str | None = WITH_SECTION, shape: str | None = None) -> Path:
    root = lens_repo(tmp_path)
    if spec is not None:
        (root / SPEC_REL).parent.mkdir(parents=True, exist_ok=True)
        (root / SPEC_REL).write_text(spec)
    if shape is not None:
        path = shape_path(root, RUN)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(shape)
    return root


def test_the_section_is_required_after_the_out_of_scope_findings() -> None:
    assert HEADING in REQUIRED_SECTIONS
    i = REQUIRED_SECTIONS.index("## Out-of-scope findings")
    assert REQUIRED_SECTIONS[i + 1] == HEADING
    assert HEADING in missing_sections("## Findings\n## Out-of-scope findings\n")


def test_the_render_places_it_before_the_review_lenses(tmp_path: Path) -> None:
    root = _repo(tmp_path, shape=SHAPE)
    body = render_pr_body(root, _state(SPEC_REL))  # type: ignore[arg-type]
    assert (
        body.index("## Out-of-scope findings")
        < body.index(HEADING)
        < body.index("## Review lenses")
    )


def test_the_shape_file_is_the_body(tmp_path: Path) -> None:
    root = _repo(tmp_path, shape="\n\n" + SHAPE + "\n\n")
    assert _section(root, _state(SPEC_REL)) == SHAPE.strip()


def test_a_run_with_no_spec(tmp_path: Path) -> None:
    root = _repo(tmp_path, spec=None, shape=SHAPE)
    assert _section(root, _state(None)) == "This run has no spec."
    assert deliver_shape_refusal(root, _state(None)) is None  # type: ignore[arg-type]


def test_a_spec_without_the_section_predates_design_shapes(tmp_path: Path) -> None:
    root = _repo(tmp_path, spec=WITHOUT_SECTION)
    assert _section(root, _state(SPEC_REL)) == "This run predates design shapes."
    assert deliver_shape_refusal(root, _state(SPEC_REL)) is None  # type: ignore[arg-type]


def test_no_shape_file_was_written(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    assert _section(root, _state(SPEC_REL)) == "No shape file was written."


def test_the_refusals_name_the_path_and_both_forms(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    shape_path(root, RUN).parent.mkdir(parents=True, exist_ok=True)
    rel = shape_path(root, RUN).relative_to(root).as_posix()
    missing = deliver_shape_refusal(root, _state(SPEC_REL))  # type: ignore[arg-type]
    assert missing is not None and rel in missing and TWO_FORMS in missing
    shape_path(root, RUN).write_text("We added a widget.\n")
    invalid = deliver_shape_refusal(root, _state(SPEC_REL))  # type: ignore[arg-type]
    assert invalid is not None and rel in invalid and TWO_FORMS in invalid
    assert "not a shape block" in invalid
    shape_path(root, RUN).write_text(SHAPE)
    assert deliver_shape_refusal(root, _state(SPEC_REL)) is None  # type: ignore[arg-type]


def test_an_unreadable_spec_is_refused_naming_it(tmp_path: Path) -> None:
    root = _repo(tmp_path, spec=None, shape=SHAPE)
    refusal = deliver_shape_refusal(root, _state(SPEC_REL))  # type: ignore[arg-type]
    assert refusal is not None and SPEC_REL in refusal


# --- through `fr run resolve --step deliver` ---------------------------------------


def _shape_file(root: Path) -> Path:
    return shape_path(root, RUN)


def _commit(root: Path, message: str) -> None:
    """Commit, then rewrite the suite log so `deliver` does not refuse it as stale."""
    commit_all(root, message)
    (root / "suite.log").write_text("n passed\n")


def test_deliver_refuses_a_missing_shape_file(tmp_path: Path, live: dict[str, str]) -> None:
    root = _at_deliver(tmp_path)
    _shape_file(root).unlink()
    _commit(root, "no shape file")
    live["body"] = "never read"
    _rec, out = _deliver(root)
    assert out.exit_code == 2, out.output
    flat = _flat(out.output)
    assert f"{RUN}.shape.md" in flat and _flat(TWO_FORMS) in flat
    assert load_run_state(root, RUN).steps["deliver"].state == "running"


def test_deliver_refuses_an_invalid_shape_file(tmp_path: Path, live: dict[str, str]) -> None:
    root = _at_deliver(tmp_path)
    _shape_file(root).write_text("Prose about the change.\n")
    _commit(root, "prose shape")
    live["body"] = "never read"
    _rec, out = _deliver(root)
    assert out.exit_code == 2, out.output
    flat = _flat(out.output)
    assert f"{RUN}.shape.md" in flat and "not a shape block" in flat
    assert _flat(TWO_FORMS) in flat


def test_deliver_refuses_an_unreadable_spec(tmp_path: Path, live: dict[str, str]) -> None:
    root = _at_deliver(tmp_path)
    (root / SPEC_REL).unlink()
    _commit(root, "spec gone")
    live["body"] = "never read"
    _rec, out = _deliver(root)
    assert out.exit_code == 2, out.output
    assert SPEC_REL in out.output and "cannot be read" in out.output


def test_the_delivered_body_carries_the_shape_file(tmp_path: Path, live: dict[str, str]) -> None:
    root = _at_deliver(tmp_path)
    live["body"] = "never read"
    _deliver(root)
    body = _body(root).read_text()
    shape = _shape_file(root).read_text().strip()
    assert body.split(HEADING, 1)[1].split("\n## ", 1)[0].strip() == shape


def test_an_in_flight_run_is_refused_once_and_recovers_with_the_render(
    tmp_path: Path, live: dict[str, str]
) -> None:
    """R18: a run whose spec predates the section, with an open PR lacking the heading,
    meets the missing-sections refusal (with its edit command) once; the render fixes it."""
    root = _at_deliver(tmp_path)
    spec = root / SPEC_REL
    text = spec.read_text()
    head, _, rest = text.partition("## Design shape")
    tail = rest.split("\n## ", 1)
    spec.write_text(head + (("## " + tail[1]) if len(tail) > 1 else ""))
    _shape_file(root).unlink()
    _commit(root, "an in-flight run: no design shape")
    live["body"] = "never read"
    _rec, first = _deliver(root)
    assert _body(root).is_file(), first.output
    rendered = _body(root).read_text()
    assert "This run predates design shapes." in rendered
    live["body"] = rendered.replace(HEADING, "## Something else")

    _rec, out = _deliver(root)

    assert out.exit_code == 2, out.output
    flat = _flat(out.output)
    assert HEADING in flat and "pr-body.md" in flat
    live["body"] = _body(root).read_text()
    _rec, out = _deliver(root)
    assert out.exit_code == 0, out.output
    assert load_run_state(root, RUN).steps["deliver"].state == "done"


@pytest.mark.parametrize("pr_body", ["minimal"])
def test_the_minimal_durable_render_carries_the_section(
    tmp_path: Path, live: dict[str, str], pr_body: str
) -> None:
    from tests.unit.test_forge_quiet_pr_body import PLAIN, _durable, _land_policy

    root = _at_deliver(tmp_path)
    _land_policy(root, f"forge:\n  pr_body: {pr_body}\n")
    live["body"] = PLAIN
    _rec, out = _deliver(root)
    assert out.exit_code == 0, out.output
    durable = _durable(root).read_text()
    assert HEADING in durable
    assert _shape_file(root).read_text().strip() in durable


def test_an_undecodable_shape_file_is_refused(tmp_path: Path, live: dict[str, str]) -> None:
    """Lens l-tests-r3: a shape file that exists but cannot be read as UTF-8."""
    root = _at_deliver(tmp_path)
    _shape_file(root).write_bytes(b"```\n\xff\xfe tree\n```\n")
    _commit(root, "undecodable shape")
    live["body"] = "never read"
    _rec, out = _deliver(root)
    assert out.exit_code == 2, out.output
    flat = _flat(out.output)
    assert f"{RUN}.shape.md" in flat and "cannot be read" in flat
    assert _flat(TWO_FORMS) in flat


def test_an_undecodable_shape_file_renders_as_no_file(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    path = shape_path(root, RUN)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\xff\xfe")
    assert _section(root, _state(SPEC_REL)) == "No shape file was written."
