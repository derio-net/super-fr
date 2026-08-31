"""The obligatory trigger at CLI entry, context-aware (spec §3.C).

A callback runs before *every* `fr` command. If any live artifact is stale it
either migrates (interactive: the operator's "pause, migrate, resume", where
the pause is invisible because the typed command still runs) or refuses loudly
and exits non-zero (daemon / CI). It must **never** auto-commit in the second
case: the bridge `reset --hard`s its checkout to `origin/main` every tick
(#286), so a commit there is discarded on the next pass — pointless *and*
actively misleading.

Two things this file guards that are easy to lose:

1. **The exemption list is exactly four things.** An over-broad exemption
   silently disables the whole mechanism, and it would disable it in the
   quietest possible way — everything keeps working, nothing migrates.
2. **The gate never lets a traceback out.** `is_stale` raises
   `MigrationChainError` on an artifact no migration moves; a gate that lets
   that escape turns a registry bug into a crash in an unrelated command.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pytest
import typer
from fr.artifacts import trigger
from fr.artifacts.registry import ARTIFACT_KINDS, ArtifactKind
from fr.artifacts.runner import MigrationRegistry, SchemaMigration
from fr.cli import app
from typer.testing import CliRunner

runner_cli = CliRunner()


# --- fixtures ------------------------------------------------------------


def _plan(root: Path, slug: str = "p", *, fr_version: str = ">=3.0.0,<4.0.0") -> Path:
    """A live plan whose `fr_version` ceiling excludes this fr — i.e. stale."""
    d = root / "docs" / "superpowers" / "plans" / slug
    d.mkdir(parents=True, exist_ok=True)
    p = d / "_meta.yaml"
    p.write_text(
        f"schema_version: 2\nplan: {slug}\ntarget_repo: derio-net/super-fr\n"
        f"fr_version: '{fr_version}'\n"
    )
    return p


class _Stream:
    def __init__(self, tty: bool) -> None:
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


GATED_COMMAND = ["models", "get", "--harness", "claude-code"]
"""An ordinary, non-exempt command that prints something identifiable."""


def _tty() -> _Stream:
    return _Stream(True)


def _pipe() -> _Stream:
    return _Stream(False)


def _gap_registry() -> MigrationRegistry:
    """A registry whose plan chain has a hole: version 2 -> 4 with no 2 -> 3."""
    kind: ArtifactKind = replace(ARTIFACT_KINDS["plan"], current_version=4)
    reg = MigrationRegistry(kinds={kind.name: kind})
    reg.register(SchemaMigration(kind="plan", from_version=3, to_version=4, fn=lambda p: None))
    return reg


# --- the exemption list --------------------------------------------------


def test_the_exemption_list_is_exactly_these_things() -> None:
    """Spec §3.C: "exemptions, narrow and explicit".

    Pinned as a literal rather than derived, because the failure mode of an
    extra entry is silence: every command keeps working and nothing ever
    migrates. Another exemption has to be argued for in a diff to this line.

    The read-only five were added by review r4-f5/r4-f11 and are a *narrowing*,
    not a widening: `fr status` is registered as "Read-only plan report
    (allowlist-safe; never mutates)" and was rewriting artifacts and creating
    commits, and `fr validate artifacts` could never report a stale artifact to
    a human because the gate migrated it away first.
    """
    assert trigger.EXEMPT_OPTIONS == frozenset({"--help", "--version"})
    assert trigger.EXEMPT_COMMANDS == frozenset(
        {"migrate", "status", "skills", "isolation", "init", "validate"}
    )
    assert trigger.SKIP_ENV_VAR == "FR_SKIP_MIGRATION"
    assert trigger.EXEMPTIONS == (
        "--help",
        "--version",
        "migrate",
        "status",
        "skills",
        "isolation",
        "init",
        "validate",
        "FR_SKIP_MIGRATION=1",
    )


def test_a_read_only_command_never_migrates_or_commits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """r4-f5 / r4-f11. Each of these either promises not to mutate, or is the
    diagnostic whose whole job is to REPORT the state the gate would silently
    repair. None of them may rewrite an artifact or write to git history."""
    _plan(tmp_path)  # stale
    ran: list[int] = []
    monkeypatch.setattr(trigger, "is_stale", lambda *a, **k: ran.append(1) or True)
    for command in ("status", "skills", "isolation", "init", "validate"):
        trigger.ensure_artifacts_current(
            argv=[command],
            invoked_subcommand=command,
            env={},
            repo_root=tmp_path,
            interactive=True,
        )
    assert ran == [], "an exempt command must not even look at the tree"


def test_help_and_version_are_exempt_wherever_they_appear() -> None:
    for argv in (["--version"], ["--help"], ["plan", "--help"], ["plan", "create", "--help"]):
        assert trigger.is_exempt(argv=argv, invoked_subcommand=argv[0], env={}), argv


def test_migrate_cannot_require_itself() -> None:
    assert trigger.is_exempt(argv=["migrate", "artifacts"], invoked_subcommand="migrate", env={})


def test_a_migrate_shaped_argument_to_another_command_is_not_exempt() -> None:
    """The exemption is the *command*, not the word appearing anywhere."""
    assert not trigger.is_exempt(argv=["pickup", "migrate"], invoked_subcommand="pickup", env={})


def test_fr_skip_migration_exempts_and_zero_does_not() -> None:
    assert trigger.is_exempt(
        argv=["apply"], invoked_subcommand="apply", env={"FR_SKIP_MIGRATION": "1"}
    )
    assert not trigger.is_exempt(
        argv=["apply"], invoked_subcommand="apply", env={"FR_SKIP_MIGRATION": "0"}
    )
    assert not trigger.is_exempt(
        argv=["apply"], invoked_subcommand="apply", env={"FR_SKIP_MIGRATION": ""}
    )


def test_an_ordinary_command_is_not_exempt() -> None:
    assert not trigger.is_exempt(argv=["apply"], invoked_subcommand="apply", env={})
    assert not trigger.is_exempt(argv=["plan", "edit"], invoked_subcommand="plan", env={})


# --- context detection ---------------------------------------------------


def test_ci_is_never_interactive() -> None:
    assert not trigger.is_interactive(env={"CI": "true"}, stdin=_tty(), stdout=_tty())
    assert not trigger.is_interactive(env={"CI": "1"}, stdin=_tty(), stdout=_tty())


def test_an_empty_ci_reads_as_unset() -> None:
    assert trigger.is_interactive(env={"CI": ""}, stdin=_tty(), stdout=_tty())


def test_no_tty_is_never_interactive() -> None:
    """The daemon and every CI runner land here even with `CI` unset."""
    assert not trigger.is_interactive(env={}, stdin=_pipe(), stdout=_tty())
    assert not trigger.is_interactive(env={}, stdin=_tty(), stdout=_pipe())


def test_a_tty_without_ci_is_interactive() -> None:
    assert trigger.is_interactive(env={}, stdin=_tty(), stdout=_tty())


def test_a_stream_that_cannot_answer_is_not_interactive() -> None:
    """Prefer refusing: an unanswerable question is not a yes."""

    class _Broken:
        def isatty(self) -> bool:
            raise ValueError("detached")

    assert not trigger.is_interactive(env={}, stdin=_Broken(), stdout=_tty())


# --- the gate ------------------------------------------------------------


def test_an_exempt_invocation_never_even_looks_at_the_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cheapness is part of the contract: this runs before every command."""
    _plan(tmp_path)
    looked = []
    monkeypatch.setattr(trigger, "is_stale", lambda *a, **k: looked.append(1) or True)
    trigger.ensure_artifacts_current(
        argv=["migrate", "artifacts"],
        invoked_subcommand="migrate",
        env={},
        repo_root=tmp_path,
    )
    assert looked == []


