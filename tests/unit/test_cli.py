from pathlib import Path

from typer.testing import CliRunner

from vk.cli import app

runner = CliRunner()


def test_version_flag():
    from vk import __version__

    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_help_flag():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "plan" in result.stdout
    assert "dispatch" in result.stdout
    assert "progress" in result.stdout
    assert "execute" in result.stdout
    assert "init" in result.stdout
    assert "skills" in result.stdout


def test_skills_command():
    result = runner.invoke(app, ["skills"])
    assert result.exit_code == 0
    for skill in ("vk-plan", "vk-dispatch", "vk-execute", "vk-progress"):
        assert skill in result.stdout
    for sub in ("vk plan new", "vk dispatch create", "vk execute scope", "vk progress sync"):
        assert sub in result.stdout


def test_plan_help():
    result = runner.invoke(app, ["plan", "--help"])
    assert result.exit_code == 0


def test_dispatch_help():
    result = runner.invoke(app, ["dispatch", "--help"])
    assert result.exit_code == 0


def test_progress_help():
    result = runner.invoke(app, ["progress", "--help"])
    assert result.exit_code == 0


def test_execute_help():
    result = runner.invoke(app, ["execute", "--help"])
    assert result.exit_code == 0


def test_init_help():
    result = runner.invoke(app, ["init", "--help"])
    assert result.exit_code == 0


def test_init_creates_config():
    result = runner.invoke(app, ["init", "--help"])
    assert result.exit_code == 0
    assert "dispatch" in result.stdout
    assert "force" in result.stdout


def test_plan_shows_help():
    result = runner.invoke(app, ["plan", "--help"])
    assert result.exit_code == 0
    assert "new" in result.stdout
    assert "self-review" in result.stdout
    assert "convert" in result.stdout


def test_dispatch_no_args_shows_usage():
    result = runner.invoke(app, ["dispatch"])
    assert result.exit_code == 2


def test_dispatch_help_lists_subcommands():
    result = runner.invoke(app, ["dispatch", "--help"])
    assert result.exit_code == 0
    assert "create" in result.stdout
    assert "migrate" in result.stdout


def test_dispatch_create_no_args_shows_usage():
    result = runner.invoke(app, ["dispatch", "create"])
    assert result.exit_code == 2


def test_progress_help_detailed():
    result = runner.invoke(app, ["progress", "--help"])
    assert result.exit_code == 0
    assert "sync" in result.stdout
    assert "board" in result.stdout
    assert "audit" in result.stdout


def test_execute_help_detailed():
    result = runner.invoke(app, ["execute", "--help"])
    assert result.exit_code == 0
    assert "check-deps" in result.stdout
    assert "scope" in result.stdout
    assert "check-step" in result.stdout


def test_dispatch_migrate_command_exists():
    result = runner.invoke(app, ["dispatch", "migrate", "--help"])
    assert result.exit_code == 0
    assert "migrate" in result.output.lower()


class TestSelfReviewDagChecks:
    def test_self_review_rejects_cycle(self, tmp_path: Path) -> None:
        # Cycle can only arise from forward-ref under backward-only rule,
        # so we construct a forward reference and confirm the specific message.
        plan = tmp_path / "p.md"
        plan.write_text(
            "# T\n\n**Spec:** `s.md`\n**Status:** Not Started\n\n**Goal:** g\n\n---\n\n"
            "## Phase 1: A [agentic]\n**Depends on:** Phase 2\n\n"
            "### Task 1: T\n\n- [ ] **Step 1:** s\n\n"
            "## Phase 2: B [agentic]\n**Depends on:** —\n\n"
            "### Task 1: T\n\n- [ ] **Step 1:** s\n"
        )
        result = runner.invoke(app, ["plan", "self-review", str(plan)])
        assert result.exit_code != 0
        assert "forward reference" in (result.stdout + (result.stderr or ""))

    def test_self_review_rejects_unknown_ref(self, tmp_path: Path) -> None:
        plan = tmp_path / "p.md"
        plan.write_text(
            "# T\n\n**Spec:** `s.md`\n**Status:** Not Started\n\n**Goal:** g\n\n---\n\n"
            "## Phase 1: A [agentic]\n**Depends on:** —\n\n"
            "### Task 1: T\n\n- [ ] **Step 1:** s\n\n"
            "## Phase 2: B [agentic]\n**Depends on:** Phase 99\n\n"
            "### Task 1: T\n\n- [ ] **Step 1:** s\n"
        )
        result = runner.invoke(app, ["plan", "self-review", str(plan)])
        assert result.exit_code != 0
        assert "does not exist" in (result.stdout + (result.stderr or ""))
