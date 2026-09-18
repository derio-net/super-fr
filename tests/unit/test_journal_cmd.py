"""Unit tests for the `fr journal` CLI (Phase 2): add / render / check.

Spec §A: append-only writes, idempotency on `--id`, PR-body render sections,
and a freshness `check` that fails closed on parse but where `render` fails
open.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def _init_repo(tmp_path: Path) -> Path:
    # `fr journal` resolves the repo root via git; make tmp_path a repo.
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return tmp_path


def _add(root: Path, *args: str):
    return runner.invoke(app, ["journal", "add", *args], env={"PWD": str(root)})


def _journal_file(root: Path, slug: str) -> Path:
    # These CLI tests all use --scope plan → journals/plans/<slug>.md.
    return root / "docs/superpowers/journals/plans" / f"{slug}.md"


class TestAdd:
    def test_add_creates_file_and_entry(self, tmp_path: Path, monkeypatch) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        res = runner.invoke(
            app,
            [
                "journal",
                "add",
                "--scope",
                "plan",
                "--slug",
                "S",
                "--kind",
                "discovery",
                "--title",
                "found a thing",
                "--body",
                "details",
                "--phase",
                "2",
                "--id",
                "d1",
            ],
        )
        assert res.exit_code == 0, res.output
        from fr.journal.model import parse_journal

        entries = parse_journal(_journal_file(root, "S").read_text())
        assert len(entries) == 1
        assert entries[0].id == "d1"
        assert entries[0].kind == "discovery"
        assert entries[0].title == "found a thing"

    def test_second_add_appends(self, tmp_path: Path, monkeypatch) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        runner.invoke(
            app,
            [
                "journal",
                "add",
                "--scope",
                "plan",
                "--slug",
                "S",
                "--kind",
                "discovery",
                "--title",
                "one",
                "--id",
                "d1",
            ],
        )
        runner.invoke(
            app,
            [
                "journal",
                "add",
                "--scope",
                "plan",
                "--slug",
                "S",
                "--kind",
                "discovery",
                "--title",
                "two",
                "--id",
                "d2",
            ],
        )
        from fr.journal.model import parse_journal

        entries = parse_journal(_journal_file(root, "S").read_text())
        assert [e.id for e in entries] == ["d1", "d2"]

    def test_add_duplicate_id_fails_without_rewriting(self, tmp_path: Path, monkeypatch) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        args = [
            "journal",
            "add",
            "--scope",
            "plan",
            "--slug",
            "S",
            "--kind",
            "discovery",
            "--title",
            "one",
            "--id",
            "d1",
        ]
        assert runner.invoke(app, args).exit_code == 0
        path = _journal_file(root, "S")
        before = path.read_text()

        res = runner.invoke(app, args)

        assert res.exit_code == 2
        assert "fr journal update" in res.output
        assert path.read_text() == before

    def test_finding_requires_state_via_cli(self, tmp_path: Path, monkeypatch) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        res = runner.invoke(
            app,
            [
                "journal",
                "add",
                "--scope",
                "plan",
                "--slug",
                "S",
                "--kind",
                "finding",
                "--title",
                "bug",
                "--id",
                "f1",
            ],
        )
        assert res.exit_code != 0


class TestRender:
    def _seed(self, root: Path) -> None:
        add = lambda *a: runner.invoke(app, ["journal", "add", *a])  # noqa: E731
        add(
            "--scope",
            "plan",
            "--slug",
            "S",
            "--kind",
            "decision",
            "--title",
            "chose X",
            "--id",
            "dec1",
        )
        add(
            "--scope",
            "plan",
            "--slug",
            "S",
            "--kind",
            "finding",
            "--title",
            "off-by-one",
            "--id",
            "f1",
            "--state",
            "fixed",
        )
        add(
            "--scope",
            "plan",
            "--slug",
            "S",
            "--kind",
            "discovery",
            "--title",
            "quirk",
            "--id",
            "disc1",
        )

    def test_render_findings_section(self, tmp_path: Path, monkeypatch) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        self._seed(root)
        res = runner.invoke(
            app, ["journal", "render", "--scope", "plan", "--slug", "S", "--section", "findings"]
        )
        assert res.exit_code == 0
        assert "off-by-one" in res.output
        assert "chose X" not in res.output

    def test_render_decisions_section(self, tmp_path: Path, monkeypatch) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        self._seed(root)
        res = runner.invoke(
            app, ["journal", "render", "--scope", "plan", "--slug", "S", "--section", "decisions"]
        )
        assert "chose X" in res.output
        assert "off-by-one" not in res.output

    def test_render_all_default(self, tmp_path: Path, monkeypatch) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        self._seed(root)
        res = runner.invoke(app, ["journal", "render", "--scope", "plan", "--slug", "S"])
        assert "chose X" in res.output and "off-by-one" in res.output and "quirk" in res.output

    def test_render_missing_journal_fails_open(self, tmp_path: Path, monkeypatch) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        res = runner.invoke(app, ["journal", "render", "--scope", "plan", "--slug", "ghost"])
        assert res.exit_code == 0
        assert res.output.strip() == ""

    def test_render_emits_brackets_verbatim(self, tmp_path: Path, monkeypatch) -> None:
        """F1: render output feeds a PR body — bracketed text must survive raw
        (a Rich console would treat `[x]` as markup and drop it)."""
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        runner.invoke(
            app,
            [
                "journal",
                "add",
                "--scope",
                "plan",
                "--slug",
                "S",
                "--kind",
                "finding",
                "--title",
                "see [details](url)",
                "--body",
                "fixed by [PR #12]",
                "--id",
                "f1",
                "--state",
                "fixed",
            ],
        )
        res = runner.invoke(app, ["journal", "render", "--scope", "plan", "--slug", "S"])
        assert "[details](url)" in res.output
        assert "[PR #12]" in res.output


class TestCheck:
    def test_check_clean_exits_zero(self, tmp_path: Path, monkeypatch) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        runner.invoke(
            app,
            [
                "journal",
                "add",
                "--scope",
                "plan",
                "--slug",
                "S",
                "--kind",
                "finding",
                "--title",
                "b",
                "--id",
                "f1",
                "--state",
                "fixed",
            ],
        )
        res = runner.invoke(app, ["journal", "check", "--scope", "plan", "--slug", "S"])
        assert res.exit_code == 0, res.output

    def test_check_open_finding_exits_nonzero(self, tmp_path: Path, monkeypatch) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        runner.invoke(
            app,
            [
                "journal",
                "add",
                "--scope",
                "plan",
                "--slug",
                "S",
                "--kind",
                "finding",
                "--title",
                "b",
                "--id",
                "f1",
                "--state",
                "open",
            ],
        )
        res = runner.invoke(app, ["journal", "check", "--scope", "plan", "--slug", "S"])
        assert res.exit_code != 0

    def test_check_malformed_fails_closed(self, tmp_path: Path, monkeypatch) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        jf = _journal_file(root, "S")
        jf.parent.mkdir(parents=True, exist_ok=True)
        jf.write_text("<!-- fr:journal broken header -->\n### x\n\nbody\n")
        res = runner.invoke(app, ["journal", "check", "--scope", "plan", "--slug", "S"])
        assert res.exit_code != 0

    def test_render_malformed_fails_open(self, tmp_path: Path, monkeypatch) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        jf = _journal_file(root, "S")
        jf.parent.mkdir(parents=True, exist_ok=True)
        jf.write_text("<!-- fr:journal broken header -->\n### x\n\nbody\n")
        res = runner.invoke(app, ["journal", "render", "--scope", "plan", "--slug", "S"])
        assert res.exit_code == 0


class TestUpdate:
    def _add_finding(self, root: Path) -> None:
        res = runner.invoke(
            app,
            [
                "journal",
                "add",
                "--scope",
                "plan",
                "--slug",
                "S",
                "--kind",
                "finding",
                "--title",
                "a finding",
                "--body",
                "original evidence",
                "--phase",
                "2",
                "--id",
                "f1",
                "--state",
                "open",
            ],
        )
        assert res.exit_code == 0, res.output

    def test_update_rewrites_finding_state_and_appends_note(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        self._add_finding(root)
        path = _journal_file(root, "S")
        path.write_text(
            "# Journal: S\n\nPreamble survives.\n\n" + path.read_text().split("\n\n", 1)[1]
        )

        res = runner.invoke(
            app,
            [
                "journal",
                "update",
                "--scope",
                "plan",
                "--slug",
                "S",
                "--id",
                "f1",
                "--state",
                "fixed",
                "--note",
                "resolved by regression",
            ],
        )

        assert res.exit_code == 0, res.output
        text = path.read_text()
        assert text.startswith("# Journal: S\n\nPreamble survives.\n\n")
        assert "id=f1 created=" in text
        assert "phase=2 state=fixed" in text
        assert "### f1 · finding [fixed] · a finding (phase 2)" in text
        from fr.journal.model import parse_journal

        entry = parse_journal(text)[0]
        assert entry.body == "original evidence\n\nresolved by regression"
        assert (
            runner.invoke(app, ["journal", "check", "--scope", "plan", "--slug", "S"]).exit_code
            == 0
        )

    def test_update_rejects_invalid_target_or_journal_without_writing(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        self._add_finding(root)
        path = _journal_file(root, "S")
        before = path.read_text()
        runner.invoke(
            app,
            [
                "journal",
                "add",
                "--scope",
                "plan",
                "--slug",
                "S",
                "--kind",
                "decision",
                "--title",
                "a decision",
                "--id",
                "d1",
            ],
        )
        before_with_decision = path.read_text()

        unknown = runner.invoke(
            app,
            [
                "journal",
                "update",
                "--scope",
                "plan",
                "--slug",
                "S",
                "--id",
                "missing",
                "--state",
                "fixed",
            ],
        )
        non_finding = runner.invoke(
            app,
            [
                "journal",
                "update",
                "--scope",
                "plan",
                "--slug",
                "S",
                "--id",
                "d1",
                "--state",
                "fixed",
            ],
        )
        assert unknown.exit_code == non_finding.exit_code == 2
        assert path.read_text() == before_with_decision

        invalid_state = runner.invoke(
            app,
            [
                "journal",
                "update",
                "--scope",
                "plan",
                "--slug",
                "S",
                "--id",
                "f1",
                "--state",
                "invalid",
            ],
        )
        assert invalid_state.exit_code == 2
        assert path.read_text() == before_with_decision

        path.write_text("<!-- fr:journal broken header -->\n")
        malformed_before = path.read_text()
        malformed = runner.invoke(
            app,
            [
                "journal",
                "update",
                "--scope",
                "plan",
                "--slug",
                "S",
                "--id",
                "f1",
                "--state",
                "fixed",
            ],
        )
        assert malformed.exit_code == 2
        assert path.read_text() == malformed_before
        assert before != malformed_before

    def test_update_rejects_invalid_entry_fields_without_writing(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        path = _journal_file(root, "S")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "<!-- fr:journal kind=finding scope=plan id=f1 created=2026-09-18T00:00:00 "
            "state=invalid -->\n### f1 · finding [invalid] · bad\n"
        )
        before = path.read_text()

        res = runner.invoke(
            app,
            [
                "journal",
                "update",
                "--scope",
                "plan",
                "--slug",
                "S",
                "--id",
                "f1",
                "--state",
                "fixed",
            ],
        )

        assert res.exit_code == 2
        assert path.read_text() == before

    def test_update_rejects_duplicate_source_ids_without_writing(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        path = _journal_file(root, "S")
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = (
            "<!-- fr:journal kind=finding scope=plan id=f1 created=2026-09-18T00:00:00 "
            "state=open -->\n### f1 · finding [open] · finding\n"
        )
        path.write_text(entry + "\n" + entry)
        before = path.read_text()

        res = runner.invoke(
            app,
            [
                "journal",
                "update",
                "--scope",
                "plan",
                "--slug",
                "S",
                "--id",
                "f1",
                "--state",
                "fixed",
            ],
        )

        assert res.exit_code == 2
        assert "duplicate journal entry id" in res.output
        assert path.read_text() == before

    @pytest.mark.parametrize(
        "bad_header",
        ["unexpected=value", "state=open state=fixed"],
    )
    def test_update_rejects_ambiguous_header_without_writing(
        self, tmp_path: Path, monkeypatch, bad_header: str
    ) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        path = _journal_file(root, "S")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "<!-- fr:journal kind=finding scope=plan id=f1 created=2026-09-18T00:00:00 "
            f"state=open {bad_header} -->\n### f1 · finding [open] · finding\n"
        )
        before = path.read_text()

        res = runner.invoke(
            app,
            [
                "journal",
                "update",
                "--scope",
                "plan",
                "--slug",
                "S",
                "--id",
                "f1",
                "--state",
                "fixed",
            ],
        )

        assert res.exit_code == 2
        assert path.read_text() == before

    def test_update_rejects_bad_entry_heading_without_writing(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        path = _journal_file(root, "S")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "### f1 · finding [open] · preamble trap\n\n"
            "<!-- fr:journal kind=finding scope=plan id=f1 created=2026-09-18T00:00:00 "
            "state=open -->\n### f1 · decision · wrong kind\n"
        )
        before = path.read_text()

        res = runner.invoke(
            app,
            [
                "journal",
                "update",
                "--scope",
                "plan",
                "--slug",
                "S",
                "--id",
                "f1",
                "--state",
                "fixed",
            ],
        )

        assert res.exit_code == 2
        assert "heading does not match" in res.output
        assert path.read_text() == before

    def test_update_refuses_legacy_state_heading_without_writing(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        path = _journal_file(root, "S")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "<!-- fr:journal kind=finding scope=plan id=f1 created=2026-09-14T22:03:02 "
            "state=fixed -->\n### f1 · finding [open] · legacy resolved finding\n"
        )
        before = path.read_text()

        update = runner.invoke(
            app,
            [
                "journal",
                "update",
                "--scope",
                "plan",
                "--slug",
                "S",
                "--id",
                "f1",
                "--state",
                "fixed",
            ],
        )
        render = runner.invoke(app, ["journal", "render", "--scope", "plan", "--slug", "S"])
        check = runner.invoke(app, ["journal", "check", "--scope", "plan", "--slug", "S"])

        assert update.exit_code == 2
        assert "cannot be safely rewritten" in update.output
        assert path.read_text() == before
        assert render.exit_code == check.exit_code == 0
        assert "[fixed]" in render.output

    def test_update_rejects_truncated_delimiter_without_writing(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        self._add_finding(root)
        path = _journal_file(root, "S")
        path.write_text(
            path.read_text()
            + "\n<!-- fr:journal kind=finding scope=plan id=truncated\n"
            + "content that must not be dropped\n"
        )
        before = path.read_text()

        update = runner.invoke(
            app,
            [
                "journal",
                "update",
                "--scope",
                "plan",
                "--slug",
                "S",
                "--id",
                "f1",
                "--state",
                "fixed",
            ],
        )
        render = runner.invoke(app, ["journal", "render", "--scope", "plan", "--slug", "S"])
        check = runner.invoke(app, ["journal", "check", "--scope", "plan", "--slug", "S"])

        assert update.exit_code == 2
        assert "unterminated journal delimiter" in update.output
        assert path.read_text() == before
        assert render.exit_code == 0
        assert render.output == ""
        assert check.exit_code == 2

    def test_update_rejects_invalid_scope_without_writing(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        self._add_finding(root)
        path = _journal_file(root, "S")
        before = path.read_text()

        res = runner.invoke(
            app,
            [
                "journal",
                "update",
                "--scope",
                "invalid",
                "--slug",
                "S",
                "--id",
                "f1",
                "--state",
                "fixed",
            ],
        )

        assert res.exit_code == 2
        assert "invalid journal scope" in res.output
        assert "KeyError" not in res.output
        assert path.read_text() == before

    def test_update_writes_archived_journal_when_it_is_the_read_resolution(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        from fr.journal.model import archived_journal_path

        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        path = archived_journal_path(root, "plan", "S")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "# Archived\n\n<!-- fr:journal kind=finding scope=plan id=f1 "
            "created=2026-09-18T00:00:00 state=open -->\n"
            "### f1 · finding [open] · old finding\n\nold evidence\n"
        )

        res = runner.invoke(
            app,
            [
                "journal",
                "update",
                "--scope",
                "plan",
                "--slug",
                "S",
                "--id",
                "f1",
                "--state",
                "refuted",
            ],
        )

        assert res.exit_code == 0, res.output
        assert "state=refuted" in path.read_text()
        assert not _journal_file(root, "S").exists()


class TestReadsResolveArchivedLocation:
    """After a spec/plan archives, its journal lives under
    implemented/journals/<scope>/; render and check must still find it (#417)."""

    def _write_archived(self, root: Path, scope: str, slug: str, text: str) -> Path:
        from fr.journal.model import archived_journal_path

        path = archived_journal_path(root, scope, slug)  # type: ignore[arg-type]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def test_render_finds_archived_journal(self, tmp_path: Path, monkeypatch) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        self._write_archived(
            root,
            "spec",
            "2026-07-24-arch",
            "# Journal\n\n"
            "<!-- fr:journal kind=decision scope=spec id=d1 created=2026-07-24T10:00:00 -->\n"
            "### d1 · decision · a call\n\nrationale\n",
        )
        res = runner.invoke(
            app, ["journal", "render", "--scope", "spec", "--slug", "2026-07-24-arch"]
        )
        assert res.exit_code == 0, res.output
        assert "a call" in res.output

    def test_check_reads_archived_journal(self, tmp_path: Path, monkeypatch) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        # An archived journal with an open finding must still fail `check`.
        self._write_archived(
            root,
            "spec",
            "2026-07-24-arch",
            "# Journal\n\n"
            "<!-- fr:journal kind=finding scope=spec id=f1 created=2026-07-24T10:00:00 "
            "state=open -->\n### f1 · finding [open] · loose end\n\nbody\n",
        )
        res = runner.invoke(
            app, ["journal", "check", "--scope", "spec", "--slug", "2026-07-24-arch"]
        )
        assert res.exit_code != 0, res.output


