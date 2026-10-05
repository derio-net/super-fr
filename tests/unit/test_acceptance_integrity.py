"""Batch `acceptance-integrity` — the acceptance edit surface keeps what it records true.

- gh#470: a matrix whose `rows:` items are flush-left (PyYAML's default dump) is
  valid YAML, and `add` / `set-status` must edit it instead of rolling back.
- gh#531: a `#L<n>` anchor into a Python file names the least stable property of
  a test. Name anchors (`#test_x`, `#TestX::test_y` — pytest's node spelling)
  are validated by `check`, refused as line anchors at authoring, and converted
  from line anchors by a matrix repair.
- gh#769: a set-status that keeps the status names what changed, never `X → X`.
- gh#654 / gh#656: the unknown-level refusal reads right for adds and drops, and
  `merge_levels` refuses an unknown level on its own.
- gh#655: the record engine refuses a ref both dropped and added, as the CLI does.
- gh#965 / gh#893: unittest spells the same test identity — `Class.test` ids,
  any `TestCase` subclass collected — and both the resolver and the repair read it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fr.acceptance.model import AcceptanceError, Row, load_matrix, parse_matrix
from fr.cli import app
from typer.testing import CliRunner

from tests.unit.acceptance_helpers import make_repo, row

runner = CliRunner()


def _invoke(root: Path, monkeypatch: pytest.MonkeyPatch, *args: str):
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    return runner.invoke(app, ["acceptance", *args])


def _matrix(root: Path) -> Path:
    return root / "docs" / "acceptance" / "matrix.yaml"


def _row(root: Path, row_id: str) -> Row:
    return next(r for r in load_matrix(_matrix(root)).rows if r.id == row_id)


def _new(id: str, capability: str = "demo") -> Row:
    return Row(
        id=id,
        capability=capability,
        acceptance="Probe.",
        origin=("own:docs/superpowers/specs/s.md",),
        levels={"unit": ("own:tests/test_a.py",)},
        status="not-implemented",
        notes="n",
    )


# --- gh#470: flush-left `rows:` ---------------------------------------------

FLUSH = (
    "org: derio-net\nrepo: own\nrows:\n"
    "- id: r1\n"
    "  capability: demo\n"
    "  acceptance: A row whose notes fit on one line.\n"
    "  origin:\n"
    "  - own:docs/superpowers/specs/s.md\n"
    "  status: not-implemented\n"
    "  notes: Short.\n"
)


@pytest.mark.parametrize("capability", ["demo", "other"])
def test_insert_into_flush_left_rows_keeps_the_matrix_valid(capability: str) -> None:
    from fr.acceptance.edit import insert_row

    out = insert_row(FLUSH, _new("probe", capability))

    assert [r.id for r in parse_matrix(out).rows] == ["r1", "probe"]
    assert "\n- id: probe\n" in out, "the new item takes its siblings' indentation"
    assert out.startswith(FLUSH), "every existing byte is kept"


def test_replace_in_flush_left_rows_keeps_the_matrix_valid() -> None:
    from fr.acceptance.edit import replace_row

    moved = _new("r1").model_copy(update={"capability": "demo", "status": "skipped"})
    out = replace_row(FLUSH, "r1", moved)

    assert parse_matrix(out).rows[0].status == "skipped"
    assert out.startswith("org: derio-net\nrepo: own\nrows:\n- id: r1\n")


def test_insert_into_an_empty_rows_key_keeps_the_indented_default() -> None:
    from fr.acceptance.edit import insert_row

    out = insert_row("org: derio-net\nrepo: own\nrows:\n", _new("first"))

    assert [r.id for r in parse_matrix(out).rows] == ["first"]
    assert "\n  - id: first\n" in out


def test_add_appends_to_a_flush_left_matrix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_repo(tmp_path, "", header="")
    _matrix(root).write_text(FLUSH)
    result = _invoke(
        root,
        monkeypatch,
        "add",
        "--id",
        "probe",
        "--capability",
        "demo",
        "--acceptance",
        "Probe.",
        "--origin",
        "own:docs/superpowers/specs/s.md",
        "--status",
        "not-implemented",
        "--notes",
        "n",
    )
    assert result.exit_code == 0, result.output
    assert [r.id for r in load_matrix(_matrix(root)).rows] == ["r1", "probe"]


# --- gh#531: name anchors, not line anchors, into Python --------------------

SOURCE = """\
import pytest


def helper():
    return 1


