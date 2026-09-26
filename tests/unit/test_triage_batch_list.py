"""`fr triage batch list` over judgements.yaml schema 1 and 2 (spec §3.A).

Phase 1 of the triage-batches plan: the loader accepts schema 1 (zero
batches) and schema 2 (a `batches:` list), and refuses anything newer with
exit 2 naming the schema. Every state directory is under tmp_path.
"""

from __future__ import annotations

from pathlib import Path

from fr.cli import app
from typer.testing import CliRunner

_JUDGED = """\
tiers:
  - {n: 1, title: Now}
issues:
  super-fr#577: {tier: 1}
  super-fr#575: {tier: 1}
"""


def _list(tmp_path: Path, judgements: str | None) -> tuple[int, str]:
    if judgements is not None:
        (tmp_path / "judgements.yaml").write_text(judgements, encoding="utf-8")
    result = CliRunner().invoke(
        app,
        ["triage", "batch", "list", "--repo", "derio-net/super-fr", "--dir", str(tmp_path)],
    )
    return result.exit_code, result.output


def test_schema_1_lists_no_batches(tmp_path: Path) -> None:
    code, out = _list(tmp_path, "schema: 1\n" + _JUDGED)
    assert code == 0, out
    assert "no batches" in out


def test_missing_judgements_lists_no_batches(tmp_path: Path) -> None:
    code, out = _list(tmp_path, None)
    assert code == 0, out
    assert "no batches" in out


def test_schema_2_lists_each_batch_with_its_member_count(tmp_path: Path) -> None:
    code, out = _list(
        tmp_path,
        "schema: 2\n"
        + _JUDGED
        + "batches:\n"
        + "  - id: lifecycle\n"
        + "    title: Separate container lifecycle from worktree lifecycle\n"
        + '    ids: ["super-fr#577", "super-fr#575"]\n',
    )
    assert code == 0, out
    assert "no batches" not in out
    line = next(ln for ln in out.splitlines() if ln.split()[:1] == ["lifecycle"])
    assert "2 issues" in line


def test_schema_3_is_refused_naming_the_schema(tmp_path: Path) -> None:
    code, out = _list(tmp_path, "schema: 3\n" + _JUDGED)
    assert code == 2, out
    assert "unsupported schema 3" in " ".join(out.split())


def test_schema_1_carrying_batches_is_refused(tmp_path: Path) -> None:
    """Batches exist only under schema 2 (spec §3.A: schema 1 loads as zero
    batches). A schema-1 stamp over a `batches:` list is a writer that forgot
    the stamp, and an older reader would mis-read the file, so refuse it."""
    code, out = _list(
        tmp_path,
        "schema: 1\n"
        + _JUDGED
        + "batches:\n"
        + "  - id: lifecycle\n"
        + "    title: t\n"
        + '    ids: ["super-fr#577"]\n',
    )
    assert code == 2, out
    assert "schema 2" in out
