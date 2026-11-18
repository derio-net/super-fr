"""The `acceptance-fragment` `-design` name repair (spec 2026-11-17-batch-acceptance-edits
R13-R16, §F; derio-net/super-fr#1461): a fragment written before #1451 as
`<slug>-design.yaml` (`feature: <slug>-design`) is renamed to `<slug>.yaml`, or merged
into an existing one, without changing the effective matrix."""

from __future__ import annotations

import subprocess
from pathlib import Path

import fr.artifacts  # noqa: F401  (registration rides on the package import)
import pytest
import yaml
from fr.acceptance.fold import fold_texts
from fr.artifacts.commit import commit_migration, uncommitted_veto
from fr.artifacts.runner import MIGRATIONS, run_migrations

FEATURES = Path("docs") / "acceptance" / "features"
SLUG = "2026-01-01-alpha"


def _row(rid: str, acceptance: str = "it works", capability: str = "C") -> str:
    return (
        f"  - id: {rid}\n"
        f"    capability: {capability}\n"
        f"    acceptance: {acceptance}\n"
        "    origin: []\n"
        "    levels: {}\n"
        "    status: not-implemented\n"
        "    notes: n\n"
    )


def _amend(rid: str, notes: str, base: int = 0) -> str:
    return (
        f"  - row: {rid}\n"
        "    op: set-status\n"
        f"    base: {base}\n"
        "    status: unwired\n"
        f"    notes: {notes}\n"
        "    why: because\n"
    )


def _frag(feature: str, rows: list[str], amendments: list[str] = ()) -> str:  # type: ignore[assignment]
    text = f"schema_version: 2\nfeature: {feature}\nrepo: o/demo\nrows:\n{''.join(rows)}"
    if amendments:
        text += "amendments:\n" + "".join(amendments)
    return text


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    ).stdout


def _repo(tmp_path: Path, files: dict[str, str]) -> Path:
    root = tmp_path / "demo"
    (root / FEATURES).mkdir(parents=True)
    for name, text in files.items():
        (root / FEATURES / name).write_text(text)
    _git(root, "init", "-q", "-b", "feat/x")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "init")
    return root


def _texts(root: Path) -> dict[str, str]:
    return {
        f"{FEATURES.as_posix()}/{p.name}": p.read_text()
        for p in sorted((root / FEATURES).glob("*.yaml"))
    }


def _matrix(texts: dict[str, str]) -> dict[str, object]:
    eff = fold_texts(texts)
    return {r.id: r for r in eff.matrix.rows}


def _load(root: Path, name: str) -> dict:
    return yaml.safe_load((root / FEATURES / name).read_text())


def test_the_repair_is_registered_on_the_fragment_kind() -> None:
    names = [r.name for r in MIGRATIONS.repairs("acceptance-fragment")]
    assert "design-name" in names


def test_a_lone_design_fragment_is_renamed_and_its_deletion_is_committed(tmp_path: Path) -> None:
    """(a) R13: renamed, `feature:` set to the slug, every entry kept; the migration
    commit holds the new file and the deletion."""
    design = _frag(f"{SLUG}-design", [_row("r1"), _row("r2")], [_amend("r1", "moved")])
    root = _repo(tmp_path, {f"{SLUG}-design.yaml": design})
    before = _matrix(_texts(root))
    report = run_migrations(root, dry_run=False)
    assert report.ok, report.failed
    assert not (root / FEATURES / f"{SLUG}-design.yaml").exists()
    new = (root / FEATURES / f"{SLUG}.yaml").read_text()
    assert new == design.replace(f"feature: {SLUG}-design\n", f"feature: {SLUG}\n")
    assert _matrix(_texts(root)) == before  # (f)
    outcome = commit_migration(root, report)
    assert outcome.committed, outcome.reason
    shown = _git(root, "show", "--no-renames", "--name-status", "--format=", "HEAD").split("\n")
    assert f"D\t{FEATURES.as_posix()}/{SLUG}-design.yaml" in shown
    assert f"A\t{FEATURES.as_posix()}/{SLUG}.yaml" in shown
    assert not _git(root, "status", "--porcelain")
    again = run_migrations(root, dry_run=True)  # idempotent
    assert not again.applied


