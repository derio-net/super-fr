"""A journal `decision` records the Owner gate (spec 2026-10-14 exit-gates R12):
header tokens `gate=<role>`, `narrows=<ref>[,<ref>...]`, `decided_by=operator`
and, on a filing, `remainder_tracked_by=<issue>`.

They are header tokens, read by name and written only when set, so the journal
kind's stamp does not move (spec §C) — which holds only for token names no
released fr knows (review p3-r1, p3-r7).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Literal

import pytest
from fr.cli import app
from pydantic import BaseModel, ConfigDict, model_validator
from typer.testing import CliRunner

runner = CliRunner()


# --- a frozen stand-in of the RELEASED reader (fr 5.26) ----------------------------
#
# Vendored, minimal and deliberately NOT imported from `fr.journal.model`: the
# point is what an fr that predates this branch does with this branch's bytes.
# Its field set, its named projection and the validator rules it has on the
# tokens it knows are copied from fr 5.26's `JournalEntry` / `parse_journal`.
# Never edit it to follow the live model — that would make it a second live one.

_RELEASED_TRACKED_BY = re.compile(r"^(#\d+|[\w.-]+/[\w.-]+#\d+|https?://\S+)$")


class _ReleasedEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: str
    scope: str
    id: str
    created: str
    phase: int | None = None
    state: Literal["fixed", "refuted", "open"] | None = None
    resolves: str | None = None
    tracked_by: str | None = None
    out_of_scope: bool = False
    review_scope: Literal["in", "out"] | None = None
    answered_by: Literal["operator", "agent"] | None = None
    input: bool = False
    filed_as: str | None = None

    @model_validator(mode="after")
    def _released_rules(self) -> _ReleasedEntry:
        if self.kind == "finding" and self.state is None:
            raise ValueError("a `finding` entry requires a `state`")
        if self.kind != "finding" and self.state is not None:
            raise ValueError("`state` is only valid on `finding` entries")
        if self.resolves is not None and self.kind != "finding":
            raise ValueError("`resolves` is only valid on `finding` entries")
        if self.tracked_by is not None:
            if self.resolves is None or self.state != "open":
                raise ValueError("`tracked_by` is only valid on an `open` resolution record")
            if not _RELEASED_TRACKED_BY.match(self.tracked_by):
                raise ValueError("`tracked_by` must name an issue")
        if self.filed_as is not None and (self.resolves is None or self.state != "open"):
            raise ValueError("`filed_as` is only valid on an `open` resolution record")
        if self.input and (self.kind != "discovery" or self.scope != "spec"):
            raise ValueError("`input` is only valid on a spec-scope `discovery`")
        if self.answered_by is not None and self.resolves is None:
            raise ValueError("`answered_by` is only valid on a resolution record")
        return self


def _released_parse(text: str) -> list[_ReleasedEntry]:
    """fr 5.26's named projection over every delimiter header in `text`."""
    out: list[_ReleasedEntry] = []
    for line in text.splitlines():
        if not (line.startswith("<!-- fr:journal ") and line.endswith(" -->")):
            continue
        fields = dict(
            tok.partition("=")[::2] for tok in line[len("<!-- fr:journal ") : -4].split(" ") if tok
        )
        answered = fields.get("answered_by")
        out.append(
            _ReleasedEntry(
                kind=fields["kind"],
                scope=fields["scope"],
                id=fields["id"],
                created=fields["created"],
                phase=int(fields["phase"]) if "phase" in fields else None,
                state=fields.get("state"),  # type: ignore[arg-type]
                resolves=fields.get("resolves"),
                tracked_by=fields.get("tracked_by"),
                out_of_scope=fields.get("out_of_scope") == "true",
                review_scope=fields.get("review_scope"),  # type: ignore[arg-type]
                answered_by=answered if answered in ("operator", "agent") else None,  # type: ignore[arg-type]
                input=fields.get("input") == "true",
                filed_as=fields.get("filed_as"),
            )
        )
    return out


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
            decided_by="operator",
        )
        filing = _decision(
            id="d1-filed", narrows=("#2",), remainder_tracked_by="derio-net/super-fr#9"
        )
        text = serialize_entry(entry) + serialize_entry(filing)
        header = text.splitlines()[0]
        assert "gate=owner" in header
        assert "narrows=derio-net/super-fr#1,#2" in header
        assert "decided_by=operator" in header
        assert "remainder_tracked_by=derio-net/super-fr#9" in text
        assert parse_journal(text) == [entry, filing]

    def test_tokens_are_serialized_only_when_set(self) -> None:
        from fr.journal.model import serialize_entry

        header = serialize_entry(_decision()).splitlines()[0]
        for token in ("gate=", "narrows=", "decided_by=", "remainder_tracked_by="):
            assert token not in header

    def test_p3_r7_the_released_reader_parses_every_new_token(self) -> None:
        """This branch's serialized decisions, every new token set, read by a
        frozen stand-in of fr 5.26's reader: it must parse them as plain
        decisions — the property that lets the journal stamp stay put."""
        from fr.journal.model import serialize_entry

        text = serialize_entry(
            _decision(gate="owner", narrows=("o/r#1", "#2"), decided_by="operator")
        ) + serialize_entry(
            _decision(id="d1-filed", narrows=("o/r#1", "#2"), remainder_tracked_by="o/r#3")
        )

        assert [(e.kind, e.answered_by, e.tracked_by) for e in _released_parse(text)] == [
            ("decision", None, None),
            ("decision", None, None),
        ]

    @pytest.mark.parametrize(
        "token", ["answered_by=operator", "tracked_by=o/r#3"], ids=["answered_by", "tracked_by"]
    )
    def test_p3_r1_the_released_reader_refuses_the_old_token_names_on_a_decision(
        self, token: str
    ) -> None:
        """Why the decision tokens are not `answered_by=` / `tracked_by=`: the
        released reader knows those and refuses them on a decision."""
        from fr.journal.model import serialize_entry

        text = serialize_entry(_decision(narrows=("#1",)))
        header, rest = text.split("\n", 1)
        with pytest.raises(ValueError):
            _released_parse(header.replace(" -->", f" {token} -->") + "\n" + rest)

    @pytest.mark.parametrize("field", ["answered_by", "tracked_by"])
    def test_p3_r1_the_live_model_keeps_answered_by_and_tracked_by_resolution_only(
        self, field: str
    ) -> None:
        value = "operator" if field == "answered_by" else "o/r#3"
        with pytest.raises(ValueError, match=field):
            _decision(narrows=("#1",), **{field: value})

    @pytest.mark.parametrize("field", ["decided_by", "remainder_tracked_by"])
    def test_p3_r1_the_new_tokens_belong_to_decisions_only(self, field: str) -> None:
        from fr.journal.model import JournalEntry

        value = "operator" if field == "decided_by" else "o/r#3"
        with pytest.raises(ValueError, match=field):
            JournalEntry(
                kind="discovery",
                scope="spec",
                id="x1",
                created="2026-10-14T00:00:00+00:00",
                title="t",
                **{field: value},  # type: ignore[arg-type]
            )

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
        assert "decided_by=operator" in _journal(root)
        assert "answered_by=" not in _journal(root)

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
