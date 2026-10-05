"""`fr triage render`'s snapshot handling (wave-driver R16, R17; review ri-2, ri-4, ri-5).

Every state directory and every git repo is under tmp_path; the repo under test is
never read or written.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml
from fr.cli import app
from fr.triage.snapshot import KEEP, store_snapshot, take_snapshot
from typer.testing import CliRunner

from tests.unit.triage_board_fixtures import busy, issue

SCOPE = "example-org/widgets"


def _state(tmp_path: Path) -> Path:
    state = tmp_path / "state"
    state.mkdir()
    f, jd = busy()
    (state / "facts.json").write_text(json.dumps(f.to_json()), encoding="utf-8")
    (state / "judgements.yaml").write_text(
        yaml.safe_dump(jd.model_dump(mode="json", by_alias=True, exclude_none=True)),
        encoding="utf-8",
    )
    return state


def _render(state: Path, *extra: str, repo: str = SCOPE) -> str:
    result = CliRunner().invoke(
        app, ["triage", "render", "--repo", repo, "--dir", str(state), *extra]
    )
    assert result.exit_code == 0, result.output
    return result.output


def _snaps(state: Path) -> list[Path]:
    return sorted((state / "snapshots").glob("*.json"))


def _matrix(path: Path, rows: dict[str, str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "schema_version": 3,
        "org": "example-org",
        "repo": "widgets",
        "rows": [
            {
                "id": rid,
                "capability": "cap",
                "acceptance": f"row {rid}",
                "origin": ["widgets:spec.md"],
                "levels": {},
                "status": status,
            }
            for rid, status in rows.items()
        ],
    }
    path.write_text(yaml.safe_dump(doc), encoding="utf-8")
    return path


def _checkout(tmp_path: Path, origin: str, rows: dict[str, str]) -> Path:
    repo = tmp_path / "checkout"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "remote", "add", "origin", origin], cwd=repo, check=True)
    _matrix(repo / "docs" / "acceptance" / "matrix.yaml", rows)
    return repo


def _stored_acceptance(state: Path) -> dict[str, str] | None:
    doc = json.loads(_snaps(state)[-1].read_text(encoding="utf-8"))
    return None if doc["acceptance"] is None else doc["acceptance"]["rows"]


# ----------------------------------------------------------------- ri-2: which matrix


def test_a_checkout_of_the_triaged_repo_supplies_its_matrix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _checkout(tmp_path, f"https://github.com/{SCOPE}.git", {"row-a": "ci"})
    monkeypatch.chdir(repo / "docs")  # a subdirectory: the toplevel is what counts
    state = _state(tmp_path)
    _render(state)
    assert _stored_acceptance(state) == {"row-a": "ci"}


def test_a_checkout_of_another_repo_is_not_this_scopes_matrix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _checkout(tmp_path, "https://github.com/other-org/other.git", {"row-a": "ci"})
    monkeypatch.chdir(repo)
    state = _state(tmp_path)
    _render(state)
    assert _stored_acceptance(state) is None
    (state / "judgements.yaml").write_text(
        (state / "judgements.yaml").read_text(encoding="utf-8") + "\n", encoding="utf-8"
    )
    facts_doc = json.loads((state / "facts.json").read_text(encoding="utf-8"))
    facts_doc["issues"].append(issue(40))
    (state / "facts.json").write_text(json.dumps(facts_doc), encoding="utf-8")
    _render(state)
    page = (state / "triage.html").read_text(encoding="utf-8")
    assert "acceptance rows: not tracked for this scope" in page
    assert "Acceptance rows moved" not in page


def test_no_matrix_says_so_instead_of_dropping_the_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bare = tmp_path / "bare"
    bare.mkdir()
    monkeypatch.chdir(bare)
    state = _state(tmp_path)
    _render(state)
    assert _stored_acceptance(state) is None
    _render(state)
    page = (state / "triage.html").read_text(encoding="utf-8")
    assert "acceptance rows: not tracked for this scope" in page


def test_an_explicit_matrix_is_read_whatever_the_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bare = tmp_path / "bare"
    bare.mkdir()
    monkeypatch.chdir(bare)
    state = _state(tmp_path)
    mx = _matrix(tmp_path / "elsewhere" / "matrix.yaml", {"row-z": "skipped"})
    _render(state, "--matrix", str(mx), repo="other-org/other")
    assert _stored_acceptance(state) == {"row-z": "skipped"}


# ------------------------------------------------------- ri-4: store only what was shown


def test_a_render_that_raises_leaves_no_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fr.commands.triage_cmd as cmd

    def boom(*_a: object, **_k: object) -> str:
        raise RuntimeError("render failed")

    monkeypatch.setattr(cmd, "render", boom)
    state = _state(tmp_path)
    result = CliRunner().invoke(app, ["triage", "render", "--repo", SCOPE, "--dir", str(state)])
    assert result.exit_code != 0
    assert _snaps(state) == [] and not (state / "triage.html").exists()


def test_a_failed_prune_is_a_warning_not_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = _state(tmp_path)
    f, jd = busy()
    snap = take_snapshot(f, jd, acceptance=None)
    from datetime import UTC, datetime, timedelta

    t0 = datetime(2026, 10, 2, tzinfo=UTC)
    for n in range(KEEP + 2):
        store_snapshot(state, snap, t0 + timedelta(minutes=n))
    real_unlink = Path.unlink

    def deny(self: Path, *a: object, **k: object) -> None:
        if self.suffix == ".json" and self.parent.name == "snapshots":
            raise PermissionError("denied")
        real_unlink(self, *a, **k)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "unlink", deny)
    warnings: list[str] = []
    path = store_snapshot(state, snap, t0 + timedelta(days=1), warn=warnings.append)
    assert path.is_file() and warnings and "cannot prune" in warnings[0]
    # and through the command: exit 0, the warning is a line of output
    facts_doc = json.loads((state / "facts.json").read_text(encoding="utf-8"))
    facts_doc["issues"].append(issue(41))
    (state / "facts.json").write_text(json.dumps(facts_doc), encoding="utf-8")
    out = _render(state)
    assert "warning" in out and "cannot prune" in out
    assert (state / "triage.html").is_file()


# ---------------------------------------------- ri-5: a re-render keeps "Since last report"


def test_two_identical_renders_store_one_snapshot_and_keep_the_earlier_diff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bare = tmp_path / "bare"
    bare.mkdir()
    monkeypatch.chdir(bare)
    state = _state(tmp_path)
    _render(state)
    assert len(_snaps(state)) == 1
    facts_doc = json.loads((state / "facts.json").read_text(encoding="utf-8"))
    facts_doc["issues"].append(issue(40))
    (state / "facts.json").write_text(json.dumps(facts_doc), encoding="utf-8")
    _render(state)
    assert len(_snaps(state)) == 2
    _render(state)
    _render(state)
    assert len(_snaps(state)) == 2, "an identical board is not stored again"
    page = (state / "triage.html").read_text(encoding="utf-8")
    assert "<td>widgets#40</td>" in page, "the diff is still against the last different snapshot"
    assert "Nothing changed" not in page


def test_re_rendering_the_only_snapshot_says_nothing_changed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bare = tmp_path / "bare"
    bare.mkdir()
    monkeypatch.chdir(bare)
    state = _state(tmp_path)
    _render(state)
    _render(state)
    assert len(_snaps(state)) == 1
    assert "Nothing changed" in (state / "triage.html").read_text(encoding="utf-8")
