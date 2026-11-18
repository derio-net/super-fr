"""R9: the fr a scaffolded pipeline installs is the commit of its release tag."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.acceptance import pin as pin_mod
from fr.acceptance.pin import FrPin, FrPinError, resolve_fr_pin, tag_for_version
from fr.acceptance.scaffold import init, refresh_ci, render_workflow
from typer.testing import CliRunner

SHA = "0123456789abcdef0123456789abcdef01234567"
PEELED = "89abcdef0123456789abcdef0123456789abcdef"
FIXED = FrPin(SHA, "v8.1.5")
CI_TYPES = ("github-actions", "gitea-actions", "gitlab-ci")


def test_tag_for_version() -> None:
    assert tag_for_version("8.1.5") == "v8.1.5"
    assert tag_for_version("8.1.6rc2") == "v8.1.6-rc.2"


def test_an_annotated_tag_resolves_to_its_peeled_commit() -> None:
    out = f"{SHA}\trefs/tags/v8.1.5\n{PEELED}\trefs/tags/v8.1.5^{{}}\n"
    assert resolve_fr_pin("8.1.5", ls_remote=lambda tag: out) == FrPin(PEELED, "v8.1.5")


def test_a_lightweight_tag_resolves_to_its_line() -> None:
    assert resolve_fr_pin("8.1.5", ls_remote=lambda t: f"{SHA}\trefs/tags/{t}\n") == FIXED


@pytest.mark.parametrize("out", ["", "\n", "garbage"])
def test_no_tag_is_an_error_naming_the_tag(out: str) -> None:
    with pytest.raises(FrPinError, match=r"v8\.1\.5"):
        resolve_fr_pin("8.1.5", ls_remote=lambda t: out)


def test_a_failing_ls_remote_is_an_error_naming_the_tag() -> None:
    def boom(tag: str) -> str:
        raise OSError("network down")

    with pytest.raises(FrPinError, match=r"v8\.1\.5.*network down"):
        resolve_fr_pin("8.1.5", ls_remote=boom)


@pytest.mark.parametrize("ci", CI_TYPES)
def test_every_job_installs_the_pinned_commit_never_main(ci: str) -> None:
    text = render_workflow(
        ci, debt=True, pages=ci != "gitea-actions", comment=ci == "github-actions", fr_pin=FIXED
    )
    line = FIXED.install_line()
    assert "@main" not in text
    assert text.count(line) == text.count("uv tool install")
    assert text.count(line) >= 2


def _tree(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and ".git" not in p.parts
    }


def _failing(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []

    def boom(tag: str) -> str:
        calls.append(tag)
        raise FrPinError(f"cannot read tag {tag}")

    monkeypatch.setattr(pin_mod, "default_ls_remote", boom)
    return calls


def test_init_with_ci_and_a_failing_resolver_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _failing(monkeypatch)
    before = _tree(tmp_path)
    with pytest.raises(FrPinError):
        init(tmp_path, "o", "r", "github", ci_type="github-actions", tracking_type="github")
    assert _tree(tmp_path) == before


def test_init_on_a_repo_with_no_ci_never_resolves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _failing(monkeypatch)
    init(tmp_path, "o", "r", "github", ci_type="none", tracking_type="github")
    assert calls == []


def test_refresh_ci_with_a_failing_resolver_leaves_the_file_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    init(
        tmp_path, "o", "r", "github", ci_type="github-actions", tracking_type="github", fr_pin=FIXED
    )
    wf = tmp_path / ".github/workflows/acceptance-report.yml"
    wf.write_text(wf.read_text().replace(SHA, "f" * 40))
    _failing(monkeypatch)
    before = _tree(tmp_path)
    with pytest.raises(FrPinError):
        refresh_ci(tmp_path, "github-actions", debt=True)
    assert _tree(tmp_path) == before


def test_the_command_exits_2_and_writes_nothing_when_the_pin_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess

    from fr.cli import app

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "remote", "add", "origin", "https://github.com/o/r.git"],
        check=True,
    )
    monkeypatch.chdir(tmp_path)
    _failing(monkeypatch)
    monkeypatch.setenv("FR_SKIP_MIGRATION", "1")
    before = _tree(tmp_path)
    res = CliRunner().invoke(app, ["acceptance", "init", "--with-ci"])
    assert res.exit_code == 2, res.output
    import fr

    flat = " ".join(res.output.split())  # rich wraps long lines
    assert f"tag {tag_for_version(fr.__version__)}" in flat
    assert flat.endswith("nothing was written")
    assert _tree(tmp_path) == before


def test_the_real_reader_asks_git_for_the_tag_and_its_peeled_form_without_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """p2-r2: the autouse fixture stubs the reader everywhere; this runs the real one."""
    import subprocess

    real = pin_mod.default_ls_remote.real  # type: ignore[attr-defined]
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "url.x.insteadOf")
    seen: dict = {}

    def run(argv: list[str], **kw: object) -> subprocess.CompletedProcess[str]:
        seen["argv"], seen["kw"] = argv, kw
        return subprocess.CompletedProcess(argv, 0, stdout="out\n", stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    assert real("v8.1.5") == "out\n"
    assert seen["argv"] == [
        "git",
        "ls-remote",
        pin_mod.FR_REPO_URL,
        "refs/tags/v8.1.5",
        "refs/tags/v8.1.5^{}",
    ]
    env = seen["kw"]["env"]
    assert not [k for k in env if k.startswith("GIT_CONFIG_")]
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert seen["kw"]["timeout"]


@pytest.mark.parametrize("failure", ["exit", "oserror"])
def test_the_real_reader_raises_frpinerror_on_failure(
    monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    import subprocess

    real = pin_mod.default_ls_remote.real  # type: ignore[attr-defined]

    def run(argv: list[str], **kw: object) -> subprocess.CompletedProcess[str]:
        if failure == "oserror":
            raise OSError("no git")
        return subprocess.CompletedProcess(argv, 128, stdout="", stderr="fatal: nope")

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(FrPinError):
        real("v8.1.5")


def test_init_with_an_existing_workflow_never_resolves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """p2-r5: the pin is read only when the workflow will be written."""
    from fr.acceptance.ci import SCAFFOLD_PATHS

    wf = tmp_path / SCAFFOLD_PATHS["github-actions"]
    wf.parent.mkdir(parents=True)
    wf.write_text("name: mine\n")
    calls = _failing(monkeypatch)
    out = init(tmp_path, "o", "r", "github", ci_type="github-actions", tracking_type="github")
    assert calls == [] and SCAFFOLD_PATHS["github-actions"] in out.skipped
    assert wf.read_text() == "name: mine\n"


@pytest.mark.parametrize("ci", ["github-actions", "gitea-actions", "gitlab-ci"])
def test_refresh_of_a_foreign_file_is_foreign_and_never_resolves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ci: str
) -> None:
    from fr.acceptance.ci import SCAFFOLD_PATHS

    wf = tmp_path / SCAFFOLD_PATHS[ci]
    wf.parent.mkdir(parents=True, exist_ok=True)
    wf.write_text("name: someone-else\n")
    calls = _failing(monkeypatch)
    out = refresh_ci(tmp_path, ci, debt=True)
    assert out.status == "foreign" and calls == []


def test_gitlab_refresh_resolves_for_the_pasted_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Paste prints the install line, so it needs the pin (and fails closed without it)."""
    from fr.acceptance.ci import SCAFFOLD_PATHS

    wf = tmp_path / SCAFFOLD_PATHS["gitlab-ci"]
    wf.write_text("acceptance-report:\n  script: x\n")
    out = refresh_ci(tmp_path, "gitlab-ci", debt=True)
    assert out.status == "paste" and "uv tool install" in out.text
    _failing(monkeypatch)
    with pytest.raises(FrPinError):
        refresh_ci(tmp_path, "gitlab-ci", debt=True)