def test_a_current_tree_neither_migrates_nor_commits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`is_stale` short-circuits; nothing else may walk the tree behind it."""
    _plan(tmp_path, fr_version=">=4.0.0,<5.0.0")
    ran, committed = [], []
    monkeypatch.setattr(trigger, "run_migrations", lambda *a, **k: ran.append(1))
    monkeypatch.setattr(trigger, "commit_migration", lambda *a, **k: committed.append(1))
    trigger.ensure_artifacts_current(
        argv=["apply"], invoked_subcommand="apply", env={}, repo_root=tmp_path, interactive=True
    )
    assert ran == [] and committed == []


def test_interactive_migrates_commits_and_returns(tmp_path: Path) -> None:
    """Migrate, commit, continue — returning is how the typed command resumes."""
    p = _plan(tmp_path)
    committed: list[object] = []
    trigger.ensure_artifacts_current(
        argv=["apply"],
        invoked_subcommand="apply",
        env={},
        repo_root=tmp_path,
        interactive=True,
        commit=lambda root, report: committed.append(report),
    )
    assert "<5.0.0" in p.read_text()
    assert len(committed) == 1


def test_non_interactive_refuses_without_migrating_or_committing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The single highest-value behaviour in the spec: a loud refusal."""
    p = _plan(tmp_path)
    before = p.read_text()
    committed: list[object] = []
    with pytest.raises(typer.Exit) as e:
        trigger.ensure_artifacts_current(
            argv=["apply"],
            invoked_subcommand="apply",
            env={"CI": "true"},
            repo_root=tmp_path,
            interactive=False,
            commit=lambda root, report: committed.append(report),
        )
    assert e.value.exit_code != 0
    assert p.read_text() == before, "a non-interactive context must never migrate"
    assert committed == [], "a non-interactive context must never commit"
    out = capsys.readouterr()
    assert "fr migrate artifacts" in out.err, "the refusal must name the command to run"
    assert trigger.SKIP_ENV_VAR in out.err


