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


# ── T2b: lifecycle mutations ───────────────────────────────────────────────


def test_set_status_preserves_header_and_appends_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    header = "# hand-written header\norg: derio-net\nrepo: own\nrows:\n"
    root = make_repo(tmp_path, row(id="promote", status="skipped"), header=header)
    matrix_path = root / "docs" / "acceptance" / "matrix.yaml"
    before = matrix_path.read_text()
    result = _invoke(
        root,
        monkeypatch,
        "set-status",
        "promote",
        "--status",
        "ci",
        "--note",
        "unit evidence landed",
    )
    assert result.exit_code == 0, result.output
    after = matrix_path.read_text()
    assert after.startswith("# hand-written header\norg: derio-net\nrepo: own\nrows:\n")
    assert 'status: "ci"' in after
    from fr.acceptance.model import load_matrix

    assert load_matrix(matrix_path).rows[0].notes == "n\nunit evidence landed"
    assert after != before


def test_acceptance_mutations_regenerate_report_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_repo(tmp_path, row(id="r1", status="skipped"))
    d = root / "docs" / "acceptance"
    status = _invoke(root, monkeypatch, "set-status", "r1", "--status", "ci")
    assert status.exit_code == 0, status.output
    level = _invoke(root, monkeypatch, "add-level", "r1", "--level", "api=own:tests/test_a.py")
    assert level.exit_code == 0, level.output
    names = ("report_local.html", "report_linked.html", "report_linked.md")
    assert all((d / name).exists() for name in names)
    assert _invoke(root, monkeypatch, "report", "--check").exit_code == 0


def test_add_level_deduplicates_retries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_repo(tmp_path, row(id="r1"))
    args = ("add-level", "r1", "--level", "api=own:tests/test_a.py")
    assert _invoke(root, monkeypatch, *args).exit_code == 0
    assert _invoke(root, monkeypatch, *args).exit_code == 0
    from fr.acceptance.model import load_matrix

    matrix = load_matrix(root / "docs" / "acceptance" / "matrix.yaml")
    assert matrix.rows[0].levels["api"] == ("own:tests/test_a.py",)


@pytest.mark.parametrize(
    "evidence",
    (
        '      unit: ["own:tests/test_a.py"]  # keep flow comment\n',
        (
            "      unit:  # keep block comment\n"
            '        - "own:tests/test_a.py"  # keep evidence comment\n'
        ),
    ),
)
def test_add_level_extends_existing_evidence_sequence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, evidence: str
) -> None:
    rows = f"""\
  - id: r1
    capability: "Cap"
    acceptance: "Operator can do X"
    origin: ["own:docs/superpowers/specs/s.md"]
    levels:
{evidence}    status: ci
    notes: "n"
"""
    root = make_repo(tmp_path, rows)
    matrix_path = root / "docs" / "acceptance" / "matrix.yaml"
    result = _invoke(root, monkeypatch, "add-level", "r1", "--level", "unit=own:tests/test_b.py")
    assert result.exit_code == 0, result.output
    after = matrix_path.read_text()
    assert "# keep" in after
    from fr.acceptance.model import load_matrix

    assert load_matrix(matrix_path).rows[0].levels["unit"] == (
        "own:tests/test_a.py",
        "own:tests/test_b.py",
    )
    assert _invoke(root, monkeypatch, "report", "--check").exit_code == 0


@pytest.mark.parametrize(
    "levels",
    (
        '    levels: {unit: ["own:tests/test_a.py"]}  # keep flow mapping comment\n',
        "    levels:\n      unit: []  # keep empty sequence comment\n",
    ),
)
def test_add_level_supports_flow_mapping_and_empty_sequence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, levels: str
) -> None:
    rows = f"""\
  - id: r1
    capability: "Cap"
    acceptance: "Operator can do X"
    origin: ["own:docs/superpowers/specs/s.md"]
{levels}    status: ci
    notes: "n"
"""
    root = make_repo(tmp_path, rows)
    matrix_path = root / "docs" / "acceptance" / "matrix.yaml"
    result = _invoke(root, monkeypatch, "add-level", "r1", "--level", "unit=own:tests/test_b.py")
    assert result.exit_code == 0, result.output
    assert "# keep" in matrix_path.read_text()
    from fr.acceptance.model import load_matrix

    assert (
        load_matrix(matrix_path).rows[0].levels["unit"]
        == (
            "own:tests/test_a.py",
            "own:tests/test_b.py",
        )
        if "test_a" in levels
        else ("own:tests/test_b.py",)
    )
    assert _invoke(root, monkeypatch, "report", "--check").exit_code == 0


@pytest.mark.parametrize(
    ("prefix", "duplicate", "args"),
    (
        ("", "    status: skipped\n    status: ci\n", ("set-status", "r1", "--status", "ci")),
        (
            "",
            (
                "    levels:\n"
                '      unit: ["own:tests/test_a.py"]\n'
                '      unit: ["own:tests/test_b.py"]\n'
            ),
            ("add-level", "r1", "--level", "api=own:tests/test_b.py"),
        ),
        ("repo: duplicate\n", "    status: ci\n", ("set-status", "r1", "--status", "ci")),
    ),
)
def test_lifecycle_mutations_reject_duplicate_yaml_keys_without_changing_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    prefix: str,
    duplicate: str,
    args: tuple[str, ...],
) -> None:
    rows = f"""\
  - id: r1
    capability: "Cap"
    acceptance: "Operator can do X"
    origin: ["own:docs/superpowers/specs/s.md"]
{duplicate}    notes: "n"
"""
    root = make_repo(tmp_path, rows, header=f"org: derio-net\n{prefix}repo: own\nrows:\n")
    matrix_path = root / "docs" / "acceptance" / "matrix.yaml"
    before = matrix_path.read_text()
    result = _invoke(root, monkeypatch, *args)
    assert result.exit_code == 1
    assert "duplicate key" in result.output
    assert matrix_path.read_text() == before


