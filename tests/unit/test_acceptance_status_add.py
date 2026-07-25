"""Phase 4 — fr acceptance status / add / check --added-since / digest / summary."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.cli import app
from typer.testing import CliRunner

from tests.unit.acceptance_helpers import make_repo, row

runner = CliRunner()

MIXED = (
    row(id="green", status="ci")
    + row(id="old-debt", status="skipped")
    + row(id="new-debt", status="not-implemented", unit="")
)


def _invoke(root: Path, monkeypatch: pytest.MonkeyPatch, *args: str):
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    return runner.invoke(app, ["acceptance", *args])


# ── T1: status ─────────────────────────────────────────────────────────────


def test_status_counts_and_open_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_repo(tmp_path, MIXED)
    result = _invoke(root, monkeypatch, "status")
    assert result.exit_code == 0
    assert "ci: 1" in result.output
    assert "skipped: 1" in result.output
    out = result.output
    assert out.index("old-debt") < out.index("new-debt")  # matrix order = oldest first
    assert "backfill owed" in out or "n" in out  # notes surface


def test_status_brief_caps_to_three(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rows = row(id="green") + "".join(row(id=f"debt-{i}", status="skipped") for i in range(5))
    root = make_repo(tmp_path, rows)
    result = _invoke(root, monkeypatch, "status", "--brief")
    assert result.exit_code == 0
    for i in range(3):
        assert f"debt-{i}" in result.output
    assert "debt-3" not in result.output
    assert "debt-4" not in result.output
    assert "+2 more" in result.output


def test_status_zero_debt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_repo(tmp_path, row(id="green"))
    result = _invoke(root, monkeypatch, "status")
    assert result.exit_code == 0
    assert "no acceptance debt" in result.output


def test_summary_is_actions_friendly_markdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_repo(tmp_path, MIXED)
    result = _invoke(root, monkeypatch, "summary")
    assert result.exit_code == 0
    assert "## Acceptance matrix" in result.output
    assert "| skipped | 1 |" in result.output
    assert "<details><summary><code>old-debt</code> [skipped]</summary>" in result.output
    assert "<!-- fr-acceptance-digest -->" not in result.output
    assert "Full HTML report remains attached" in result.output


def test_summary_zero_debt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_repo(tmp_path, row(id="green"))
    result = _invoke(root, monkeypatch, "summary")
    assert result.exit_code == 0
    assert "No open acceptance debt." in result.output
    assert "<details>" not in result.output


# ── T2: add ────────────────────────────────────────────────────────────────

ADD_ARGS = [
    "add",
    "--id",
    "new-row",
    "--capability",
    "Caps",
    "--acceptance",
    "Operator can add rows",
    "--origin",
    "own:docs/superpowers/specs/s.md",
    "--level",
    "unit=own:tests/test_a.py",
    "--status",
    "not-implemented",
    "--notes",
    "born in a test",
]


def test_add_appends_and_preserves_header(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_repo(tmp_path, row())
    matrix_path = root / "docs" / "acceptance" / "matrix.yaml"
    before = matrix_path.read_text()
    header = before.split("rows:")[0]
    result = _invoke(root, monkeypatch, *ADD_ARGS)
    assert result.exit_code == 0, result.output
    after = matrix_path.read_text()
    assert after.startswith(header + "rows:")
    assert after.startswith(before)  # pure append
    assert "new-row" in after
    check = _invoke(root, monkeypatch, "check")
    assert check.exit_code == 0, check.output


def test_add_regenerates_report_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`fr acceptance add` creates/updates the whole committed set in the same
    tree, and a follow-up `report --check` passes (the CLI mutation path stays
    in sync)."""
    root = make_repo(tmp_path, row())
    d = root / "docs" / "acceptance"
    files = [d / "report_local.html", d / "report_linked.html", d / "report_linked.md"]
    assert not any(f.exists() for f in files)
    result = _invoke(root, monkeypatch, *ADD_ARGS)
    assert result.exit_code == 0, result.output
    assert all(f.exists() for f in files), "add must generate the report set"
    assert "new-row" in (d / "report_local.html").read_text()
    assert "blob/main/" in (d / "report_linked.md").read_text()
    check = _invoke(root, monkeypatch, "report", "--check")
    assert check.exit_code == 0, check.output