def test_alpha():
    assert helper()


@pytest.mark.parametrize("x", [1])
def test_beta(x):
    y = x
    assert y


class TestGroup:
    def test_inner(self):
        assert True

    async def test_async(self):
        assert True
"""


def test_node_line_resolves_functions_classes_and_methods() -> None:
    from fr.acceptance.anchors import node_line

    assert node_line(SOURCE, "test_alpha") == 8
    assert node_line(SOURCE, "test_beta") == 13, "the def line, not the decorator's"
    assert node_line(SOURCE, "TestGroup") == 18
    assert node_line(SOURCE, "TestGroup::test_inner") == 19
    assert node_line(SOURCE, "TestGroup::test_async") == 22
    assert node_line(SOURCE, "test_missing") is None
    assert node_line(SOURCE, "TestGroup::test_missing") is None
    assert node_line(SOURCE, "test_inner") is None, "a method is not a module-level name"
    assert node_line("def broken(:\n", "broken") is None


def test_enclosing_node_names_the_test_a_line_sits_in() -> None:
    from fr.acceptance.anchors import enclosing_node

    assert enclosing_node(SOURCE, 8) == "test_alpha"
    assert enclosing_node(SOURCE, 9) == "test_alpha"
    assert enclosing_node(SOURCE, 12) == "test_beta", "a decorator line belongs to its def"
    assert enclosing_node(SOURCE, 15) == "test_beta"
    assert enclosing_node(SOURCE, 18) == "TestGroup"
    assert enclosing_node(SOURCE, 20) == "TestGroup::test_inner"
    assert enclosing_node(SOURCE, 1) is None, "a module-level line names no test"
    assert enclosing_node(SOURCE, 4) == "helper"
    assert enclosing_node(SOURCE, 999) is None


@pytest.mark.parametrize(
    ("ref", "refused"),
    [
        ("own:tests/test_a.py#L12", True),
        ("own:tests/test_a.py#L12-L20", True),
        ("own:tests/test_a.py#test_a", False),
        ("own:tests/test_a.py", False),
        ("own:.github/workflows/ci.yml#L40", False),
        ("own:docs/superpowers/specs/s.md#L3", False),
    ],
)
def test_line_anchor_error_refuses_only_line_anchors_into_python(ref: str, refused: bool) -> None:
    from fr.acceptance.anchors import line_anchor_error

    assert (line_anchor_error(ref) is not None) is refused


def _check_errors(root: Path) -> list[str]:
    from fr.acceptance.check import check

    return check(load_matrix(_matrix(root)), root).errors


def test_check_accepts_a_name_anchor_that_resolves(tmp_path: Path) -> None:
    root = make_repo(tmp_path, row(unit='"own:tests/test_a.py#test_a"'))
    assert _check_errors(root) == []


def test_check_refuses_a_name_anchor_that_names_no_test(tmp_path: Path) -> None:
    root = make_repo(tmp_path, row(unit='"own:tests/test_a.py#test_gone"'))
    errors = _check_errors(root)
    assert any("test_gone" in e and "names no" in e for e in errors), errors


def test_check_refuses_a_line_anchor_into_python_and_suggests_the_name(tmp_path: Path) -> None:
    root = make_repo(tmp_path, row(unit='"own:tests/test_a.py#L1"'))
    errors = _check_errors(root)
    assert any("line anchor" in e and "own:tests/test_a.py#test_a" in e for e in errors), errors


def test_check_leaves_line_anchors_into_other_files_alone(tmp_path: Path) -> None:
    root = make_repo(tmp_path, row(unit='"own:.github/workflows/ci.yml#L1"'))
    assert _check_errors(root) == []


def test_set_status_refuses_a_new_line_anchor_into_python(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_repo(tmp_path, row(id="target", status="skipped"))
    before = _matrix(root).read_bytes()
    result = _invoke(
        root,
        monkeypatch,
        "set-status",
        "--id",
        "target",
        "--status",
        "ci",
        "--notes",
        "n",
        "--level",
        "unit=own:tests/test_a.py#L1",
    )
    assert result.exit_code == 2, result.output
    assert "line anchor" in result.output
    assert _matrix(root).read_bytes() == before


def test_the_ad_hoc_report_links_a_name_anchor_to_its_current_line(tmp_path: Path) -> None:
    from fr.acceptance.report import LinkBuilder

    root = make_repo(tmp_path, "")
    (root / "tests" / "test_a.py").write_text("\n\ndef test_a(): pass\n")

    def url(probe: bool) -> str:
        return LinkBuilder(
            mode="github",
            ref="main",
            root=root,
            out_dir=root,
            sibling_root="..",
            org="derio-net",
            own_repo="own",
            probe=probe,
        ).url("own:tests/test_a.py#test_a")

    assert url(probe=True).endswith("/tests/test_a.py#L3")
    assert url(probe=False).endswith("/tests/test_a.py#test_a"), (
        "the committed reports stay a pure function of matrix.yaml"
    )


# --- gh#531: the matrix repair converting line anchors ----------------------


def _repair():
    from fr.artifacts.matrix_anchors import MATRIX_NAME_ANCHORS_REPAIR

    return MATRIX_NAME_ANCHORS_REPAIR


def test_the_repair_is_registered_for_the_matrix_kind() -> None:
    import fr.artifacts  # noqa: F401  (registration rides on the package import)
    from fr.artifacts.runner import MIGRATIONS

    assert _repair() in MIGRATIONS.repairs("matrix")


def test_the_repair_converts_line_anchors_that_land_in_a_test(tmp_path: Path) -> None:
    root = make_repo(
        tmp_path,
        row(id="r1", unit='"own:tests/test_a.py#L1", "own:tests/test_b.py#L10"')
        + row(id="r2", unit='"own:tests/test_b.py#L1"'),
    )
    (root / "tests" / "test_b.py").write_text(
        "def test_b1(): pass\n" + "\n" * 8 + "def test_b10(): pass\n"
    )
    path = _matrix(root)
    assert _repair().applies(path)

    _repair().fn(path)

    rows = {r.id: r for r in load_matrix(path).rows}
    assert rows["r1"].levels["unit"] == (
        "own:tests/test_a.py#test_a",
        "own:tests/test_b.py#test_b10",
    )
    assert rows["r2"].levels["unit"] == ("own:tests/test_b.py#test_b1",), (
        "#L1 is not a prefix of #L10"
    )
    assert not _repair().applies(path), "applying the repair makes its predicate false"


def test_the_repair_leaves_what_it_cannot_convert(tmp_path: Path) -> None:
    root = make_repo(
        tmp_path,
        row(
            id="r1",
            unit='"own:tests/test_c.py#L1", "sib:tests/test_x.py#L5", "own:tests/test_c.py#L4"',
        ),
    )
    (root / "tests" / "test_c.py").write_text(
        "import os\n\ndef _helper():\n    return 1\n\ndef test_c(): pass\n"
    )
    path = _matrix(root)

    assert not _repair().applies(path), (
        "a module-level line, a sibling repo, and a line inside a helper (an anchor that "
        "slid off its test, not one that names a test) all stay as they are"
    )


@pytest.mark.parametrize(
    ("node", "is_test"),
    [
        ("test_a", True),
        ("TestGroup", True),
        ("TestGroup::test_inner", True),
        ("_helper", False),
        ("TestGroup::_setup", False),
        ("Helper::test_x", False),
    ],
)
def test_is_test_node_follows_pytest_collection(node: str, is_test: bool) -> None:
    from fr.acceptance.anchors import is_test_node

    assert is_test_node(node) is is_test


def test_check_does_not_suggest_a_helper_as_the_anchor(tmp_path: Path) -> None:
    root = make_repo(tmp_path, row(unit='"own:tests/test_a.py#L2"'))
    (root / "tests" / "test_a.py").write_text(
        "def _helper():\n    return 1\n\ndef test_a(): pass\n"
    )
    errors = _check_errors(root)
    assert any("sits in no test" in e for e in errors), errors


def test_the_repair_regenerates_committed_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_repo(tmp_path, row(id="r1", unit='"own:tests/test_a.py#L1"'))
    assert _invoke(root, monkeypatch, "report", "--deterministic").exit_code == 0

    wrote = list(_repair().fn(_matrix(root)) or ())

    assert {p.name for p in wrote} == {
        "report_local.html",
        "report_linked.html",
        "report_linked.md",
    }
    assert _invoke(root, monkeypatch, "report", "--check").exit_code == 0
    assert "test_a.py#test_a" in (root / "docs/acceptance/report_linked.md").read_text()


# --- gh#769: set-status names what changed ----------------------------------


def test_set_status_with_an_unchanged_status_names_the_added_level(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fr.commands.acceptance_cmd as cmd

    root = make_repo(tmp_path, row(id="target", status="skipped"))
    (root / "tests" / "test_b.py").write_text("def test_b(): pass\n")
    messages: list[str] = []
    real = cmd._apply_rows

    def spy(root_: Path, item: object, message: str, drops: object = None) -> None:
        messages.append(message)
        real(root_, item, message, drops)  # type: ignore[arg-type]

    monkeypatch.setattr(cmd, "_apply_rows", spy)
    result = _invoke(
        root,
        monkeypatch,
        "set-status",
        "--id",
        "target",
        "--status",
        "skipped",
        "--notes",
        "more evidence",
        "--level",
        "unit=own:tests/test_b.py",
    )
    assert result.exit_code == 0, result.output
    assert "skipped → skipped" not in messages[0] + result.output
    assert "+1 level ref" in messages[0], messages
    assert "+1 level ref" in result.output


def test_describe_move_names_each_kind_of_change() -> None:
    from fr.acceptance.edit import describe_move

    old = _new("r").model_copy(update={"status": "skipped"})
    assert describe_move(old, old.model_copy(update={"status": "ci"})) == "skipped → ci"
    more = old.model_copy(
        update={"levels": {"unit": ("own:tests/test_a.py",), "int": ("own:tests/i.py",)}}
    )
    assert describe_move(old, more) == "skipped (+1 level ref)"
    fewer = old.model_copy(update={"levels": {}})
    assert describe_move(old, fewer) == "skipped (-1 level ref)"
    assert describe_move(old, old.model_copy(update={"notes": "other"})) == "skipped (notes)"
    assert describe_move(old, old) == "skipped (unchanged)"


# --- gh#654 / gh#656: unknown evidence levels -------------------------------


def test_merge_levels_refuses_an_unknown_level() -> None:
    from fr.acceptance.edit import merge_levels

    with pytest.raises(AcceptanceError, match="unknown level keys"):
        merge_levels({}, {"unti": ["own:tests/test_a.py"]})


@pytest.mark.parametrize("verb", ["merge", "drop"])
def test_the_unknown_level_refusal_reads_right_for_adds_and_drops(verb: str) -> None:
    from fr.acceptance.edit import drop_levels, merge_levels

    with pytest.raises(AcceptanceError) as exc:
        if verb == "merge":
            merge_levels({}, {"unti": ["own:tests/test_a.py"]})
        else:
            drop_levels({"unit": ("own:tests/test_a.py",)}, {"unti": ["own:tests/test_a.py"]})
    message = str(exc.value)
    assert "silently drop refs" not in message
    assert "neither added nor removed" in message


# --- gh#655: the engine refuses a contradictory drop ------------------------


def test_the_engine_refuses_a_ref_both_dropped_and_added(tmp_path: Path) -> None:
    from fr.record.apply import RecordRefusedError, RecordTarget, apply_record
    from fr.record.model import AcceptanceItem, StepRecord

    root = make_repo(tmp_path, row(id="target", status="skipped"))
    before = _matrix(root).read_bytes()
    record = StepRecord(
        acceptance=(
            AcceptanceItem(
                id="target",
                status="ci",
                notes="n",
                levels={"unit": ("own:tests/test_a.py",)},
            ),
        )
    )
    target = RecordTarget(
        message="m", acceptance_drops={"target": {"unit": ("own:tests/test_a.py",)}}
    )

    with pytest.raises(RecordRefusedError, match="both"):
        apply_record(root, None, record, target=target)
    assert _matrix(root).read_bytes() == before
    assert yaml.safe_load(before)  # still the original, valid matrix


# --- review of this batch ----------------------------------------------------


def test_replace_keeps_a_section_comment_between_flush_left_rows() -> None:
    from fr.acceptance.edit import replace_row

    text = FLUSH + "\n# --- section B ---\n" + FLUSH.split("rows:\n", 1)[1].replace("r1", "r2")
    moved = _new("r1").model_copy(update={"status": "skipped"})

    out = replace_row(text, "r1", moved)

    assert "\n\n# --- section B ---\n- id: r2\n" in out
    assert [r.status for r in parse_matrix(out).rows] == ["skipped", "not-implemented"]


def test_the_repair_never_rewrites_inside_a_longer_repo_name(tmp_path: Path) -> None:
    header = "org: derio-net\nrepo: fr\nrows:\n"
    root = make_repo(
        tmp_path,
        row(id="r1", origin='"fr:docs/superpowers/specs/s.md"', unit='"fr:tests/test_a.py#L1"')
        + row(
            id="r2", origin='"fr:docs/superpowers/specs/s.md"', unit='"super-fr:tests/test_a.py#L1"'
        ),
        name="fr",
        header=header,
    )

    _repair().fn(_matrix(root))

    rows = {r.id: r for r in load_matrix(_matrix(root)).rows}
    assert rows["r1"].levels["unit"] == ("fr:tests/test_a.py#test_a",)
    assert rows["r2"].levels["unit"] == ("super-fr:tests/test_a.py#L1",), (
        "a sibling's ref is not ours"
    )


def test_the_repair_writes_nothing_when_the_reports_cannot_render(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fr.acceptance.report as report

    root = make_repo(tmp_path, row(id="r1", unit='"own:tests/test_a.py#L1"'))
    assert _invoke(root, monkeypatch, "report", "--deterministic").exit_code == 0
    before = _matrix(root).read_bytes()

    def boom(*_a: object, **_k: object) -> dict[str, str]:
        raise RuntimeError("render failed")

    monkeypatch.setattr(report, "render_committed_set", boom)
    with pytest.raises(RuntimeError):
        _repair().fn(_matrix(root))
    assert _matrix(root).read_bytes() == before, "the repair retries next run, not half-done"


# --- gh#965 / gh#893: unittest's spelling of a test identity ---------------

UNITTEST_SOURCE = """\
import unittest


