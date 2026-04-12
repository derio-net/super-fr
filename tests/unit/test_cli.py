from typer.testing import CliRunner

from vk.cli import app

runner = CliRunner()


def test_version_flag():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.3.0" in result.stdout


def test_help_flag():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "plan" in result.stdout
    assert "dispatch" in result.stdout
    assert "progress" in result.stdout
    assert "execute" in result.stdout
    assert "init" in result.stdout
    assert "install-skills" in result.stdout


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


def test_init_not_implemented():
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 1
    assert "not yet implemented" in result.stdout


def test_install_skills_not_implemented():
    result = runner.invoke(app, ["install-skills"])
    assert result.exit_code == 1
    assert "not yet implemented" in result.stdout


def test_plan_no_subcommand():
    result = runner.invoke(app, ["plan"])
    assert result.exit_code == 0


def test_dispatch_no_args_shows_usage():
    result = runner.invoke(app, ["dispatch"])
    assert result.exit_code == 2  # missing required PLAN_PATH argument


def test_progress_no_subcommand():
    result = runner.invoke(app, ["progress"])
    assert result.exit_code == 0


def test_execute_no_subcommand():
    result = runner.invoke(app, ["execute"])
    assert result.exit_code == 0