# --- R10: the staleness warning ------------------------------------------------------


def _pinned_repo(root: Path, ci: str, tag: str) -> None:
    from fr.acceptance.ci import SCAFFOLD_PATHS

    path = root / SCAFFOLD_PATHS[ci]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"jobs:\n  run: {FrPin(SHA, tag).install_line()}\n")


@pytest.mark.parametrize("ci", CI_TYPES)
def test_an_older_pin_warns_once_naming_the_remedy(tmp_path: Path, ci: str) -> None:
    from fr.acceptance.pin import stale_pin_warning

    _pinned_repo(tmp_path, ci, "v8.0.0")
    msg = stale_pin_warning(tmp_path, "8.1.5")
    assert msg is not None and "fr acceptance init --refresh-ci" in msg and "v8.0.0" in msg


@pytest.mark.parametrize("tag", ["v8.1.5", "v9.0.0"])
def test_an_equal_or_newer_pin_is_silent(tmp_path: Path, tag: str) -> None:
    from fr.acceptance.pin import stale_pin_warning

    _pinned_repo(tmp_path, "github-actions", tag)
    assert stale_pin_warning(tmp_path, "8.1.5") is None


def test_an_unpinned_or_missing_workflow_is_silent(tmp_path: Path) -> None:
    from fr.acceptance.pin import stale_pin_warning

    assert stale_pin_warning(tmp_path, "8.1.5") is None
    wf = tmp_path / ".github/workflows/acceptance-report.yml"
    wf.parent.mkdir(parents=True)
    wf.write_text(
        'run: uv tool install "git+https://github.com/derio-net/super-fr@main#subdirectory=packages/fr"\n'
    )
    assert stale_pin_warning(tmp_path, "8.1.5") is None


def test_an_rc_pin_compares_by_pep_440(tmp_path: Path) -> None:
    from fr.acceptance.pin import stale_pin_warning

    _pinned_repo(tmp_path, "github-actions", "v8.1.6-rc.1")
    assert stale_pin_warning(tmp_path, "8.1.6") is not None
    assert stale_pin_warning(tmp_path, "8.1.6rc2") is not None
    assert stale_pin_warning(tmp_path, "8.1.6rc1") is None


def test_acceptance_check_reports_an_older_pin_as_a_warning_and_exits_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """l-tests-r4: through `check()` and the CLI, R10's message is a warning, never an
    error, and the gate still passes."""
    import fr
    from fr.acceptance.check import check
    from fr.acceptance.fold import effective
    from fr.cli import app

    from tests.unit.acceptance_helpers import make_repo, row

    root = make_repo(tmp_path, row())
    _pinned_repo(root, "github-actions", "v1.0.0")
    monkeypatch.setattr(fr, "__version__", "8.1.5")
    folded = effective(root)
    result = check(folded.matrix, root, retired=folded.retired)
    stale = [w for w in result.warnings if "--refresh-ci" in w]
    assert len(stale) == 1 and "v1.0.0" in stale[0]
    assert not any("--refresh-ci" in e for e in result.errors)
    assert result.errors == []

    monkeypatch.setenv("FR_REPO_ROOT", str(root))
    out = CliRunner().invoke(app, ["acceptance", "check", "--no-fetch"])
    assert out.exit_code == 0, out.output
    warning = [ln for ln in out.output.splitlines() if "--refresh-ci" in ln]
    assert len(warning) == 1 and warning[0].startswith("::warning ")
