"""A journal `decision` records the Owner gate (spec 2026-10-14 exit-gates R12):
header tokens `gate=<role>`, `narrows=<ref>[,<ref>...]` and `answered_by=operator`.

They are header tokens, read by name and written only when set, so the journal
kind's stamp does not move (spec §C).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def _decision(**kw: object):
    from fr.journal.model import JournalEntry

    base: dict[str, object] = {
        "kind": "decision",
        "scope": "spec",
        "id": "d1",
        "created": "2026-10-14T00:00:00+00:00",
        "title": "Owner narrows the issue",
        "body": "Only half of it ships here.",
    }
    return JournalEntry(**{**base, **kw})  # type: ignore[arg-type]


class TestModel:
    def test_a_decision_round_trips_every_token(self) -> None:
        from fr.journal.model import parse_journal, serialize_entry

        entry = _decision(
            gate="owner",
            narrows=("derio-net/super-fr#1", "#2"),
            answered_by="operator",
        )
        text = serialize_entry(entry)
        header = text.splitlines()[0]
        assert "gate=owner" in header
        assert "narrows=derio-net/super-fr#1,#2" in header
        assert "answered_by=operator" in header
        (back,) = parse_journal(text)
        assert back == entry

    def test_tokens_are_serialized_only_when_set(self) -> None:
        from fr.journal.model import serialize_entry

        header = serialize_entry(_decision()).splitlines()[0]
        for token in ("gate=", "narrows=", "answered_by="):
            assert token not in header

    def test_an_older_shaped_parse_ignores_the_tokens(self) -> None:
        """The named projection: a parser that names only the fields it knows
        never hands the new tokens to the model, so an older fr reads the
        decision as a plain one."""
        from fr.journal import model

        text = model.serialize_entry(_decision(gate="owner", narrows=("#7",)))
        older = text.replace(" gate=owner", "").replace(" narrows=#7", "")
        (plain,) = model.parse_journal(older)
        assert plain.gate is None and plain.narrows == ()

    def test_answered_by_stays_refused_on_a_finding_that_is_not_a_resolution(self) -> None:
        from fr.journal.model import JournalEntry

        with pytest.raises(ValueError, match="answered_by"):
            JournalEntry(
                kind="finding",
                scope="spec",
                id="f1",
                created="2026-10-14T00:00:00+00:00",
                title="t",
                state="open",
                answered_by="operator",
            )

    @pytest.mark.parametrize(
        ("kw", "why"),
        [
            ({"gate": "nobody"}, "gate"),
            ({"narrows": ("not a ref",)}, "narrows"),
        ],
    )
    def test_a_bad_token_value_is_refused(self, kw: dict[str, object], why: str) -> None:
        with pytest.raises(ValueError, match=why):
            _decision(**kw)

    @pytest.mark.parametrize("token", ["gate", "narrows"])
    def test_the_tokens_belong_to_decisions_only(self, token: str) -> None:
        from fr.journal.model import JournalEntry

        value: object = "owner" if token == "gate" else ("#1",)
        with pytest.raises(ValueError, match=token):
            JournalEntry(
                kind="discovery",
                scope="spec",
                id="x1",
                created="2026-10-14T00:00:00+00:00",
                title="t",
                **{token: value},  # type: ignore[arg-type]
            )


def _repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    from fr.commands import journal_cmd

    monkeypatch.setattr(journal_cmd, "_orphan_refusal", lambda *a, **k: None)
    monkeypatch.chdir(root)
    return root


def _add_decision(env: dict[str, str] | None, *extra: str):
    return runner.invoke(
        app,
        [
            *("journal", "add", "--scope", "spec", "--slug", "s", "--kind", "decision"),
            *("--id", "d1", "--title", "Owner narrows #1", *extra),
        ],
        env=env,
    )


def _journal(root: Path) -> str:
    return (root / "docs/superpowers/journals/specs/s.md").read_text()


class TestAdd:
    def test_add_writes_gate_and_narrows(self, tmp_path: Path, monkeypatch) -> None:
        root = _repo(tmp_path, monkeypatch)
        res = _add_decision(None, "--gate", "owner", "--narrows", "derio-net/super-fr#1,#2")
        assert res.exit_code == 0, res.output
        header = next(line for line in _journal(root).splitlines() if " id=d1 " in line)
        assert "gate=owner" in header and "narrows=derio-net/super-fr#1,#2" in header

    def test_a_bad_narrows_ref_is_refused_and_nothing_written(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        root = _repo(tmp_path, monkeypatch)
        res = _add_decision(None, "--narrows", "issue one")
        assert res.exit_code == 2, res.output
        assert not (root / "docs/superpowers/journals/specs/s.md").exists()

    def test_answered_by_operator_is_verified_against_the_transcript(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        from tests.unit.transcript_sessions import asked_at

        root = _repo(tmp_path, monkeypatch)
        asked_at(tmp_path / "projects", "2099-01-01T00:00:00.000Z", session_id="s-q")
        env = {
            "FR_HARNESS": "claude-code",
            "FR_TRANSCRIPT_ROOT": str(tmp_path / "projects"),
            "CLAUDE_CODE_SESSION_ID": "s-q",
        }
        res = _add_decision(env, "--narrows", "#1", "--answered-by", "operator")
        assert res.exit_code == 0, res.output
        assert "answered_by=operator" in _journal(root)

    def test_an_answered_by_operator_claim_with_no_answer_since_is_refused(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        from tests.unit.transcript_sessions import asked_at

        root = _repo(tmp_path, monkeypatch)
        first = runner.invoke(
            app,
            [
                *("journal", "add", "--scope", "spec", "--slug", "s", "--kind"),
                *("discovery", "--id", "x0", "--title", "earlier"),
            ],
        )
        assert first.exit_code == 0, first.output
        before = _journal(root)
        asked_at(tmp_path / "projects", "2000-01-01T00:00:00.000Z", session_id="s-q")
        env = {
            "FR_HARNESS": "claude-code",
            "FR_TRANSCRIPT_ROOT": str(tmp_path / "projects"),
            "CLAUDE_CODE_SESSION_ID": "s-q",
        }
        res = _add_decision(env, "--narrows", "#1", "--answered-by", "operator")
        assert res.exit_code == 2, res.output
        assert "no answered question" in res.output
        assert _journal(root) == before
