"""Unit tests for the `fr journal` CLI (Phase 2): add / render / check.

Spec §A: append-only writes, idempotency on `--id`, PR-body render sections,
and a freshness `check` that fails closed on parse but where `render` fails
open.
"""

from __future__ import annotations

from pathlib import Path

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
    return root / "docs/superpowers/journals" / f"{slug}.md"


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

    def test_add_idempotent_on_id(self, tmp_path: Path, monkeypatch) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        for _ in range(2):
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
        from fr.journal.model import parse_journal

        entries = parse_journal(_journal_file(root, "S").read_text())
        assert [e.id for e in entries] == ["d1"]

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
