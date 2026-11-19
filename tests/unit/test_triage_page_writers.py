"""The page writers the commands and the driver share (spec 2026-11-18-triage-pages-ux §C,
R5, R6). Every state directory is under tmp_path; nothing reaches a forge or the repo."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml
from fr.cli import app
from fr.commands import (
    triage_architecture_cmd,
    triage_cmd,
    triage_history_cmd,
    triage_kanban_cmd,
    triage_origins_cmd,
)
from fr.triage.architecture import Measured
from fr.triage.gitseam import Checkout
from typer.testing import CliRunner

from tests.unit.triage_board_fixtures import busy

REPO = "example-org/widgets"
AT = datetime(2026, 11, 18, 9, 30, tzinfo=UTC)
STAMP = re.compile(r"rendered \d{4}-\d\d-\d\d \d\d:\d\d UTC")


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


def _scope() -> Any:
    return triage_cmd._scope(REPO, None)


def _normal(text: str) -> str:
    return STAMP.sub("rendered <stamp>", text)


def _command(state: Path, *argv: str) -> None:
    result = CliRunner().invoke(app, ["triage", *argv, "--repo", REPO, "--dir", str(state)])
    assert result.exit_code == 0, result.output


def _copy(state: Path, name: str) -> Path:
    other = state.parent / name
    other.mkdir()
    for p in state.iterdir():
        if p.is_file():
            (other / p.name).write_bytes(p.read_bytes())
    return other


def test_write_backlog_writes_both_pages_with_the_moment_passed_in(tmp_path: Path) -> None:
    state = _state(tmp_path)
    cmd = _copy(state, "cmd")
    warned: list[str] = []
    out = triage_cmd.write_backlog(
        _scope(), state, now=AT, warn=warned.append, loader=None, prefix="fr", ci_none=frozenset()
    ).path
    _command(cmd, "backlog")
    assert out == state / "backlog.html"
    assert "rendered 2026-11-18 09:30 UTC" in out.read_text(encoding="utf-8")
    for name in ("backlog.html", "issues.html"):
        assert _normal((state / name).read_text("utf-8")) == _normal(
            (cmd / name).read_text("utf-8")
        )


def test_write_backlog_hands_its_loader_and_ci_none_to_the_session_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = _state(tmp_path)
    seen: dict[str, Any] = {}
    real = triage_kanban_cmd.read_sessions

    def spy(*a: Any, **kw: Any) -> Any:
        seen.update(kw)
        return real(*a, **kw)

    monkeypatch.setattr(triage_kanban_cmd, "read_sessions", spy)
    loader = lambda name: None  # noqa: E731
    triage_cmd.write_backlog(
        _scope(), state, now=AT, warn=lambda m: None, loader=loader, prefix="pfx",
        ci_none=frozenset({REPO}),
    )  # fmt: skip
    assert seen["loader"] is loader and seen["prefix"] == "pfx"


def test_write_history_matches_the_command(tmp_path: Path) -> None:
    state = _state(tmp_path)
    cmd = _copy(state, "cmd")
    out = triage_history_cmd.write_history(_scope(), state, now=AT, warn=lambda m: None).path
    _command(cmd, "history", "render")
    assert "rendered 2026-11-18 09:30 UTC" in out.read_text(encoding="utf-8")
    assert _normal(out.read_text("utf-8")) == _normal((cmd / "history.html").read_text("utf-8"))


def _origins_files(state: Path) -> None:
    from fr.triage.origins import OriginsFacts, write_facts

    write_facts(
        state / "origins-facts.json",
        OriginsFacts(scope=REPO, since="2026-09-01", collected_at=AT.isoformat(), issues=[]),
    )


def test_write_origins_matches_the_command(tmp_path: Path) -> None:
    state = _state(tmp_path)
    _origins_files(state)
    cmd = _copy(state, "cmd")
    out = triage_origins_cmd.write_origins(_scope(), state, now=AT, warn=lambda m: None).path
    _command(cmd, "origins", "render")
    assert "rendered 2026-11-18 09:30 UTC" in out.read_text(encoding="utf-8")
    assert _normal(out.read_text("utf-8")) == _normal((cmd / "origins.html").read_text("utf-8"))


SUBSYSTEMS = {
    "subsystems": [
        {"name": "src", "path": ["src/**"], "then_ref": "HEAD", "themes": ["code"]},
    ]
}


class _CountingMeasure:
    def __init__(self, result: dict[str, Measured]) -> None:
        self.calls = 0
        self.result = result

    def __call__(self, checkout: Any, subsystems: Any, *, now_ref: str) -> dict[str, Measured]:
        self.calls += 1
        return self.result


def test_write_architecture_returns_its_measurement_and_reuses_one_without_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = _state(tmp_path)
    (state / "subsystems.yaml").write_text(yaml.safe_dump(SUBSYSTEMS), encoding="utf-8")
    first = {"src": Measured(then=None, now=None)}
    spy = _CountingMeasure(first)
    monkeypatch.setattr(triage_architecture_cmd, "measure_subsystems", spy)
    nowhere = Checkout(tmp_path / "no-such-clone")  # any git call through it would fail
    written = triage_architecture_cmd.write_architecture(
        _scope(), state, now=AT, warn=lambda m: None, checkout=nowhere, measured=None
    )
    assert spy.calls == 1 and written.measured == first
    again = triage_architecture_cmd.write_architecture(
        _scope(), state, now=AT, warn=lambda m: None, checkout=nowhere, measured=written.measured
    )
    assert spy.calls == 1 and again.measured is written.measured
    assert "rendered 2026-11-18 09:30 UTC" in again.path.read_text(encoding="utf-8")


def test_write_architecture_with_no_clone_renders_with_no_measurement(tmp_path: Path) -> None:
    state = _state(tmp_path)
    (state / "subsystems.yaml").write_text(yaml.safe_dump(SUBSYSTEMS), encoding="utf-8")
    warned: list[str] = []
    written = triage_architecture_cmd.write_architecture(
        _scope(), state, now=AT, warn=warned.append, checkout=tmp_path / "missing", measured=None
    )
    assert written.measured == {} and (state / "architecture.html").is_file()
    assert any("not measured" in w for w in warned)


def test_write_board_takes_the_moment(tmp_path: Path) -> None:
    state = _state(tmp_path)
    out, _ = triage_kanban_cmd.write_board(_scope(), state, scope_args=["--repo", REPO], now=AT)
    assert "rendered 2026-11-18 09:30 UTC" in out.read_text(encoding="utf-8")


def test_a_broken_manifest_raises_for_the_caller_and_the_command_exits_2(tmp_path: Path) -> None:
    from fr.triage.errors import TriageError

    state = _state(tmp_path)
    (state / "history").mkdir()
    (state / "history" / "manifest.yaml").write_text("sections: [[\n", encoding="utf-8")
    with pytest.raises(TriageError):
        triage_history_cmd.write_history(_scope(), state, now=AT, warn=lambda m: None)
    result = CliRunner().invoke(
        app, ["triage", "history", "render", "--repo", REPO, "--dir", str(state)]
    )
    assert result.exit_code == 2


def test_a_legacy_file_that_cannot_be_removed_is_a_warning_not_a_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(target: Path, key: str) -> None:
        raise OSError("read-only file system")

    state = _state(tmp_path)
    for module in (triage_cmd, triage_kanban_cmd):
        monkeypatch.setattr(module, "remove_legacy", refuse)
    for verb in ("backlog", "batches"):
        result = CliRunner().invoke(app, ["triage", verb, "--repo", REPO, "--dir", str(state)])
        assert result.exit_code == 0, result.output
        assert "old file was not removed" in result.output and "read-only" in result.output
    assert (state / "backlog.html").is_file() and (state / "issues.html").is_file()
    assert (state / "batches.html").is_file()