def test_add_render_failure_keeps_row(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A report-render failure warns but never rolls back the appended row."""
    import fr.acceptance.report as report_mod

    def boom(*_a: object, **_k: object) -> str:
        raise RuntimeError("render exploded")

    monkeypatch.setattr(report_mod, "render_deterministic", boom)
    root = make_repo(tmp_path, row())
    matrix_path = root / "docs" / "acceptance" / "matrix.yaml"
    result = _invoke(root, monkeypatch, *ADD_ARGS)
    assert result.exit_code == 0, result.output
    assert "new-row" in matrix_path.read_text()  # row survived
    assert "report" in result.output.lower()  # warned to run report


def test_add_rejects_bad_status_file_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_repo(tmp_path, row())
    matrix_path = root / "docs" / "acceptance" / "matrix.yaml"
    before = matrix_path.read_text()
    args = [a if a != "not-implemented" else "sheduled" for a in ADD_ARGS]
    result = _invoke(root, monkeypatch, *args)
    assert result.exit_code == 2
    assert matrix_path.read_text() == before


def test_add_rejects_bad_level_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_repo(tmp_path, row())
    args = [a if not a.startswith("unit=") else "unti=own:tests/test_a.py" for a in ADD_ARGS]
    result = _invoke(root, monkeypatch, *args)
    assert result.exit_code == 2
    assert "unti" in result.output


def test_add_rejects_duplicate_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_repo(tmp_path, row(id="new-row"))
    result = _invoke(root, monkeypatch, *ADD_ARGS)
    assert result.exit_code == 2
    assert "new-row" in result.output


def test_add_accumulates_levels_and_origins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_repo(tmp_path, row())
    extra = [
        "--origin",
        "own:tests/test_a.py",
        "--level",
        "api=own:tests/test_a.py",
    ]
    result = _invoke(root, monkeypatch, *ADD_ARGS, *extra)
    assert result.exit_code == 0, result.output
    from fr.acceptance.model import load_matrix

    m = load_matrix(root / "docs" / "acceptance" / "matrix.yaml")
    new = next(r for r in m.rows if r.id == "new-row")
    assert len(new.origin) == 2
    assert new.levels["unit"] and new.levels["api"]


@pytest.mark.parametrize(
    "flag,value",
    [
        ("--origin", "no-colon-ref"),
        ("--level", "unit=own/slash-in-repo:tests/x.py"),
        ("--level", "unit=own:"),
    ],
)
def test_add_rejects_malformed_refs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flag: str, value: str
) -> None:
    """Dog-food finding: a shell-mangled ref (zsh `$VAR:t` modifier) sailed
    through `add` and only failed at the next `check`. Ref grammar is
    validated at add time, before the file is touched."""
    root = make_repo(tmp_path, row())
    matrix_path = root / "docs" / "acceptance" / "matrix.yaml"
    before = matrix_path.read_text()
    result = _invoke(root, monkeypatch, *ADD_ARGS, flag, value)
    assert result.exit_code == 2, result.output
    assert matrix_path.read_text() == before


# ── T3: --added-since ──────────────────────────────────────────────────────


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _git_repo(tmp_path: Path, rows_text: str) -> Path:
    root = make_repo(tmp_path, rows_text, git=False)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")
    return root


def test_added_since_lists_new_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _git_repo(tmp_path, row(id="a"))
    matrix_path = root / "docs" / "acceptance" / "matrix.yaml"
    matrix_path.write_text(matrix_path.read_text() + row(id="b") + row(id="c"))
    result = _invoke(root, monkeypatch, "check", "--added-since", "HEAD")
    assert result.exit_code == 0, result.output
    assert "added since HEAD" in result.output
    assert "b" in result.output and "c" in result.output
    assert "\na —" not in result.output


def test_added_since_base_without_matrix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_repo(tmp_path, "", git=False)
    matrix_path = root / "docs" / "acceptance" / "matrix.yaml"
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    matrix_path.unlink()
    (root / "docs" / "superpowers" / "specs" / "s.md").unlink()
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "no matrix", "--allow-empty")
    (root / "docs" / "superpowers" / "specs" / "s.md").write_text("# s\n\n## Test Plan\n\n1. x\n")
    matrix_path.write_text("org: derio-net\nrepo: own\nrows:\n" + row(id="a"))
    result = _invoke(root, monkeypatch, "check", "--added-since", "HEAD")
    assert result.exit_code == 0, result.output
    assert "a" in result.output.split("added since HEAD")[1]


def test_added_since_bad_ref(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _git_repo(tmp_path, row(id="a"))
    result = _invoke(root, monkeypatch, "check", "--added-since", "no-such-ref")
    assert result.exit_code == 1
    assert "no-such-ref" in result.output


# ── T4: digest ─────────────────────────────────────────────────────────────


def test_digest_table_and_marker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_repo(tmp_path, MIXED)
    result = _invoke(root, monkeypatch, "digest")
    assert result.exit_code == 0
    assert "## Acceptance debt" in result.output
    assert "| old-debt | skipped |" in result.output
    assert "| new-debt | not-implemented |" in result.output
    assert "green" not in result.output.split("## Acceptance debt")[1]
    assert "<!-- fr-acceptance-digest -->" in result.output
    out = result.output
    assert out.index("old-debt") < out.index("new-debt")


def test_digest_zero_debt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_repo(tmp_path, row(id="green"))
    result = _invoke(root, monkeypatch, "digest")
    assert result.exit_code == 0
    assert "No open acceptance debt." in result.output
    assert "<!-- fr-acceptance-digest -->" in result.output