def test_a_chain_gap_refuses_instead_of_escaping_as_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`is_stale` raises on a gap; a gate that lets it out crashes `fr status`."""
    _plan(tmp_path)
    with pytest.raises(typer.Exit) as e:
        trigger.ensure_artifacts_current(
            argv=["apply"],
            invoked_subcommand="apply",
            env={},
            repo_root=tmp_path,
            interactive=True,
            registry=_gap_registry(),
        )
    assert e.value.exit_code == 2
    assert "chain" in capsys.readouterr().err.lower()


def test_a_half_migrated_tree_is_exit_two_not_a_silent_pass(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A malformed constraint is reported, never rewritten — and never ignored.

    Two plans: one the repair can widen, one whose constraint it refuses to
    guess at. The good one migrates (so `is_stale` said yes and the runner
    ran), the bad one lands in `report.failed`, and the gate refuses to let the
    command run over the resulting half-migrated tree.
    """
    good = _plan(tmp_path, "good")
    bad = _plan(tmp_path, "bad", fr_version="not a specifier")
    with pytest.raises(typer.Exit) as e:
        trigger.ensure_artifacts_current(
            argv=["apply"],
            invoked_subcommand="apply",
            env={},
            repo_root=tmp_path,
            interactive=True,
            commit=lambda root, report: None,
        )
    assert e.value.exit_code == 2
    assert "<5.0.0" in good.read_text(), "one bad artifact must not stop the others"
    assert "not a specifier" in bad.read_text(), "a constraint fr cannot parse is never rewritten"
    assert "FAILED" in capsys.readouterr().err


# --- wired into the real app ---------------------------------------------
#
# The callback reads the *process* argv for the `--help` / `--version` tokens,
# because click's group context does not expose the subcommand's own arguments
# (`ctx.args` is empty by the time the group callback runs, verified on click
# 8.3). These tests therefore set `sys.argv` to what the operator would have
# typed rather than leaving pytest's argv in place.


def _invoke(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, argv: list[str], *, interactive: bool = True
):
    # `conftest._skip_artifact_migration_gate` sets FR_SKIP_MIGRATION for the
    # whole suite; these are the invocations that must actually see the gate,
    # so it goes away here. `CliRunner(env=...)` *updates* os.environ rather
    # than replacing it, which is why this is a delenv and not an omission.
    monkeypatch.delenv("FR_SKIP_MIGRATION", raising=False)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setattr(sys, "argv", ["fr", *argv])
    monkeypatch.setattr(trigger, "is_interactive", lambda **k: interactive)
    monkeypatch.setattr(trigger, "commit_migration", lambda root, report: None)
    return runner_cli.invoke(app, argv, env={"VK_REPO_ROOT": str(tmp_path)})


def test_the_callback_runs_before_the_invoked_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Interactive: the migration happens and the typed command still prints.

    `fr models get` and not `fr skills`: `skills` is read-only and therefore
    exempt from the gate now (review r4-f5/r4-f11), so it would prove nothing.
    """
    p = _plan(tmp_path)
    result = _invoke(monkeypatch, tmp_path, GATED_COMMAND)
    assert result.exit_code == 0, result.output
    assert "<5.0.0" in p.read_text()
    assert "claude-code" in result.output, "the typed command must still run"


def test_the_callback_refuses_the_command_in_ci(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = _plan(tmp_path)
    before = p.read_text()
    result = _invoke(monkeypatch, tmp_path, GATED_COMMAND, interactive=False)
    assert result.exit_code != 0
    assert p.read_text() == before
    assert "claude-code" not in result.output, "the command must not run on stale artifacts"


def test_the_callback_does_not_fire_for_migrate_itself(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`fr migrate artifacts --dry-run` must stay a preview, not a migration."""
    p = _plan(tmp_path)
    before = p.read_text()
    result = _invoke(monkeypatch, tmp_path, ["migrate", "artifacts"])
    assert result.exit_code == 0, result.output
    assert p.read_text() == before, "the entry callback migrated behind a dry-run"


