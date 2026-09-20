"""Unit tests for the `fr journal` CLI (Phase 2): add / render / check.

Spec §A: append-only writes, duplicate-id refusal, PR-body render sections,
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
                "--phase",
                "1",
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
                "--phase",
                "1",
            ],
        )
        from fr.journal.model import parse_journal

        entries = parse_journal(_journal_file(root, "S").read_text())
        assert [e.id for e in entries] == ["d1", "d2"]

    def test_duplicate_add_fails_loudly_without_writing(self, tmp_path: Path, monkeypatch) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        first = _add(
            root,
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
            "--phase",
            "1",
        )
        assert first.exit_code == 0, first.output
        before = _journal_file(root, "S").read_text()

        duplicate = _add(
            root,
            "--scope",
            "plan",
            "--slug",
            "S",
            "--kind",
            "discovery",
            "--title",
            "two",
            "--id",
            "d1",
            "--phase",
            "1",
        )

        assert duplicate.exit_code == 2
        assert "d1" in duplicate.output
        assert "fr journal resolve" in duplicate.output
        assert _journal_file(root, "S").read_text() == before

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
                "--phase",
                "1",
            ],
        )
        assert res.exit_code != 0


class TestAddRequiresPhaseOrGlobal:
    """P3.T1 (spec §5.A2): `--scope plan` must not let an entry go untagged by
    accident — the untagged branch is what rendered 16 discoveries / 13,281
    chars in full at every phase in the phase-2 measurement."""

    def test_neither_phase_nor_global_is_refused_naming_the_consequence(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        res = _add(
            root,
            "--scope",
            "plan",
            "--slug",
            "S",
            "--kind",
            "discovery",
            "--title",
            "t",
        )
        assert res.exit_code == 2, res.output
        # The consequence, not just the flag name — a test asserting only on
        # exit code would pass against a message that says nothing.
        assert "renders in full" in res.output
        assert "every handoff" in res.output
        assert "every phase" in res.output
        assert not _journal_file(root, "S").exists()

    def test_global_alone_succeeds_and_writes_an_untagged_entry(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        res = _add(
            root,
            "--scope",
            "plan",
            "--slug",
            "S",
            "--kind",
            "discovery",
            "--title",
            "t",
            "--id",
            "d1",
            "--global",
        )
        assert res.exit_code == 0, res.output
        from fr.journal.model import parse_journal

        entries = parse_journal(_journal_file(root, "S").read_text())
        assert entries[0].phase is None

    def test_phase_alone_succeeds_and_tags_it(self, tmp_path: Path, monkeypatch) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        res = _add(
            root,
            "--scope",
            "plan",
            "--slug",
            "S",
            "--kind",
            "discovery",
            "--title",
            "t",
            "--id",
            "d1",
            "--phase",
            "3",
        )
        assert res.exit_code == 0, res.output
        from fr.journal.model import parse_journal

        entries = parse_journal(_journal_file(root, "S").read_text())
        assert entries[0].phase == 3

    def test_phase_and_global_together_is_refused_as_contradictory(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        res = _add(
            root,
            "--scope",
            "plan",
            "--slug",
            "S",
            "--kind",
            "discovery",
            "--title",
            "t",
            "--phase",
            "3",
            "--global",
        )
        assert res.exit_code == 2, res.output
        assert not _journal_file(root, "S").exists()

    def test_spec_scope_needs_neither_flag(self, tmp_path: Path, monkeypatch) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        res = _add(
            root,
            "--scope",
            "spec",
            "--slug",
            "S",
            "--kind",
            "discovery",
            "--title",
            "t",
            "--id",
            "d1",
        )
        assert res.exit_code == 0, res.output

    def test_debug_scope_needs_neither_flag(self, tmp_path: Path, monkeypatch) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        res = _add(
            root,
            "--scope",
            "debug",
            "--slug",
            "S",
            "--kind",
            "discovery",
            "--title",
            "t",
            "--id",
            "d1",
        )
        assert res.exit_code == 0, res.output


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
            "--phase",
            "1",
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
            "--phase",
            "1",
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
            "--phase",
            "1",
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
                "--phase",
                "1",
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
                "--phase",
                "1",
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
                "--phase",
                "1",
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


class TestScopeValidation:
    def test_every_journal_command_rejects_invalid_scope_cleanly(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        commands = (
            ["add", "--kind", "decision", "--title", "x"],
            ["resolve", "--id", "f1", "--state", "fixed", "--note", "x"],
            ["render"],
            ["check"],
            ["handoff", "--phase", "1"],
        )

        for command in commands:
            res = runner.invoke(app, ["journal", *command, "--scope", "bogus", "--slug", "S"])
            assert res.exit_code == 2, res.output
            assert "invalid journal scope" in res.output
            assert "Traceback" not in res.output


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


class TestResolve:
    """Phase 7 (spec §3.G.1) — `fr journal resolve` appends a resolution record
    the gate can read, and never rewrites the finding it resolves."""

    def _open_finding(self, root: Path, monkeypatch, fid: str = "f1") -> None:
        monkeypatch.chdir(root)
        res = _add(
            root,
            "--scope",
            "plan",
            "--slug",
            "S",
            "--kind",
            "finding",
            "--title",
            "a real bug",
            "--body",
            "the original body",
            "--state",
            "open",
            "--id",
            fid,
            "--phase",
            "1",
        )
        assert res.exit_code == 0, res.output

    def _resolve(self, *args: str):
        return runner.invoke(app, ["journal", "resolve", *args])

    def test_resolve_appends_a_record_and_leaves_the_original_entry_intact(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        from fr.journal.model import parse_journal

        root = _init_repo(tmp_path)
        self._open_finding(root, monkeypatch)
        res = self._resolve(
            "--scope",
            "plan",
            "--slug",
            "S",
            "--id",
            "f1",
            "--state",
            "fixed",
            "--note",
            "superseded by entry d9",
        )
        assert res.exit_code == 0, res.output

        entries = parse_journal(_journal_file(root, "S").read_text())
        original = next(e for e in entries if e.id == "f1")
        assert original.state == "open"  # append-only: never rewritten
        assert original.body == "the original body"
        assert original.title == "a real bug"

        record = next(e for e in entries if e.resolves == "f1")
        assert record.id != "f1"
        assert record.state == "fixed"
        assert "superseded by entry d9" in record.body

    def test_check_is_clean_once_the_only_open_finding_is_resolved(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """The gate fr-goal §7 asks for: unsatisfiable before, satisfiable now."""
        root = _init_repo(tmp_path)
        self._open_finding(root, monkeypatch)
        before = runner.invoke(app, ["journal", "check", "--scope", "plan", "--slug", "S"])
        assert before.exit_code == 1

        self._resolve(
            "--scope", "plan", "--slug", "S", "--id", "f1", "--state", "fixed", "--note", "why"
        )
        after = runner.invoke(app, ["journal", "check", "--scope", "plan", "--slug", "S"])
        assert after.exit_code == 0, after.output

    def test_check_reports_a_finding_reopened_by_a_later_add(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Last record wins — the effective state is a fold, not a one-way flag."""
        root = _init_repo(tmp_path)
        self._open_finding(root, monkeypatch)
        self._resolve(
            "--scope", "plan", "--slug", "S", "--id", "f1", "--state", "fixed", "--note", "why"
        )
        reopened = _add(
            root,
            "--scope",
            "plan",
            "--slug",
            "S",
            "--kind",
            "finding",
            "--title",
            "it came back",
            "--state",
            "open",
            "--resolves",
            "f1",
            "--id",
            "f1-again",
            "--phase",
            "1",
        )
        assert reopened.exit_code == 0, reopened.output
        res = runner.invoke(app, ["journal", "check", "--scope", "plan", "--slug", "S"])
        assert res.exit_code == 1
        assert "f1" in res.output

    def test_a_second_resolution_supersedes_the_first(self, tmp_path: Path, monkeypatch) -> None:
        from fr.journal.model import effective_finding_states, parse_journal

        root = _init_repo(tmp_path)
        self._open_finding(root, monkeypatch)
        self._resolve(
            "--scope", "plan", "--slug", "S", "--id", "f1", "--state", "fixed", "--note", "first"
        )
        second = self._resolve(
            "--scope",
            "plan",
            "--slug",
            "S",
            "--id",
            "f1",
            "--state",
            "refuted",
            "--note",
            "second look: not a bug",
        )
        assert second.exit_code == 0, second.output
        entries = parse_journal(_journal_file(root, "S").read_text())
        # Two distinct records — an id collision would make the journal invalid.
        ids = [e.id for e in entries]
        assert len(ids) == len(set(ids)) == 3
        assert effective_finding_states(entries)["f1"] == "refuted"

    def test_resolve_of_an_unknown_id_exits_nonzero_naming_it(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """A silent success is the failure this verb exists to prevent."""
        root = _init_repo(tmp_path)
        self._open_finding(root, monkeypatch)
        before = _journal_file(root, "S").read_text()
        res = self._resolve(
            "--scope", "plan", "--slug", "S", "--id", "typo", "--state", "fixed", "--note", "why"
        )
        assert res.exit_code != 0
        assert "typo" in res.output
        assert _journal_file(root, "S").read_text() == before

    def test_resolve_refuses_a_journal_with_duplicate_ids_without_writing(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        root = _init_repo(tmp_path)
        self._open_finding(root, monkeypatch)
        entry = _journal_file(root, "S").read_text().split("# Journal: S\n\n", 1)[1]
        _journal_file(root, "S").write_text(f"# Journal: S\n\n{entry}\n{entry}")
        before = _journal_file(root, "S").read_text()

        res = self._resolve(
            "--scope", "plan", "--slug", "S", "--id", "f1", "--state", "fixed", "--note", "why"
        )

        assert res.exit_code == 2
        assert "duplicate journal entry id" in res.output
        assert _journal_file(root, "S").read_text() == before

    def test_resolve_on_a_journal_that_does_not_exist_is_refused(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        res = self._resolve(
            "--scope", "plan", "--slug", "S", "--id", "f1", "--state", "fixed", "--note", "why"
        )
        assert res.exit_code != 0
        assert not _journal_file(root, "S").exists()

    def test_resolve_requires_a_note(self, tmp_path: Path, monkeypatch) -> None:
        """'Resolved' with no reason is the silent state change the rule forbids."""
        root = _init_repo(tmp_path)
        self._open_finding(root, monkeypatch)
        before = _journal_file(root, "S").read_text()
        res = self._resolve("--scope", "plan", "--slug", "S", "--id", "f1", "--state", "fixed")
        assert res.exit_code == 2
        assert _journal_file(root, "S").read_text() == before

    def test_resolve_refuses_state_open(self, tmp_path: Path, monkeypatch) -> None:
        """`resolve` closes a finding; re-opening one is `add --resolves`."""
        root = _init_repo(tmp_path)
        self._open_finding(root, monkeypatch)
        before = _journal_file(root, "S").read_text()
        res = self._resolve(
            "--scope", "plan", "--slug", "S", "--id", "f1", "--state", "open", "--note", "why"
        )
        assert res.exit_code == 2
        assert "fixed" in res.output and "refuted" in res.output
        assert _journal_file(root, "S").read_text() == before

    def test_resolve_refuses_an_id_that_is_not_a_finding(self, tmp_path: Path, monkeypatch) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        _add(
            root,
            "--scope",
            "plan",
            "--slug",
            "S",
            "--kind",
            "discovery",
            "--title",
            "a note",
            "--id",
            "d1",
            "--phase",
            "1",
        )
        before = _journal_file(root, "S").read_text()
        res = self._resolve(
            "--scope", "plan", "--slug", "S", "--id", "d1", "--state", "fixed", "--note", "why"
        )
        assert res.exit_code != 0
        assert "d1" in res.output
        assert _journal_file(root, "S").read_text() == before

    def test_render_shows_both_the_finding_and_its_resolution(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """The PR body reads `render`: what was found AND what became of it."""
        root = _init_repo(tmp_path)
        self._open_finding(root, monkeypatch)
        self._resolve(
            "--scope",
            "plan",
            "--slug",
            "S",
            "--id",
            "f1",
            "--state",
            "fixed",
            "--note",
            "superseded by entry d9",
        )
        res = runner.invoke(
            app, ["journal", "render", "--scope", "plan", "--slug", "S", "--section", "findings"]
        )
        assert res.exit_code == 0, res.output
        assert "a real bug" in res.output
        assert "superseded by entry d9" in res.output


def test_add_resolves_refuses_an_id_not_in_this_journal(tmp_path: Path, monkeypatch) -> None:
    """`resolve` already refuses an unknown id; `--resolves` must too (r7-m2).

    `effective_finding_states` deliberately tolerates a record naming a finding
    that is not in the file, so a hand-spliced journal cannot crash the gate.
    The cost of that tolerance is that a typo'd `--resolves` id would report as
    open forever with nothing in the journal to explain it — a gate wedged by an
    unfindable id, which is the silent-stall shape this whole PR removes. Refuse
    it at the door instead."""
    root = _init_repo(tmp_path)
    monkeypatch.chdir(root)
    _add(
        root,
        "--scope",
        "plan",
        "--slug",
        "s",
        "--kind",
        "finding",
        "--id",
        "real",
        "--state",
        "open",
        "--title",
        "t",
        "--body",
        "b",
        "--phase",
        "1",
    )

    res = _add(
        root,
        "--scope",
        "plan",
        "--slug",
        "s",
        "--kind",
        "finding",
        "--id",
        "reopen",
        "--state",
        "open",
        "--title",
        "t",
        "--body",
        "b",
        "--resolves",
        "typoed-id",
        "--phase",
        "1",
    )
    assert res.exit_code == 2, res.output
    assert "typoed-id" in res.output
    assert "reopen" not in _journal_file(root, "s").read_text()
