"""`fr-herdr restart-idle` — the console script over `fr_herdr.restart` (spec 2026-10-06 §A)."""

from __future__ import annotations

import shutil

import pytest
from fr_herdr import cli, restart


@pytest.fixture
def inside_herdr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/local/bin/herdr")
    monkeypatch.setenv("HERDR_ENV", "1")


def _report(*lines: restart.PaneLine, dry_run: bool = True) -> restart.RestartReport:
    return restart.RestartReport(list(lines), dry_run)


def _fake(monkeypatch: pytest.MonkeyPatch, report: restart.RestartReport) -> list[dict]:
    seen: list[dict] = []

    def fake(*, yes: bool, exclude: tuple[str, ...] = ()) -> restart.RestartReport:
        seen.append({"yes": yes, "exclude": tuple(exclude)})
        return report

    monkeypatch.setattr(restart, "restart_idle", fake)
    return seen


def test_prints_one_line_per_pane_then_a_summary(
    inside_herdr: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen = _fake(
        monkeypatch,
        _report(
            restart.PaneLine("w2:p1", "alpha", "ok", "would restart"),
            restart.PaneLine("w2:p2", "beta", "skip", "draft"),
        ),
    )
    assert cli.main(["restart-idle"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "ok  w2:p1  alpha"
    assert out[1] == "skip draft  w2:p2  beta"
    assert out[-1] == "1 would restart, 1 skipped, 0 failed"
    assert any("--yes" in line for line in out)  # a dry run says how to execute
    assert seen == [{"yes": False, "exclude": ()}]


def test_a_failed_pane_exits_one_and_prints_the_resume_command(
    inside_herdr: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _fake(
        monkeypatch,
        _report(
            restart.PaneLine("w2:p1", "alpha", "fail", "exit-dialog", "claude --resume s1"),
            restart.PaneLine("w2:p2", "beta", "ok", ""),
            dry_run=False,
        ),
    )
    assert cli.main(["restart-idle", "--yes"]) == 1
    out = capsys.readouterr().out
    assert "fail exit-dialog  w2:p1  alpha" in out
    assert "resume: claude --resume s1" in out
    assert "1 restarted, 0 skipped, 1 failed" in out


def test_yes_and_repeated_exclude_reach_the_engine(
    inside_herdr: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = _fake(monkeypatch, _report(dry_run=False))
    assert cli.main(["restart-idle", "--yes", "--exclude", "w2:p1", "--exclude", "w2:p2"]) == 0
    assert seen == [{"yes": True, "exclude": ("w2:p1", "w2:p2")}]


def test_outside_herdr_it_refuses_with_exit_two(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/local/bin/herdr")
    monkeypatch.delenv("HERDR_ENV", raising=False)
    seen = _fake(monkeypatch, _report())
    assert cli.main(["restart-idle", "--yes"]) == 2
    err = capsys.readouterr().err
    assert "not inside a herdr session" in err and seen == []


def test_herdr_off_path_refuses_with_the_runners_own_words(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.setenv("HERDR_ENV", "1")
    assert cli.main(["restart-idle"]) == 2
    assert "herdr is not on PATH" in capsys.readouterr().err


def test_a_herdr_error_while_listing_is_a_refusal(
    inside_herdr: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def boom(**_kw: object) -> restart.RestartReport:
        raise restart.HerdrError("herdr agent list failed: no socket")

    monkeypatch.setattr(restart, "restart_idle", boom)
    assert cli.main(["restart-idle"]) == 2
    assert "no socket" in capsys.readouterr().err