def test_subcommand_help_is_exempt_at_the_app_level(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`fr plan --help` reaches the callback (top-level `--help` does not)."""
    p = _plan(tmp_path)
    before = p.read_text()
    result = _invoke(monkeypatch, tmp_path, ["plan", "--help"])
    assert result.exit_code == 0, result.output
    assert p.read_text() == before, "asking for help migrated the tree"


# --- the offer of adoption (spec §3.E) -----------------------------------


def _in_flight_plan(root: Path, slug: str = "2019-03-04-thermosiphon-rebuild") -> Path:
    """A parseable, current, HALF-DONE plan — the adoption case."""
    d = root / "docs" / "superpowers" / "plans" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "_meta.yaml").write_text(
        f"schema_version: 2\nplan: {slug}\ntarget_repo: derio-net/super-fr\ncreated: 2019-03-04\n"
    )
    (d / "_prose.md").write_text("# Prose\n")
    for n, tick in ((1, "x"), (2, '" "')):
        (d / f"{n:02d}.yaml").write_text(
            f"schema_version: 2\nphase:\n  number: {n}\n  title: P{n}\n  tag: agentic\n"
            f"  depends_on: []\n  tracking_issue: null\n"
            f"tasks:\n  - number: 1\n    title: T\n    steps:\n"
            f"      - id: P{n}.T1.S1\n        text: s\n"
            f"state:\n  steps:\n    P{n}.T1.S1:\n      state: {tick}\n"
            f"      ticked_at: null\n      note: null\n"
            f"  completion:\n    at: null\n    note: null\n    observed_prs: []\n"
        )
    return d


def test_the_gate_reports_in_flight_plans_with_no_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Spec §3.E: the migration reports in-flight work that has no cursor, and
    names the command that gives it one."""
    _plan(tmp_path)  # something stale, so the gate does its work
    _in_flight_plan(tmp_path)

    trigger.ensure_artifacts_current(
        argv=["apply"],
        invoked_subcommand="apply",
        env={},
        repo_root=tmp_path,
        interactive=True,
        commit=lambda root, report: None,
    )

    err = capsys.readouterr().err
    assert "fr run adopt docs/superpowers/plans/2019-03-04-thermosiphon-rebuild" in err
    assert "not forced" in err


def test_the_gate_creates_no_run_of_its_own(tmp_path: Path) -> None:
    """The constraint that outranks the spec's wording: this callback fires
    before an UNRELATED command. An operator who typed `fr status` must not
    come back to new git-tracked files. Adoption is `fr run adopt` /
    `fr migrate artifacts --adopt`, both of which the operator typed on
    purpose."""
    _plan(tmp_path)
    _in_flight_plan(tmp_path)

    trigger.ensure_artifacts_current(
        argv=["apply"],
        invoked_subcommand="apply",
        env={},
        repo_root=tmp_path,
        interactive=True,
        commit=lambda root, report: None,
    )

    assert not (tmp_path / "docs" / "superpowers" / "runs").exists()


def test_a_complete_plan_is_not_offered_by_the_gate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The other direction — a cursor over finished work is noise."""
    _plan(tmp_path)
    plan_dir = _in_flight_plan(tmp_path)
    (plan_dir / "02.yaml").write_text((plan_dir / "02.yaml").read_text().replace('" "', "x"))

    trigger.ensure_artifacts_current(
        argv=["apply"],
        invoked_subcommand="apply",
        env={},
        repo_root=tmp_path,
        interactive=True,
        commit=lambda root, report: None,
    )

    assert "fr run adopt" not in capsys.readouterr().err


def test_the_non_interactive_refusal_does_not_reach_the_offer(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A refusal is a refusal: nothing migrated, so there is no "your fr
    changed under this work" moment to report an offer in."""
    _plan(tmp_path)
    _in_flight_plan(tmp_path)

    with pytest.raises(typer.Exit):
        trigger.ensure_artifacts_current(
            argv=["apply"],
            invoked_subcommand="apply",
            env={"CI": "true"},
            repo_root=tmp_path,
            interactive=False,
        )

    assert "fr run adopt" not in capsys.readouterr().err


# --- review r4-f4 / r4-f5 / r4-f2: what the gate must refuse -------------


def test_an_artifact_the_gate_cannot_inspect_is_refused_not_waved_through(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """r4-f4. This module's docstring promises "refusing rather than running
    over a tree of unknown state", but that only ever fired for exceptions that
    ESCAPED — and a stamp error or a raising repair predicate never escapes,
    it becomes a `FailedAction`. `is_stale` discarded those, so the single
    unreadable artifact below produced `stale=False` and the command ran.

    One plan, and it is the broken one: with a second, healthy-but-stale plan
    the old code passed by accident.
    """
    bad = _plan(tmp_path, "bad", fr_version="not a specifier")
    before = bad.read_text()
    committed: list[object] = []

    with pytest.raises(typer.Exit) as e:
        trigger.ensure_artifacts_current(
            argv=["apply"],
            invoked_subcommand="apply",
            env={},
            repo_root=tmp_path,
            interactive=True,
            commit=lambda root, report: committed.append(report),
        )

    assert e.value.exit_code == 2
    assert bad.read_text() == before
    assert committed == []
    err = capsys.readouterr().err
    assert "FAILED" in err and "bad" in err


def test_an_unreadable_stamp_is_refused_not_waved_through(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The same hole reached through the stamp rather than a predicate."""
    d = tmp_path / "docs" / "superpowers" / "plans" / "bad"
    d.mkdir(parents=True)
    (d / "_meta.yaml").write_text("schema_version: two\nplan: bad\n")

    with pytest.raises(typer.Exit) as e:
        trigger.ensure_artifacts_current(
            argv=["apply"],
            invoked_subcommand="apply",
            env={},
            repo_root=tmp_path,
            interactive=True,
            commit=lambda root, report: None,
        )

    assert e.value.exit_code == 2
    assert "FAILED" in capsys.readouterr().err


def test_the_gate_refuses_on_the_repositorys_default_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """r4-f5. Running `fr` in the base clone on `main` migrated the tree and
    made a local commit on a protected branch, automatically, before a command
    typed for some other reason. Refusing is the operator's standing preference
    when the situation is ambiguous, and this repo's own doctrine is that the
    base clone is not where work happens."""
    p = _plan(tmp_path)
    before = p.read_text()
    committed: list[object] = []
    monkeypatch.setattr(trigger, "on_default_branch", lambda root: "main")

    with pytest.raises(typer.Exit) as e:
        trigger.ensure_artifacts_current(
            argv=["apply"],
            invoked_subcommand="apply",
            env={},
            repo_root=tmp_path,
            interactive=True,
            commit=lambda root, report: committed.append(report),
        )

    assert e.value.exit_code == 2
    assert p.read_text() == before, "the default branch must never be migrated automatically"
    assert committed == []
    err = capsys.readouterr().err
    assert "main" in err, "the refusal must name the branch"
    assert "fr migrate artifacts" in err, "and the command to run instead"
    assert trigger.SKIP_ENV_VAR in err


def test_a_feature_branch_is_migrated_as_before(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The refusal is scoped to the default branch and nothing else."""
    p = _plan(tmp_path)
    monkeypatch.setattr(trigger, "on_default_branch", lambda root: None)

    trigger.ensure_artifacts_current(
        argv=["apply"],
        invoked_subcommand="apply",
        env={},
        repo_root=tmp_path,
        interactive=True,
        commit=lambda root, report: None,
    )

    assert "<5.0.0" in p.read_text()


def test_the_gate_holds_back_an_artifact_with_uncommitted_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """r4-f2, at the gate: the veto is consulted, and a held-back artifact is a
    refusal rather than a silent skip."""
    p = _plan(tmp_path)
    before = p.read_text()
    monkeypatch.setattr(
        trigger, "uncommitted_veto", lambda root: lambda path: "has uncommitted changes"
    )

    with pytest.raises(typer.Exit) as e:
        trigger.ensure_artifacts_current(
            argv=["apply"],
            invoked_subcommand="apply",
            env={},
            repo_root=tmp_path,
            interactive=True,
            commit=lambda root, report: None,
        )

    assert e.value.exit_code == 2
    assert p.read_text() == before
    assert "uncommitted" in capsys.readouterr().err