def test_lifecycle_mutations_preserve_row_comments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows = """\
  # before row
  - id: r1  # identity
    capability: "Cap"  # grouping
    acceptance: "Operator can do X"  # outcome
    origin: ["own:docs/superpowers/specs/s.md"]  # design
    levels:  # evidence
      unit: ["own:tests/test_a.py"]  # existing test
    # status rationale
    status: skipped  # awaiting coverage
    notes: "n"  # prior evidence
  # after row
"""
    root = make_repo(tmp_path, rows)
    matrix_path = root / "docs" / "acceptance" / "matrix.yaml"
    status = _invoke(root, monkeypatch, "set-status", "r1", "--status", "ci", "--note", "landed")
    assert status.exit_code == 0
    level = _invoke(root, monkeypatch, "add-level", "r1", "--level", "api=own:tests/test_a.py")
    assert level.exit_code == 0
    after = matrix_path.read_text()
    for comment in (
        "# before row",
        "# identity",
        "# grouping",
        "# outcome",
        "# design",
        "# evidence",
        "# existing test",
        "# status rationale",
        "# awaiting coverage",
        "# prior evidence",
        "# after row",
    ):
        assert comment in after
    from fr.acceptance.model import load_matrix

    updated = load_matrix(matrix_path).rows[0]
    assert updated.status == "ci"
    assert updated.notes == "n\nlanded"
    assert updated.levels["api"] == ("own:tests/test_a.py",)


def test_add_level_rejects_aliased_levels_without_changing_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows = """\
  - id: source
    capability: "Cap"
    acceptance: "Operator can do X"
    origin: ["own:docs/superpowers/specs/s.md"]
    levels: &levels
      unit: ["own:tests/test_a.py"]
    status: ci
    notes: "n"
  - id: target
    capability: "Cap"
    acceptance: "Operator can do X"
    origin: ["own:docs/superpowers/specs/s.md"]
    levels: *levels
    status: ci
    notes: "n"
"""
    root = make_repo(tmp_path, rows)
    matrix_path = root / "docs" / "acceptance" / "matrix.yaml"
    before = matrix_path.read_text()
    result = _invoke(root, monkeypatch, "add-level", "target", "--level", "api=own:tests/test_a.py")
    assert result.exit_code == 2
    assert "alias" in result.output.lower()
    assert matrix_path.read_text() == before


@pytest.mark.parametrize("levels", ("", "    levels: {}\n"))
def test_add_level_materializes_omitted_or_empty_levels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, levels: str
) -> None:
    rows = f"""\
  - id: r1
    capability: "Cap"
    acceptance: "Operator can do X"
    origin: ["own:docs/superpowers/specs/s.md"]
{levels}    # keep this neighboring comment
    status: ci
    notes: "n"
"""
    root = make_repo(tmp_path, rows)
    matrix_path = root / "docs" / "acceptance" / "matrix.yaml"
    result = _invoke(root, monkeypatch, "add-level", "r1", "--level", "api=own:tests/test_a.py")
    assert result.exit_code == 0, result.output
    assert "# keep this neighboring comment" in matrix_path.read_text()
    from fr.acceptance.model import load_matrix

    assert load_matrix(matrix_path).rows[0].levels["api"] == ("own:tests/test_a.py",)


def test_set_status_materializes_omitted_notes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows = """\
  - id: r1
    capability: "Cap"
    acceptance: "Operator can do X"
    origin: ["own:docs/superpowers/specs/s.md"]
    # keep this neighboring comment
    status: skipped
"""
    root = make_repo(tmp_path, rows)
    matrix_path = root / "docs" / "acceptance" / "matrix.yaml"
    result = _invoke(root, monkeypatch, "set-status", "r1", "--status", "ci", "--note", "landed")
    assert result.exit_code == 0, result.output
    assert "# keep this neighboring comment" in matrix_path.read_text()
    from fr.acceptance.model import load_matrix

    updated = load_matrix(matrix_path).rows[0]
    assert updated.status == "ci"
    assert updated.notes == "landed"


def test_set_status_render_failure_keeps_update(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fr.acceptance.report as report_mod

    def boom(*_a: object, **_k: object) -> str:
        raise RuntimeError("render exploded")

    monkeypatch.setattr(report_mod, "render_deterministic", boom)
    root = make_repo(tmp_path, row(id="r1", status="skipped"))
    result = _invoke(root, monkeypatch, "set-status", "r1", "--status", "ci")
    assert result.exit_code == 0, result.output
    assert "report" in result.output.lower()
    from fr.acceptance.model import load_matrix

    assert load_matrix(root / "docs" / "acceptance" / "matrix.yaml").rows[0].status == "ci"


@pytest.mark.parametrize(
    "args",
    [
        ("set-status", "missing", "--status", "ci"),
        ("set-status", "r1", "--status", "not-ci"),
        ("add-level", "missing", "--level", "unit=own:tests/test_a.py"),
        ("add-level", "r1", "--level", "bad=own:tests/test_a.py"),
        ("add-level", "r1", "--level", "unit=bad-ref"),
    ],
)
def test_lifecycle_mutations_reject_invalid_input_without_changing_matrix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, args: tuple[str, ...]
) -> None:
    root = make_repo(tmp_path, row(id="r1"))
    matrix_path = root / "docs" / "acceptance" / "matrix.yaml"
    before = matrix_path.read_text()
    result = _invoke(root, monkeypatch, *args)
    assert result.exit_code == 2, result.output
    assert matrix_path.read_text() == before


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
