"""Unit tests for the `fr journal` CLI (Phase 2): add / render / check.

Spec §A: append-only writes, duplicate-id refusal, PR-body render sections,
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
        #
        # Normalize whitespace first: rich soft-wraps stderr to the terminal
        # width, so matching raw output pins the assertion to an 80-column
        # terminal and goes red on any shell that exports COLUMNS. Verified:
        # at COLUMNS=70 this test failed before normalizing. Same idiom and
        # same reason as test_v2_pickup.py and test_plan_acceptance_links.py.
        flat = " ".join(res.output.split())
        assert "renders in full in every handoff, at every phase" in flat
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
        # Substance, not just exit code — the sibling test above sets that bar
        # and this one used to fall short of it: replacing the whole message
        # body with "nope" left every test in this file green.
        flat = " ".join(res.output.split())
        assert "--phase and --global are contradictory" in flat
        assert not _journal_file(root, "S").exists()

    def test_global_is_refused_outside_plan_scope(self, tmp_path: Path, monkeypatch) -> None:
        """`--global` used to be a silent no-op on spec/debug, so
        `--phase 3 --global` wrote a phase-3-tagged entry while the operator
        had asked for a global one. A plan-only flag that cannot apply is
        refused rather than ignored."""
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
            "--global",
        )
        assert res.exit_code == 2, res.output
        flat = " ".join(res.output.split())
        assert "--global applies to --scope plan only" in flat

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


class TestCheckRequireReviews:
    """`fr journal check --require-reviews`: its argument grammar, its
    refusals, and the gate itself.

    The gate fails when a phase the plan LOCALLY claims is done
    (`fr.render.plan_locally_complete` — `completion.at` set, or every step
    ticked) carries no `kind=review` journal entry naming it. Manual-tagged
    phases are exempt (spec D4) and the exemption is stated in the failure
    message rather than applied silently.

    (This docstring described the flag as unimplemented until review r-p2-f3
    — the same stale-disclaimer shape the gate's own source comment was
    deleted for one step earlier.)"""

    def _seed_open_finding(self, slug: str, finding_id: str = "f1") -> None:
        """Give `slug`'s journal one OPEN finding.

        Without this, every slug — right, wrong or empty — resolves to a
        journal with no findings and exits 0, so a derivation test passes even
        with the derivation completely broken (review r-p1-f2 proved it by
        mutation). Seeding a finding under the EXPECTED slug is what makes
        "exit 1, and this id in the output" evidence that the right journal
        was read.
        """
        res = runner.invoke(
            app,
            [
                "journal", "add", "--scope", "plan", "--slug", slug,
                "--kind", "finding", "--id", finding_id, "--state", "open",
                "--title", "seeded", "--body", "b",
                # Plan-scope `add` refuses an untagged entry (gh#464: `--phase N`
                # or `--global`). The seeded finding belongs to no phase — it
                # exists to prove WHICH journal was read — so it says so.
                "--global",
            ],
        )  # fmt: skip
        assert res.exit_code == 0, res.output

    def _write_plan(self, root: Path, slug: str):
        """One trivial agentic phase — the degenerate case of
        `_write_plan_phases` (review r-p2-f7)."""
        from fr.plan_ops import PhaseSpec

        return self._write_plan_phases(root, slug, [PhaseSpec(number=1, title="One", tasks=())])

    def _write_plan_phases(self, root: Path, slug: str, phases):
        from fr.plan_ops import create

        (root / "docs" / "superpowers" / "specs").mkdir(parents=True, exist_ok=True)
        create(
            repo_root=root,
            slug=slug,
            spec=None,
            target_repo="derio-net/test",
            fr_version=">=3.0.0,<5.0.0",
            phases=phases,
            prose="# x\n",
        )
        return root / "docs" / "superpowers" / "plans" / slug

    def test_require_reviews_is_inert_when_all_phases_incomplete(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """No phase is locally complete, so none is OWED a review — exit 0
        with the flag on, exactly as without it.

        Paired with `test_require_reviews_fails_on_a_completed_phase_with_no_review`
        below on a COMPLETED phase of the same shape, per review r-p1-f2: that
        counterpart is what proves the flag is doing real work here rather than
        the gate being unbuilt (or broken) and every phase happening to look
        incomplete.
        """
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        self._write_plan(root, "RR1")

        res = runner.invoke(
            app,
            ["journal", "check", "--scope", "plan", "--slug", "RR1", "--require-reviews"],
        )

        assert res.exit_code == 0, res.output

    def test_require_reviews_refuses_non_plan_scope(self, tmp_path: Path, monkeypatch) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)

        res = runner.invoke(
            app,
            ["journal", "check", "--scope", "spec", "--slug", "S", "--require-reviews"],
        )

        assert res.exit_code == 2, res.output
        # Mirrors the refusal `fr journal handoff` already uses for the same
        # condition (only plan journals have phases) — not a second phrasing.
        assert "only plan journals have phases" in res.output

    def test_plan_dir_without_slug_derives_slug_from_basename(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        self._write_plan(root, "RR2")
        self._seed_open_finding("RR2")

        res = runner.invoke(
            app,
            [
                "journal",
                "check",
                "--scope",
                "plan",
                "--plan-dir",
                "docs/superpowers/plans/RR2",
            ],
        )

        # Exit 1 naming the seeded finding proves RR2's journal was the one
        # read. A bare `exit_code == 0` would also pass if the derivation
        # produced "TOTALLY-WRONG-SLUG", or "" — which is how the fail-open
        # in r-p1-f1 survived.
        assert res.exit_code == 1, res.output
        assert "f1" in res.output

    def test_slug_without_plan_dir_still_works(self, tmp_path: Path, monkeypatch) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        self._write_plan(root, "RR3")
        self._seed_open_finding("RR3", "f3")

        res = runner.invoke(app, ["journal", "check", "--scope", "plan", "--slug", "RR3"])

        assert res.exit_code == 1, res.output
        assert "f3" in res.output

    def test_a_plan_dir_with_no_final_component_is_refused_not_silently_passed(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """`--plan-dir .` must not fail OPEN (review r-p1-f1).

        `Path(".").name` is `""`, and an empty slug resolves
        `journals/plans/.md`, which does not exist, which reads as an empty
        journal — so the command used to exit 0 having checked nothing, INCLUDING
        the pre-existing open-findings rule. Found live: on a plan whose journal
        carried four open findings, `--slug` exited 1 and `--plan-dir .` exited 0.
        """
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        self._write_plan(root, "RR5")
        self._seed_open_finding("RR5", "f5")

        for bad in (".", "", "docs/superpowers/plans/RR5/.."):
            res = runner.invoke(
                app,
                ["journal", "check", "--scope", "plan", "--plan-dir", bad, "--require-reviews"],
            )
            # Exit 2 (refused), never 0 (silently passed). Exit 1 would also be
            # acceptable behaviour but is not what this refusal does.
            assert res.exit_code == 2, f"--plan-dir {bad!r} -> {res.exit_code}: {res.output}"

    def test_scope_refusal_beats_a_missing_slug(self, tmp_path: Path, monkeypatch) -> None:
        """The scope objection is reported first (review r-p1-f3).

        `--require-reviews --scope spec` is unsatisfiable whatever slug is
        supplied, so complaining about the missing slug would send the operator
        to fix the wrong thing and learn the real objection one run later.
        """
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)

        res = runner.invoke(app, ["journal", "check", "--scope", "spec", "--require-reviews"])

        assert res.exit_code == 2, res.output
        assert "only plan journals have phases" in res.output
        assert "--slug" not in res.output

    def test_plan_dir_is_refused_outside_plan_scope(self, tmp_path: Path, monkeypatch) -> None:
        """`--plan-dir` names a plan (review r-p1-f6).

        Accepted under `--scope spec` it would quietly derive a slug and check
        a SPEC journal named after that plan folder — a different file than the
        operator asked about, reported as a clean pass.
        """
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)

        res = runner.invoke(
            app,
            ["journal", "check", "--scope", "spec", "--plan-dir", "docs/superpowers/plans/RR6"],
        )

        assert res.exit_code == 2, res.output
        assert "--plan-dir" in res.output

    def test_slug_wins_when_both_are_given(self, tmp_path: Path, monkeypatch) -> None:
        """An explicit `--slug` is not overridden by `--plan-dir`'s basename.

        Unpinned until now (review r-p1-f6), and about to become observable:
        once the gate lands, a disagreeing pair reads the journal from one
        place and the phases from another, so which one names the journal must
        be a decision the suite holds, not an accident of argument order.
        """
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        self._write_plan(root, "RR7")
        self._seed_open_finding("RR7", "f7")

        res = runner.invoke(
            app,
            [
                "journal", "check", "--scope", "plan", "--slug", "RR7",
                "--plan-dir", "docs/superpowers/plans/SOMETHING-ELSE",
            ],
        )  # fmt: skip

        assert res.exit_code == 1, res.output
        assert "f7" in res.output

    def test_neither_slug_nor_plan_dir_exits_2_naming_both(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)

        res = runner.invoke(app, ["journal", "check", "--scope", "plan"])

        assert res.exit_code == 2, res.output
        assert "--slug" in res.output
        assert "--plan-dir" in res.output

    def test_without_require_reviews_completed_unreviewed_phase_still_exits_zero(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Back-compat (spec D2): `fr journal check --scope plan` behaves
        exactly as it did before the flag existed, even for a phase the plan
        claims is done with no review entry naming it — the assertion a later
        refactor is most likely to break silently."""
        from fr.plan_ops import complete_phase

        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        plan_dir = self._write_plan(root, "RR4")
        complete_phase(plan_dir, 1)

        res = runner.invoke(app, ["journal", "check", "--scope", "plan", "--slug", "RR4"])

        assert res.exit_code == 0, res.output

    def test_require_reviews_fails_on_a_completed_phase_with_no_review(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """P2.T2.S1(a): a locally-complete agentic phase with no `review`
        entry naming it fails, and the message names the phase number."""
        from fr.plan_ops import complete_phase

        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        plan_dir = self._write_plan(root, "RR8")
        complete_phase(plan_dir, 1)

        res = runner.invoke(
            app, ["journal", "check", "--scope", "plan", "--slug", "RR8", "--require-reviews"]
        )

        assert res.exit_code == 1, res.output
        assert "owed a review" in res.output
        assert "--phase 1" in res.output

    def test_require_reviews_passes_once_the_phase_is_reviewed(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """P2.T2.S1(b): the same phase, now with a `kind=review phase=1`
        entry recorded, passes."""
        from fr.plan_ops import complete_phase

        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        plan_dir = self._write_plan(root, "RR9")
        complete_phase(plan_dir, 1)
        add_res = runner.invoke(
            app,
            [
                "journal", "add", "--scope", "plan", "--slug", "RR9",
                "--kind", "review", "--phase", "1", "--id", "review-1",
                "--title", "phase 1 review", "--body", "no findings",
            ],
        )  # fmt: skip
        assert add_res.exit_code == 0, add_res.output

        res = runner.invoke(
            app, ["journal", "check", "--scope", "plan", "--slug", "RR9", "--require-reviews"]
        )

        assert res.exit_code == 0, res.output

    def test_every_step_ticked_but_completion_at_unset_is_still_owed_a_review(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """P2.T2.S1(c) — THE test this phase exists for.

        An agentic phase with every step ticked and `completion.at` UNSET
        still claims to be done under `plan_locally_complete`. Had the gate
        keyed on `completion.at` alone this phase would look incomplete and
        pass silently; had it keyed on `_phase_complete` it would ALSO pass
        silently, because `_phase_complete` additionally requires an observed
        merged PR that never exists during an fr-goal run (spec, "Which
        completion predicate, and why it matters"). This is the one test that
        distinguishes all three candidate predicates.
        """
        from fr.plan_ops import PhaseSpec, TaskSpec, tick

        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        plan_dir = self._write_plan_phases(
            root,
            "RR10",
            [
                PhaseSpec(
                    number=1,
                    title="One",
                    tasks=(
                        TaskSpec(
                            number=1,
                            title="T1",
                            steps=[{"id": "P1.T1.S1", "text": "do x"}],
                        ),
                    ),
                )
            ],
        )
        tick(plan_dir, "P1.T1.S1")

        res = runner.invoke(
            app, ["journal", "check", "--scope", "plan", "--slug", "RR10", "--require-reviews"]
        )

        assert res.exit_code == 1, res.output
        assert "owed a review" in res.output
        assert "--phase 1" in res.output

    def test_manual_phase_is_exempt_and_the_message_names_the_exemption(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """P2.T2.S1(d): a `[manual]` phase with `completion.at` set and no
        review is not owed one, and an unrelated failing agentic phase's
        message names the manual exemption (spec D4) so a reader is not left
        wondering why the manual phase is missing from the list."""
        from fr.plan_ops import PhaseSpec, complete_phase

        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        plan_dir = self._write_plan_phases(
            root,
            "RR11",
            [
                PhaseSpec(number=1, title="Agentic", tasks=()),
                PhaseSpec(number=2, title="Manual", tag="manual", tasks=()),
            ],
        )
        complete_phase(plan_dir, 1)
        complete_phase(plan_dir, 2, note="operator did this by hand")

        res = runner.invoke(
            app, ["journal", "check", "--scope", "plan", "--slug", "RR11", "--require-reviews"]
        )

        assert res.exit_code == 1, res.output
        assert "--phase 1" in res.output
        assert "--phase 2" not in res.output
        assert "manual" in res.output.lower()

    def test_a_nonexistent_plan_dir_is_refused_not_silently_passed(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """P2.T2.S1(e), first half: the plan dir doesn't exist. Fail-closed."""
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        runner.invoke(
            app,
            [
                "journal", "add", "--scope", "plan", "--slug", "RR12",
                "--kind", "discovery", "--title", "x", "--id", "d1",
            ],
        )  # fmt: skip

        res = runner.invoke(
            app,
            [
                "journal", "check", "--scope", "plan", "--slug", "RR12",
                "--plan-dir", "docs/superpowers/plans/RR12-does-not-exist",
                "--require-reviews",
            ],
        )  # fmt: skip

        assert res.exit_code == 2, res.output

    def test_a_plan_dir_that_does_not_parse_is_refused_not_silently_passed(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """P2.T2.S1(e), second half: the plan dir exists but has no
        `_meta.yaml` (not a v2 plan) — `parse` raises `PlanSchemaError`, and
        the gate must fail closed rather than treat it as zero phases."""
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        empty_dir = root / "docs" / "superpowers" / "plans" / "RR13-empty"
        empty_dir.mkdir(parents=True)
        runner.invoke(
            app,
            [
                "journal", "add", "--scope", "plan", "--slug", "RR13",
                "--kind", "discovery", "--title", "x", "--id", "d1",
            ],
        )  # fmt: skip

        res = runner.invoke(
            app,
            [
                "journal", "check", "--scope", "plan", "--slug", "RR13",
                "--plan-dir", "docs/superpowers/plans/RR13-empty",
                "--require-reviews",
            ],
        )  # fmt: skip

        assert res.exit_code == 2, res.output

    def test_the_fail_closed_diagnostic_is_not_eaten_by_rich_markup(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Pydantic's error text must reach the operator intact
        (review r-p2-f4).

        A validation error ends in `[type=missing, input_value=..., input_type=
        dict]` — the most diagnostic half of it. Rich parses `[...]` as a style
        tag and SILENTLY DROPS it, so a fail-closed exit 2 would name the file
        and then withhold the reason. `markup=False` is what keeps it; nothing
        pinned that, because the repo's other fail-closed tests raise errors
        with no brackets in them.
        """
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        bad = root / "docs" / "superpowers" / "plans" / "RR23"
        bad.mkdir(parents=True)
        # A `_meta.yaml` that parses as YAML but fails PlanMeta validation, so
        # the error carries pydantic's bracketed detail.
        (bad / "_meta.yaml").write_text("schema_version: 2\n")

        res = runner.invoke(
            app,
            [
                "journal", "check", "--scope", "plan", "--slug", "RR23",
                "--plan-dir", "docs/superpowers/plans/RR23", "--require-reviews",
            ],
        )  # fmt: skip

        assert res.exit_code == 2, res.output
        assert "not parseable" in res.output
        assert "[type=missing" in res.output, (
            "Rich ate the bracketed pydantic detail — the fail-closed exit "
            f"named the file but withheld the reason: {res.output!r}"
        )

    def test_composition_reports_both_open_findings_and_owed_reviews(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """P2.T2.S1(f): a journal with both an open finding and an unreviewed
        phase fails on both, and the open-findings line keeps its exact
        pre-existing wording, because things grep it."""
        from fr.plan_ops import complete_phase

        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        plan_dir = self._write_plan(root, "RR14")
        complete_phase(plan_dir, 1)
        self._seed_open_finding("RR14", "f14")

        res = runner.invoke(
            app, ["journal", "check", "--scope", "plan", "--slug", "RR14", "--require-reviews"]
        )

        assert res.exit_code == 1, res.output
        assert "1 open finding(s): f14" in res.output
        assert "--phase 1" in res.output
        # The source comment claims the open-findings line prints FIRST and
        # always; nothing asserted it until review r-p2-f6. Membership alone
        # would pass with the two gates' output interleaved or reordered.
        assert res.output.index("open finding(s)") < res.output.index("owed a review")

    def test_a_plan_with_no_recognised_phase_files_is_refused_not_passed(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """A vacuous pass is a fail-open (review r-p2-f1).

        `fr.parser.parse` silently ignores any file not matching `NN.yaml`, so
        a phase file misnamed `1.yaml` (or `02.yml`, or `phase-02.yaml`) makes
        `plan.phases` empty — and a plan holding a real, COMPLETE, UNREVIEWED
        phase would then exit 0 with no output at all. That is the state the
        spec's Background condemns: satisfaction and violation looking the
        same. Refuse instead, per §B's fail-closed rule.
        """
        from fr.plan_ops import complete_phase

        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        plan_dir = self._write_plan(root, "RR20")
        complete_phase(plan_dir, 1)
        # Misname the phase file exactly as a careless hand-edit would.
        (plan_dir / "01.yaml").rename(plan_dir / "1.yaml")

        res = runner.invoke(
            app, ["journal", "check", "--scope", "plan", "--slug", "RR20", "--require-reviews"]
        )

        assert res.exit_code == 2, res.output
        assert "no phase files" in res.output

    def test_the_remediation_command_is_not_wrapped_across_lines(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """The failure message ends in a command meant to be pasted
        (review r-p2-f2).

        Rich folds at the terminal width in any non-TTY — a pipe, CI, or
        `fr run advance` running the `kind: cli` step, which is exactly the
        consumer the cursor-enforced gate was designed for. Folded, the one
        command pastes as three broken ones.

        `COLUMNS` is set NARROW here, deliberately. conftest's autouse
        `_wide_terminal` fixture pins every CLI test at 200 columns so path
        assertions stop depending on how long `tmp_path` happens to be — and
        that wide default silently disables any test *about* wrapping. Written
        without this override, this test passed with `soft_wrap` removed
        (mutation-verified), i.e. it asserted nothing. conftest names this
        override as the supported escape.
        """
        from fr.plan_ops import complete_phase

        monkeypatch.setenv("COLUMNS", "80")
        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        plan_dir = self._write_plan(root, "RR21-a-deliberately-long-slug-to-force-the-fold")
        complete_phase(plan_dir, 1)

        res = runner.invoke(
            app,
            [
                "journal", "check", "--scope", "plan",
                "--slug", "RR21-a-deliberately-long-slug-to-force-the-fold",
                "--require-reviews",
            ],
        )  # fmt: skip

        assert res.exit_code == 1, res.output
        command_lines = [ln for ln in res.output.splitlines() if "fr journal add" in ln]
        assert len(command_lines) == 1, res.output
        line = command_lines[0]
        for fragment in ("--scope plan", "--kind review", "--phase 1", "--title", "--body"):
            assert fragment in line, f"{fragment!r} fell off the command line: {line!r}"

    def test_an_unreadable_plan_file_is_fail_closed(self, tmp_path: Path, monkeypatch) -> None:
        """The `OSError` arm of the fail-closed except was unpinned
        (review r-p2-f5): narrowing it to `PlanSchemaError` alone left every
        test green, because both existing fail-closed tests raise
        `PlanSchemaError`. `fr.parser` reads the PHASE files outside its own
        try-block (`parser.py:201`), so `OSError` is reachable there — whereas
        `_meta.yaml` is read INSIDE it and surfaces as `PlanSchemaError`. The
        first version of this test broke `_meta.yaml` and so exercised the very
        arm it was written to pin nothing about."""
        from fr.plan_ops import complete_phase

        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        plan_dir = self._write_plan(root, "RR22")
        complete_phase(plan_dir, 1)
        # A DIRECTORY named `01.yaml` still matches the phase-file regex
        # (which matches on the name), so `parse` reaches `read_text` and
        # raises IsADirectoryError — an OSError, not a PlanSchemaError.
        (plan_dir / "01.yaml").unlink()
        (plan_dir / "01.yaml").mkdir()

        res = runner.invoke(
            app, ["journal", "check", "--scope", "plan", "--slug", "RR22", "--require-reviews"]
        )

        assert res.exit_code == 2, res.output
        assert "not parseable" in res.output

    def test_a_resolved_finding_does_not_resurface_under_require_reviews(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """P2.T2.S1(g): a finding closed by `fr journal resolve` must not
        resurface — the new gate must not have bypassed `open_finding_ids`'
        fold to get its answer."""
        from fr.plan_ops import complete_phase

        root = _init_repo(tmp_path)
        monkeypatch.chdir(root)
        plan_dir = self._write_plan(root, "RR15")
        complete_phase(plan_dir, 1)
        self._seed_open_finding("RR15", "f15")
        resolve_res = runner.invoke(
            app,
            [
                "journal", "resolve", "--scope", "plan", "--slug", "RR15",
                "--id", "f15", "--state", "fixed", "--note", "fixed it",
            ],
        )  # fmt: skip
        assert resolve_res.exit_code == 0, resolve_res.output
        runner.invoke(
            app,
            [
                "journal", "add", "--scope", "plan", "--slug", "RR15",
                "--kind", "review", "--phase", "1", "--id", "review-1",
                "--title", "phase 1 review", "--body", "no findings",
            ],
        )  # fmt: skip

        res = runner.invoke(
            app, ["journal", "check", "--scope", "plan", "--slug", "RR15", "--require-reviews"]
        )

        assert res.exit_code == 0, res.output


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


class TestResolveDeferred:
    """`--state deferred --tracked-by <issue>`: a finding that is VALID but not
    this change's to fix. With only fixed | refuted available, such findings
    were closed as "refuted" to satisfy the gate — which says the finding was
    wrong when it was not (super-fr#535 was closed that way, then corrected by
    hand). A deferral must name where the work lives, so it cannot become a
    quiet way to drop a finding."""

    def _open(self, root: Path, monkeypatch) -> None:
        TestResolve._open_finding(self, root, monkeypatch)  # type: ignore[arg-type]

    def _resolve(self, *args: str):
        return runner.invoke(
            app, ["journal", "resolve", "--scope", "plan", "--slug", "S", "--id", "f1", *args]
        )

    def test_deferred_requires_tracked_by(self, tmp_path: Path, monkeypatch) -> None:
        root = _init_repo(tmp_path)
        self._open(root, monkeypatch)
        before = _journal_file(root, "S").read_text()
        res = self._resolve("--state", "deferred", "--note", "later")
        assert res.exit_code == 2
        assert "--tracked-by" in res.output
        assert _journal_file(root, "S").read_text() == before

    def test_tracked_by_is_only_for_a_deferral(self, tmp_path: Path, monkeypatch) -> None:
        root = _init_repo(tmp_path)
        self._open(root, monkeypatch)
        res = self._resolve("--state", "fixed", "--tracked-by", "#9", "--note", "x")
        assert res.exit_code == 2
        assert "deferred" in res.output

    @pytest.mark.parametrize("ref", ["", "soon", "#", "#12 later", "issue 12"])
    def test_tracked_by_must_name_an_issue(self, tmp_path: Path, monkeypatch, ref: str) -> None:
        root = _init_repo(tmp_path)
        self._open(root, monkeypatch)
        res = self._resolve("--state", "deferred", "--tracked-by", ref, "--note", "x")
        assert res.exit_code == 2, res.output

    @pytest.mark.parametrize(
        "ref",
        ["#535", "derio-net/super-fr#535", "https://github.com/derio-net/super-fr/issues/535"],
    )
    def test_a_deferral_closes_the_gate_and_says_where_it_went(
        self, tmp_path: Path, monkeypatch, ref: str
    ) -> None:
        from fr.journal.model import parse_journal

        root = _init_repo(tmp_path)
        self._open(root, monkeypatch)
        res = self._resolve("--state", "deferred", "--tracked-by", ref, "--note", "valid; later")
        assert res.exit_code == 0, res.output

        entries = parse_journal(_journal_file(root, "S").read_text())
        record = next(e for e in entries if e.resolves == "f1")
        # Written as `open` + a token: an older fr ignores the token and reads the
        # finding as still open (fails closed), never as closed and never as a
        # parse error. The in-memory fold is what reads it as deferred.
        assert record.state == "open" and record.tracked_by == ref

        check = runner.invoke(app, ["journal", "check", "--scope", "plan", "--slug", "S"])
        assert check.exit_code == 0, check.output
        assert "deferred" in check.output and ref in check.output, "said, not hidden"

        render = runner.invoke(
            app, ["journal", "render", "--scope", "plan", "--slug", "S", "--section", "findings"]
        )
        assert f"[deferred → {ref}]" in render.output

    def test_a_later_record_still_wins(self, tmp_path: Path, monkeypatch) -> None:
        root = _init_repo(tmp_path)
        self._open(root, monkeypatch)
        self._resolve("--state", "deferred", "--tracked-by", "#9", "--note", "later")
        reopen = runner.invoke(
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
                "back in scope",
                "--state",
                "open",
                "--resolves",
                "f1",
                "--phase",
                "1",
            ],
        )
        assert reopen.exit_code == 0, reopen.output
        check = runner.invoke(app, ["journal", "check", "--scope", "plan", "--slug", "S"])
        assert check.exit_code == 1, "re-opened after a deferral: open again"
        self._resolve("--state", "fixed", "--note", "done after all")
        check = runner.invoke(app, ["journal", "check", "--scope", "plan", "--slug", "S"])
        assert check.exit_code == 0
