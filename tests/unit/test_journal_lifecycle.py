"""Phase 3: journal lifecycle wiring — plan-create init + archive moves.

Spec §A: `fr plan create` initializes the plan journal; `fr archive` moves a
plan journal to implemented/journals/ with its plan, and a spec journal follows
a fully-implemented spec. Plans/specs without a journal stay fully functional
(back-compat).
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def _make_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "test@example.com"], check=True
    )
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], check=True)
    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
    (tmp_path / "docs" / "superpowers" / "plans").mkdir()
    return tmp_path


def _make_spec(repo: Path, slug: str = "test-spec") -> Path:
    spec_path = repo / "docs" / "superpowers" / "specs" / f"2026-05-10-{slug}.md"
    spec_path.write_text(
        "# Test spec\n\n"
        "## Implementation Plans\n\n"
        "| Plan | Repo | File | Depends on |\n"
        "|------|------|------|------------|\n"
    )
    return spec_path


def _create_plan(repo: Path, slug: str, spec_path: Path):
    from fr.plan_ops import PhaseSpec, create

    return create(
        repo_root=repo,
        slug=slug,
        spec=str(spec_path.relative_to(repo)),
        target_repo="derio-net/test",
        fr_version=">=1.0.0,<4.0.0",
        phases=[
            PhaseSpec(
                number=1,
                title="First",
                tag="agentic",
                tasks=({"number": 1, "title": "t", "steps": [{"id": "P1.T1.S1", "text": "s"}]},),
            )
        ],
        prose="# plan\n",
    )


class TestPlanCreateInitializesJournal:
    def test_create_writes_plan_journal(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        spec = _make_spec(repo)
        _create_plan(repo, "2026-07-22-lc", spec)
        jpath = repo / "docs/superpowers/journals/plans/2026-07-22-lc.md"
        assert jpath.exists(), "plan create must initialize the plan journal"

    def test_created_journal_parses_empty(self, tmp_path: Path) -> None:
        from fr.journal.model import parse_journal

        repo = _make_repo(tmp_path)
        spec = _make_spec(repo)
        _create_plan(repo, "2026-07-22-lc", spec)
        jpath = repo / "docs/superpowers/journals/plans/2026-07-22-lc.md"
        assert parse_journal(jpath.read_text()) == []

    def test_plan_without_journal_still_parses(self, tmp_path: Path) -> None:
        """Back-compat: a plan folder whose journal was removed still parses."""
        from fr.parser import parse

        repo = _make_repo(tmp_path)
        spec = _make_spec(repo)
        plan_dir = repo / "docs/superpowers/plans/2026-07-22-lc"
        _create_plan(repo, "2026-07-22-lc", spec)
        (repo / "docs/superpowers/journals/plans/2026-07-22-lc.md").unlink()
        assert parse(plan_dir) is not None


class TestArchiveMovesPlanJournal:
    def test_archive_moves_plan_journal(self, tmp_path: Path) -> None:
        from fr.archive import archive_plan_dir

        repo = _make_repo(tmp_path)
        spec = _make_spec(repo)
        _create_plan(repo, "2026-07-22-lc", spec)
        plan_dir = repo / "docs/superpowers/plans/2026-07-22-lc"
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", "seed"], check=True)

        archive_plan_dir(repo, plan_dir)
        assert not (repo / "docs/superpowers/journals/plans/2026-07-22-lc.md").exists()
        assert (repo / "docs/superpowers/implemented/journals/plans/2026-07-22-lc.md").exists()

    def test_archive_no_journal_is_noop(self, tmp_path: Path) -> None:
        from fr.archive import archive_plan_dir

        repo = _make_repo(tmp_path)
        spec = _make_spec(repo)
        _create_plan(repo, "2026-07-22-lc", spec)
        plan_dir = repo / "docs/superpowers/plans/2026-07-22-lc"
        (repo / "docs/superpowers/journals/plans/2026-07-22-lc.md").unlink()
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", "seed"], check=True)
        # No journal to move — must not raise.
        archive_plan_dir(repo, plan_dir)


class TestSpecJournalFollowsSpec:
    def test_spec_journal_moves_when_spec_archived(self, tmp_path: Path) -> None:
        from fr.archive import spec_archive_sweep

        repo = _make_repo(tmp_path)
        # A spec is "fully implemented" when every plan row is non-blocking; a
        # manual row (File cell `—`) never blocks, so this spec qualifies for
        # the sweep.
        spec = repo / "docs/superpowers/specs/2026-05-10-solo.md"
        spec.write_text(
            "# Solo spec\n\n"
            "## Implementation Plans\n\n"
            "| Plan | Repo | File | Depends on |\n"
            "|------|------|------|------------|\n"
            "| Manual step | `derio-net/test` | — | — |\n"
        )
        sjournal = repo / "docs/superpowers/journals/specs/2026-05-10-solo.md"
        sjournal.parent.mkdir(parents=True, exist_ok=True)
        sjournal.write_text("# Journal: 2026-05-10-solo\n")
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", "seed"], check=True)

        result = spec_archive_sweep(repo, gh=None)
        moved_specs = [m for m in result.moves if m.kind == "spec"]
        assert moved_specs, "spec with no open plan rows should archive"
        assert not sjournal.exists()
        assert (repo / "docs/superpowers/implemented/journals/specs/2026-05-10-solo.md").exists()
        assert spec  # spec fixture used

    def test_spec_journal_moves_for_design_named_spec(self, tmp_path: Path) -> None:
        """Regression for #417: real specs are named `<slug>-design.md`, but the
        spec-scope journal is keyed by the bare `<slug>`. The sweep must strip
        the `-design` suffix — the prior test used a suffix-less fixture name, so
        the slug mismatch never surfaced and journals were left behind."""
        from fr.archive import spec_archive_sweep

        repo = _make_repo(tmp_path)
        spec = repo / "docs/superpowers/specs/2026-05-10-widget-design.md"
        spec.write_text(
            "# Widget spec\n\n"
            "## Implementation Plans\n\n"
            "| Plan | Repo | File | Depends on |\n"
            "|------|------|------|------------|\n"
            "| Manual step | `derio-net/test` | — | — |\n"
        )
        # Journal keyed by the bare slug, NOT the `-design` filename stem.
        sjournal = repo / "docs/superpowers/journals/specs/2026-05-10-widget.md"
        sjournal.parent.mkdir(parents=True, exist_ok=True)
        sjournal.write_text("# Journal: 2026-05-10-widget\n")
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", "seed"], check=True)

        result = spec_archive_sweep(repo, gh=None)
        assert [m for m in result.moves if m.kind == "spec"], "design-named spec should archive"
        assert not sjournal.exists(), "the bare-slug journal must move with its spec"
        assert (repo / "docs/superpowers/implemented/journals/specs/2026-05-10-widget.md").exists()

    def test_spec_without_journal_is_noop(self, tmp_path: Path) -> None:
        """Back-compat: a spec that never had a journal archives cleanly."""
        from fr.archive import spec_archive_sweep

        repo = _make_repo(tmp_path)
        spec = repo / "docs/superpowers/specs/2026-05-10-bare-design.md"
        spec.write_text(
            "# Bare spec\n\n"
            "## Implementation Plans\n\n"
            "| Plan | Repo | File | Depends on |\n"
            "|------|------|------|------------|\n"
            "| Manual step | `derio-net/test` | — | — |\n"
        )
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", "seed"], check=True)

        result = spec_archive_sweep(repo, gh=None)
        assert [m for m in result.moves if m.kind == "spec"], "spec should still archive"