class FooTests(unittest.TestCase):
    def setUp(self):
        self.x = 1

    def test_x(self):
        assert self.x


class Base(unittest.IsolatedAsyncioTestCase):
    pass


class BarChecks(Base):
    async def test_y(self):
        assert True


class Plain:
    def test_z(self):
        assert True
"""


def test_node_line_resolves_unittest_dotted_ids() -> None:
    from fr.acceptance.anchors import node_line

    assert node_line(SOURCE, "TestGroup.test_inner") == 19, "unittest's '.' is '::'"
    assert node_line(UNITTEST_SOURCE, "FooTests.test_x") == 8
    assert node_line(SOURCE, "TestGroup.test_missing") is None
    assert node_line(SOURCE, "TestGroup.") is None, "an empty part names nothing"
    assert node_line(SOURCE, "TestGroup..test_inner") is None
    assert node_line(SOURCE, ".test_alpha") is None


def test_check_accepts_a_unittest_dotted_anchor(tmp_path: Path) -> None:
    root = make_repo(tmp_path, row(unit='"own:tests/test_u.py#TestU.test_u"'))
    (root / "tests" / "test_u.py").write_text("class TestU:\n    def test_u(self): pass\n")
    assert _check_errors(root) == []


@pytest.mark.parametrize(
    ("line", "name"),
    [
        (9, "FooTests::test_x"),
        (18, "BarChecks::test_y"),
        (6, None),
        (23, None),
    ],
)
def test_collection_recognises_unittest_testcase_subclasses(line: int, name: str | None) -> None:
    """A `TestCase` subclass is collected whatever its name — directly or via a
    base in the same module; its `setUp` is still a helper, and a plain class
    not named `Test*` still is not collected."""
    from fr.acceptance.anchors import collected_node_at

    assert collected_node_at(UNITTEST_SOURCE, line) == name


def test_the_repair_converts_a_line_anchor_inside_a_testcase_subclass(tmp_path: Path) -> None:
    root = make_repo(tmp_path, row(id="r1", unit='"own:tests/test_u.py#L9"'))
    (root / "tests" / "test_u.py").write_text(UNITTEST_SOURCE)
    path = _matrix(root)

    _repair().fn(path)

    assert _row(root, "r1").levels["unit"] == ("own:tests/test_u.py#FooTests::test_x",)


def test_collection_reads_a_base_where_python_resolves_it() -> None:
    """A function-local `TestCase` that shares a name with a module-level helper
    does not certify the helper; a base cycle terminates and collects nothing."""
    from fr.acceptance.anchors import collected_node_at

    shadow = (
        "import unittest\n"
        "class Helper:\n"
        "    def test_x(self):\n"
        "        pass\n"
        "def f():\n"
        "    class Helper(unittest.TestCase):\n"
        "        pass\n"
    )
    assert collected_node_at(shadow, 4) is None
    cycle = "class A(B):\n    def test_a(self):\n        pass\nclass B(A):\n    pass\n"
    assert collected_node_at(cycle, 3) is None