def test_disjoint_fragments_merge_with_the_slug_files_entries_first(tmp_path: Path) -> None:
    """(b) R14: one fragment, `<slug>.yaml`'s rows and amendments first."""
    root = _repo(
        tmp_path,
        {
            f"{SLUG}.yaml": _frag(SLUG, [_row("a1")], [_amend("a1", "own")]),
            f"{SLUG}-design.yaml": _frag(
                f"{SLUG}-design", [_row("d1")], [_amend("d1", "old"), _amend("a1", "x", 1)]
            ),
        },
    )
    before = _matrix(_texts(root))
    report = run_migrations(root, dry_run=False)
    assert report.ok, report.failed
    assert not (root / FEATURES / f"{SLUG}-design.yaml").exists()
    data = _load(root, f"{SLUG}.yaml")
    assert data["feature"] == SLUG
    assert [r["id"] for r in data["rows"]] == ["a1", "d1"]
    assert [(a["row"], a["notes"]) for a in data["amendments"]] == [
        ("a1", "own"),
        ("d1", "old"),
        ("a1", "x"),
    ]
    assert _matrix(_texts(root)) == before  # (f)


def test_an_entry_identical_in_both_is_kept_once(tmp_path: Path) -> None:
    """(c) R14: the shared row and amendment appear once."""
    root = _repo(
        tmp_path,
        {
            f"{SLUG}.yaml": _frag(SLUG, [_row("a1"), _row("s")], [_amend("s", "same")]),
            f"{SLUG}-design.yaml": _frag(
                f"{SLUG}-design", [_row("s"), _row("d1")], [_amend("s", "same")]
            ),
        },
    )
    before = _texts(root)
    report = run_migrations(root, dry_run=False)
    assert report.ok, report.failed
    data = _load(root, f"{SLUG}.yaml")
    assert [r["id"] for r in data["rows"]] == ["a1", "s", "d1"]
    assert [(a["row"], a["notes"]) for a in data["amendments"]] == [("s", "same")]
    assert not (root / FEATURES / f"{SLUG}-design.yaml").exists()
    # The old set folds only with each shared entry once (a row defined twice is
    # unfoldable); the fold after equals that reading of it.
    once = dict(before)
    once[f"{FEATURES.as_posix()}/{SLUG}-design.yaml"] = _frag(f"{SLUG}-design", [_row("d1")])
    assert _matrix(_texts(root)) == _matrix(once)


def test_an_id_held_differently_fails_the_artifact_and_moves_no_byte(tmp_path: Path) -> None:
    """(d) R14: both files byte-identical, the failure names the id."""
    files = {
        f"{SLUG}.yaml": _frag(SLUG, [_row("s", "one thing")]),
        f"{SLUG}-design.yaml": _frag(f"{SLUG}-design", [_row("s", "another thing")]),
    }
    root = _repo(tmp_path, files)
    report = run_migrations(root, dry_run=False)
    assert not report.ok
    (failure,) = [f for f in report.failed if f.path.name == f"{SLUG}-design.yaml"]
    assert "row s" in failure.error
    for name, text in files.items():
        assert (root / FEATURES / name).read_text() == text


def test_uncommitted_edits_in_the_slug_file_hold_the_repair_back(tmp_path: Path) -> None:
    """(e) R16: `<slug>.yaml` is a companion, so the veto holds the -design file."""
    files = {
        f"{SLUG}.yaml": _frag(SLUG, [_row("a1")]),
        f"{SLUG}-design.yaml": _frag(f"{SLUG}-design", [_row("d1")]),
    }
    root = _repo(tmp_path, files)
    edited = files[f"{SLUG}.yaml"] + _row("mid-edit")
    (root / FEATURES / f"{SLUG}.yaml").write_text(edited)
    report = run_migrations(root, dry_run=False, veto=uncommitted_veto(root))
    assert not report.ok
    assert any(f"{SLUG}.yaml" in f.error for f in report.failed)
    assert (root / FEATURES / f"{SLUG}.yaml").read_text() == edited
    assert (root / FEATURES / f"{SLUG}-design.yaml").read_text() == files[f"{SLUG}-design.yaml"]


