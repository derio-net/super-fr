"""Writers write fragments (spec 2026-11-04-repo-feature-settings R16, R18, R19).

`fr acceptance add` creates a row in the fragment of the feature that owns it (its
one origin spec, else `--feature`), converting a spec or plan path origin to its
logical form and taking `repo:` from a sibling fragment, else the origin remote,
else `--repo`. `set-status` rewrites a row still pending on this branch in place in
the fragment that holds it (a merged row takes amendments: test_acceptance_amend),
and `fr acceptance init` creates the fragments directory and no report. Every
commit holds only the fragment.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml
from fr.acceptance.fold import clear_fold_cache, load_effective
from fr.cli import app
from typer.testing import CliRunner

from tests.unit.acceptance_helpers import FRAGMENTS_REL, fragment_text

runner = CliRunner()
SLUG = "2026-01-01-widget"
SPEC = f"docs/superpowers/specs/{SLUG}-design.md"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=True
    ).stdout


def _repo(tmp_path: Path, *, remote: bool = True, fragment: str | None = None) -> Path:
    root = tmp_path / "widget"
    (root / "docs" / "superpowers" / "specs").mkdir(parents=True)
    (root / SPEC).write_text("# Widget\n\n## Test Plan\n\n1. x\n")
    (root / "docs" / "superpowers" / "journals" / "debug").mkdir(parents=True)
    (root / "docs/superpowers/journals/debug/2026-01-02-bug.md").write_text("# bug\n")
    (root / "tests").mkdir()
    (root / "tests" / "test_w.py").write_text("def test_w():\n    pass\n")
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / ".github" / "workflows" / "ci.yml").write_text("on: push\n")
    (root / FRAGMENTS_REL).mkdir(parents=True)
    (root / FRAGMENTS_REL / ".gitkeep").write_text("")
    if fragment is not None:
        (root / FRAGMENTS_REL / "other.yaml").write_text(fragment)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    if remote:
        _git(root, "remote", "add", "origin", "https://github.com/acme/widget.git")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "seed")
    _git(root, "checkout", "-q", "-b", "feat/w")
    clear_fold_cache()
    return root


def _invoke(root: Path, monkeypatch: pytest.MonkeyPatch, *args: str):
    monkeypatch.setenv("FR_REPO_ROOT", str(root))
    return runner.invoke(app, ["acceptance", *args])


def _add(root: Path, monkeypatch: pytest.MonkeyPatch, rid: str, *origin: str, extra=()):
    args = ["add", "--id", rid, "--capability", "Widget", "--acceptance", f"{rid} works"]
    for o in origin:
        args += ["--origin", o]
    args += ["--level", "unit=widget:tests/test_w.py#test_w", "--status", "unwired"]
    args += ["--notes", "n", *extra]
    return _invoke(root, monkeypatch, *args)


def _fragment(root: Path, feature: str) -> dict:
    return yaml.safe_load((root / FRAGMENTS_REL / f"{feature}.yaml").read_text())


def _committed(root: Path) -> list[str]:
    return sorted(_git(root, "show", "--name-only", "--format=", "HEAD").split())


def test_add_creates_the_fragment_of_its_origin_spec(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)

    res = _add(root, monkeypatch, "w1", f"spec:{SLUG}#R1")

    assert res.exit_code == 0, res.output
    frag = _fragment(root, SLUG)
    assert frag["feature"] == SLUG
    assert frag["repo"] == "acme/widget"
    assert [r["id"] for r in frag["rows"]] == ["w1"]
    assert _committed(root) == [f"{FRAGMENTS_REL}/{SLUG}.yaml"]


def test_add_extends_the_fragment_and_converts_a_path_origin_to_logical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    assert _add(root, monkeypatch, "w1", f"spec:{SLUG}#R1").exit_code == 0

    res = _add(root, monkeypatch, "w2", f"widget:{SPEC}#R2")

    assert res.exit_code == 0, res.output
    rows = {r["id"]: r for r in _fragment(root, SLUG)["rows"]}
    assert set(rows) == {"w1", "w2"}
    assert rows["w2"]["origin"] == [f"spec:{SLUG}#R2"]
    assert [r.id for r in load_effective(root).rows] == ["w1", "w2"]


def test_a_row_with_no_single_origin_spec_is_refused_unless_feature_names_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    debug = "widget:docs/superpowers/journals/debug/2026-01-02-bug.md"

    refused = _add(root, monkeypatch, "b1", debug)
    assert refused.exit_code == 2
    assert "--feature" in refused.output
    assert not (root / FRAGMENTS_REL / "legacy.yaml").exists()

    res = _add(root, monkeypatch, "b1", debug, extra=("--feature", "legacy"))
    assert res.exit_code == 0, res.output
    assert [r["id"] for r in _fragment(root, "legacy")["rows"]] == ["b1"]


def test_repo_comes_from_a_sibling_fragment_before_the_remote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path, fragment=fragment_text("other", "", repo="acme/renamed"))

    assert _add(root, monkeypatch, "w1", f"spec:{SLUG}#R1").exit_code == 0

    assert _fragment(root, SLUG)["repo"] == "acme/renamed"


def test_with_no_fragment_and_no_remote_add_needs_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path, remote=False)

    refused = _add(root, monkeypatch, "w1", f"spec:{SLUG}#R1")
    assert refused.exit_code == 2
    assert "--repo" in refused.output

    res = _add(root, monkeypatch, "w1", f"spec:{SLUG}#R1", extra=("--repo", "acme/widget"))
    assert res.exit_code == 0, res.output
    assert _fragment(root, SLUG)["repo"] == "acme/widget"


def test_set_status_on_a_pending_row_rewrites_it_in_its_own_fragment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    assert _add(root, monkeypatch, "w1", f"spec:{SLUG}#R1").exit_code == 0

    res = _invoke(
        root, monkeypatch, "set-status", "--id", "w1", "--status", "ci", "--notes", "wired"
    )

    assert res.exit_code == 0, res.output
    (row,) = _fragment(root, SLUG)["rows"]
    assert (row["status"], row["notes"]) == ("ci", "wired")
    assert _committed(root) == [f"{FRAGMENTS_REL}/{SLUG}.yaml"]


def test_a_record_entry_writes_the_fragment_through_the_overlay(tmp_path: Path) -> None:
    from fr.record import apply as engine
    from fr.record.model import AcceptanceItem, StepRecord

    root = _repo(tmp_path)
    item = AcceptanceItem(
        id="w1",
        capability="Widget",
        acceptance="w1 works",
        origin=(f"widget:{SPEC}#R1",),
        status="not-implemented",
        notes="owed",
    )

    outcome = engine.apply_record(
        root,
        None,
        StepRecord(acceptance=(item,)),
        target=engine.RecordTarget(message="chore(fr): acceptance — add w1"),
    )

    assert outcome.committed
    (row,) = _fragment(root, SLUG)["rows"]
    assert row["origin"] == [f"spec:{SLUG}#R1"]
    assert _committed(root) == [f"{FRAGMENTS_REL}/{SLUG}.yaml"]


def test_init_creates_the_fragments_directory_and_no_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "fresh"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "remote", "add", "origin", "https://github.com/acme/fresh.git")

    res = _invoke(root, monkeypatch, "init")

    assert res.exit_code == 0, res.output
    assert (root / FRAGMENTS_REL).is_dir()
    assert not list((root / FRAGMENTS_REL).glob("*.yaml"))
    assert not (root / "docs" / "acceptance" / "matrix.yaml").exists()
    assert not list((root / "docs" / "acceptance").glob("report*"))
    assert (root / ".claude" / "rules" / "acceptance-matrix.md").is_file()
    check = _invoke(root, monkeypatch, "check")
    assert check.exit_code == 0, check.output
