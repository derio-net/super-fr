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


def test_the_exemption_list_is_exactly_four_things() -> None:
    """Spec §3.C: "exemptions, narrow and explicit".

    Pinned as a literal rather than derived, because the failure mode of an
    extra entry is silence: every command keeps working and nothing ever
    migrates. A fifth exemption has to be argued for in a diff to this line.
    """
    assert trigger.EXEMPT_OPTIONS == frozenset({"--help", "--version"})
    assert trigger.EXEMPT_COMMANDS == frozenset({"migrate"})
    assert trigger.SKIP_ENV_VAR == "FR_SKIP_MIGRATION"
    assert trigger.EXEMPTIONS == ("--help", "--version", "migrate", "FR_SKIP_MIGRATION=1")


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
        argv=["status"], invoked_subcommand="status", env={"FR_SKIP_MIGRATION": "1"}
    )
    assert not trigger.is_exempt(
        argv=["status"], invoked_subcommand="status", env={"FR_SKIP_MIGRATION": "0"}
    )
    assert not trigger.is_exempt(
        argv=["status"], invoked_subcommand="status", env={"FR_SKIP_MIGRATION": ""}
    )


def test_an_ordinary_command_is_not_exempt() -> None:
    assert not trigger.is_exempt(argv=["status"], invoked_subcommand="status", env={})
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
        argv=["status"], invoked_subcommand="status", env={}, repo_root=tmp_path, interactive=True
    )
    assert ran == [] and committed == []


def test_interactive_migrates_commits_and_returns(tmp_path: Path) -> None:
    """Migrate, commit, continue — returning is how the typed command resumes."""
    p = _plan(tmp_path)
    committed: list[object] = []
    trigger.ensure_artifacts_current(
        argv=["status"],
        invoked_subcommand="status",
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
            argv=["status"],
            invoked_subcommand="status",
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
            argv=["status"],
            invoked_subcommand="status",
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
            argv=["status"],
            invoked_subcommand="status",
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
    """Interactive: the migration happens and `fr skills` still prints."""
    p = _plan(tmp_path)
    result = _invoke(monkeypatch, tmp_path, ["skills"])
    assert result.exit_code == 0, result.output
    assert "<5.0.0" in p.read_text()
    assert "Commands" in result.output, "the typed command must still run"


def test_the_callback_refuses_the_command_in_ci(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = _plan(tmp_path)
    before = p.read_text()
    result = _invoke(monkeypatch, tmp_path, ["skills"], interactive=False)
    assert result.exit_code != 0
    assert p.read_text() == before
    assert "Commands" not in result.output, "the command must not run on stale artifacts"


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