@pytest.mark.parametrize(
    "name",
    ["2026-01-01-alpha-design.yaml", "legacy.yaml", "2026-01-01-beta-design.yaml"],
)
def test_only_a_design_file_whose_feature_is_its_stem_applies(tmp_path: Path, name: str) -> None:
    """The predicate: name ends `-design.yaml` AND `feature:` equals the stem."""
    (repair,) = [r for r in MIGRATIONS.repairs("acceptance-fragment") if r.name == "design-name"]
    path = tmp_path / name
    path.write_text(_frag(f"{SLUG}-design", [_row("r")]))
    assert repair.applies(path) is (name == f"{SLUG}-design.yaml")


def test_a_non_utf8_sibling_fails_the_repair_naming_that_sibling(tmp_path: Path) -> None:
    """l-errors-r1: the sibling read at the fold goes through `read_utf8`, so the
    failure names the file that is not UTF-8, never the -design file or the codec."""
    design = _frag(f"{SLUG}-design", [_row("r1")])
    root = _repo(tmp_path, {f"{SLUG}-design.yaml": design})
    bad = root / FEATURES / "2026-01-02-beta.yaml"
    bad.write_bytes(_frag("2026-01-02-beta", [_row("b1")]).encode() + b"# caf\xe9\n")
    report = run_migrations(root, dry_run=False)
    (failure,) = [f for f in report.failed if f.path.name == f"{SLUG}-design.yaml"]
    assert f"{bad} is not UTF-8 text" in failure.error
    assert "codec" not in failure.error
    assert (root / FEATURES / f"{SLUG}-design.yaml").read_text() == design


def test_a_non_utf8_design_file_fails_naming_itself(tmp_path: Path) -> None:
    """l-errors-r1: `applies` does not mask a non-UTF-8 -design file as 'not mine'."""
    path = tmp_path / f"{SLUG}-design.yaml"
    path.write_bytes(_frag(f"{SLUG}-design", [_row("r1")]).encode() + b"# caf\xe9\n")
    (repair,) = [r for r in MIGRATIONS.repairs("acceptance-fragment") if r.name == "design-name"]
    with pytest.raises(UnicodeDecodeError) as info:
        repair.applies(path)
    assert str(info.value).startswith(f"{path} is not UTF-8 text")


def test_a_rename_that_would_change_the_fold_names_the_row_and_moves_no_byte(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """l-tests-r4 / l-errors-r4: the R15 refusal names the rows whose folded row
    differs, and both files stay byte-identical."""
    import fr.artifacts.fragment_design_name as mod

    files = {
        f"{SLUG}.yaml": _frag(SLUG, [_row("a1")]),
        f"{SLUG}-design.yaml": _frag(f"{SLUG}-design", [_row("d1"), _row("d2")]),
    }
    root = _repo(tmp_path, files)
    real = mod._matrix
    design_key = f"features/{SLUG}-design.yaml"

    def skewed(texts: dict[str, str]) -> tuple[dict[str, object], dict[str, object]]:
        rows, retired = real(texts)
        if design_key in texts:
            return rows, retired
        rows = dict(rows)
        rows["d2"] = rows["d2"].model_copy(update={"notes": "tampered"})  # type: ignore[attr-defined]
        rows.pop("a1")
        return rows, {**retired, "gone": object()}

    monkeypatch.setattr(mod, "_matrix", skewed)
    report = run_migrations(root, dry_run=False)
    (failure,) = [f for f in report.failed if f.path.name == f"{SLUG}-design.yaml"]
    assert "would change the effective matrix" in failure.error
    assert "rows a1, d2" in failure.error
    assert "retired gone" in failure.error
    assert "d1" not in failure.error
    for name, text in files.items():
        assert (root / FEATURES / name).read_text() == text