class TestHandoff:
    """`fr journal handoff` — the curated executor brief (methodology
    restoration): dependency-scoped composition over the raw journal."""

    def _write_plan(self, root: Path, slug: str = "H") -> Path:
        from fr.plan_ops import PhaseSpec, create

        (root / "docs" / "superpowers" / "specs").mkdir(parents=True, exist_ok=True)
        create(
            repo_root=root,
            slug=slug,
            spec=None,
            target_repo="derio-net/test",
            fr_version=">=3.0.0,<5.0.0",
            phases=[
                PhaseSpec(number=1, title="One", tasks=()),
                PhaseSpec(number=2, title="Two", depends_on=(1,), tasks=()),
            ],
            prose="# x\n",
        )
        return root / "docs" / "superpowers" / "plans" / slug

    def _write_journal(self, root: Path, slug: str = "H") -> None:
        from fr.journal.model import JournalEntry, journal_path, serialize_entry

        def e(eid, kind, title, body, phase=None, state=None):
            return serialize_entry(
                JournalEntry(
                    kind=kind,  # type: ignore[arg-type]
                    scope="plan",  # type: ignore[arg-type]
                    id=eid,
                    created="2026-09-09T00:00:00",
                    phase=phase,
                    title=title,
                    body=body,
                    state=state,  # type: ignore[arg-type]
                )
            )

        path = journal_path(root, "plan", slug)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "# Journal: H\n\n"
            + e("o9", "finding", "Open elsewhere", "actionable anywhere", phase=9, state="open")
            + "\n"
            + e("d1", "decision", "Dep decision", "why we did it", phase=1)
            + "\n"
            + e("d5", "decision", "Far decision", "unrelated rationale", phase=5)
            + "\n"
            + e("f5", "finding", "Fixed elsewhere", "ancient detail", phase=5, state="fixed")
        )

    def _handoff(self, phase: str = "2", extra: list | None = None):
        argv = ["journal", "handoff", "--scope", "plan", "--slug", "H", "--phase", phase]
        return runner.invoke(app, argv + (extra or []))

    def test_handoff_composes_dependency_scoped_brief(self, tmp_path: Path, monkeypatch) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        self._write_plan(root)
        self._write_journal(root)

        res = self._handoff()

        assert res.exit_code == 0, res.output
        assert "actionable anywhere" in res.output  # open: full
        assert "why we did it" in res.output  # dep decision: full
        assert "Far decision" in res.output  # far: collapsed, title kept
        assert "unrelated rationale" not in res.output
        assert "Fixed elsewhere" in res.output
        assert "ancient detail" not in res.output
        assert "fr journal render --scope plan --slug H" in res.output

    def test_handoff_missing_journal_fails_open(self, tmp_path: Path, monkeypatch) -> None:
        from fr.journal.model import journal_path

        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        self._write_plan(root)
        # `create` seeds a plan journal — remove it: a journal never written
        # is nothing to curate (empty output, exit 0).
        journal_path(root, "plan", "H").unlink()

        res = self._handoff()

        assert res.exit_code == 0, res.output
        assert res.output.strip() == ""

    def test_handoff_malformed_journal_fails_closed(self, tmp_path: Path, monkeypatch) -> None:
        """Unlike `render` (PR-body feed, fail-open), the handoff feeds an
        executor brief — a silently-empty handoff makes the executor guess."""
        from fr.journal.model import journal_path

        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        self._write_plan(root)
        path = journal_path(root, "plan", "H")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("<!-- fr:journal broken header -->\n")

        res = self._handoff()

        assert res.exit_code == 2, res.output

    def test_handoff_missing_plan_fails_closed(self, tmp_path: Path, monkeypatch) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        self._write_journal(root)

        res = self._handoff()

        assert res.exit_code == 2, res.output
        assert "H" in res.output

    def test_handoff_unknown_phase_is_refused(self, tmp_path: Path, monkeypatch) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        self._write_plan(root)
        self._write_journal(root)

        res = self._handoff(phase="9")

        assert res.exit_code == 2, res.output
        assert "phase 9" in res.output

    def test_handoff_refuses_non_plan_scope(self, tmp_path: Path, monkeypatch) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)

        res = runner.invoke(
            app, ["journal", "handoff", "--scope", "spec", "--slug", "S", "--phase", "1"]
        )

        assert res.exit_code == 2, res.output
