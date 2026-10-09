"""Candidate-install contract and the acceptance scenarios (spec
2026-10-06-verification-strategies R8-R10, §I).

`.fr/candidate-install <prefix> <source>` installs this checkout into a tmp
prefix (the operator's `fr` link stays exactly as found: gh#683, also enforced
for the whole session by `tests/conftest.py`), then every
`tests/scenarios/<row>.sh` runs against that installed `fr` from a fresh git
fixture, the way `fr verification walk` runs them. One test per matrix row, so
each row can cite its own evidence by name.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT, link_state, runner_packages, uv_tool_bin_dir

INSTALL = REPO_ROOT / ".fr" / "candidate-install"
SCENARIOS = REPO_ROOT / "tests" / "scenarios"


def _env(prefix: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in {"FR_HARNESS_FR", "CI"}}
    env.update(
        UV_TOOL_DIR=str(prefix / "uv-tools"),
        UV_TOOL_BIN_DIR=str(prefix / "bin"),
        PATH=f"{prefix / 'bin'}{os.pathsep}{env.get('PATH', '')}",
    )
    return env


@pytest.fixture(scope="module")
def installed(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """The candidate installed into a throwaway prefix, once for the module."""
    real = uv_tool_bin_dir(os.environ) / "fr"
    before = link_state(real)
    prefix = tmp_path_factory.mktemp("candidate-prefix")
    done = subprocess.run(
        [str(INSTALL), str(prefix), str(REPO_ROOT)], capture_output=True, text=True, check=False
    )
    assert done.returncode == 0, done.stderr[-2000:]
    assert done.stdout.strip().splitlines()[-1] == "fr", done.stdout
    assert link_state(real) == before, "the candidate install relinked the operator's fr"
    yield prefix
    assert link_state(real) == before


def _scenario(name: str, prefix: Path, tmp_path: Path) -> None:
    script = SCENARIOS / f"{name}.sh"
    assert script.is_file() and os.access(script, os.X_OK), script
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    subprocess.run(["git", "init", "-q", str(fixture)], check=True)
    done = subprocess.run(
        [str(script)], cwd=fixture, env=_env(prefix), capture_output=True, text=True, check=False
    )
    assert done.returncode == 0, f"{name}:\n{done.stdout[-1500:]}\n{done.stderr[-2500:]}"
    assert f"ok: {name}" in done.stdout


def test_the_install_prints_fr_and_the_tool_runs(installed: Path) -> None:
    done = subprocess.run(
        [str(installed / "bin" / "fr"), "--version"],
        env=_env(installed),
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr


def test_the_install_exposes_the_fr_herdr_console_script(installed: Path) -> None:
    """`--with-executables-from fr-herdr`: the script is in `<prefix>/bin` beside fr."""
    exe = installed / "bin" / "fr-herdr"
    assert exe.exists()
    done = subprocess.run(
        [str(exe), "restart-idle", "--help"], env=_env(installed), capture_output=True, text=True
    )
    assert done.returncode == 0 and "--exclude" in done.stdout, done.stderr


def test_herdr_opencode_launch(installed: Path, tmp_path: Path) -> None:
    _scenario("herdr-opencode", installed, tmp_path)


def test_herdr_opencode_restart(installed: Path, tmp_path: Path) -> None:
    _scenario("herdr-opencode-restart", installed, tmp_path)


def test_the_install_carries_every_runner_package(installed: Path) -> None:
    """The `--with` set mirrors install.sh's: every `fr.runners` package imports."""
    py = installed / "uv-tools" / "fr" / "bin" / "python"
    for pkg in runner_packages():
        mod = pkg.replace("-", "_")
        done = subprocess.run([str(py), "-c", f"import {mod}"], capture_output=True, text=True)
        assert done.returncode == 0, f"{pkg}: {done.stderr}"


_UV_STUB = """#!/bin/sh
if [ "$1 $2 $3" = "tool install --help" ]; then echo "      --with-executables-from <X>"; exit 0; fi
for a in "$@"; do printf '%s\\n' "$a" >> "$UV_STUB_LOG"; done
mkdir -p "$UV_TOOL_BIN_DIR"
printf '#!/bin/sh\\necho "fr 9.9.9"\\n' > "$UV_TOOL_BIN_DIR/fr"
chmod +x "$UV_TOOL_BIN_DIR/fr"
"""


def test_a_git_source_installs_every_package_from_its_subdirectory(tmp_path: Path) -> None:
    """`git+<url>@<ref>` names each package by `#subdirectory=packages/<pkg>`,
    and the git list covers exactly the packages the checkout derivation finds."""
    stub = tmp_path / "bin" / "uv"
    stub.parent.mkdir()
    stub.write_text(_UV_STUB)
    stub.chmod(0o755)
    log = tmp_path / "uv.log"
    env = {**os.environ, "UV_STUB_LOG": str(log), "PATH": f"{stub.parent}{os.pathsep}/usr/bin:/bin"}
    source = "git+https://example.invalid/org/repo@rc/feat-x/abc123def456"

    done = subprocess.run(
        [str(INSTALL), str(tmp_path / "prefix"), source],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert done.returncode == 0, done.stderr
    assert done.stdout.strip().splitlines()[-1] == "fr"
    argv = log.read_text().splitlines()
    base = "git+https://example.invalid/org/repo@rc/feat-x/abc123def456"
    assert argv[:3] == ["tool", "install", "--force"]
    assert f"{base}#subdirectory=packages/fr" in argv
    for pkg in runner_packages():
        assert f"{pkg} @ {base}#subdirectory=packages/{pkg}" in argv, pkg


def test_the_install_refuses_a_source_without_the_package(tmp_path: Path) -> None:
    done = subprocess.run(
        [str(INSTALL), str(tmp_path / "prefix"), str(tmp_path)], capture_output=True, text=True
    )
    assert done.returncode == 2
    assert "packages/fr" in done.stderr


def test_every_scenario_script_has_a_test_here() -> None:
    on_disk = {p.stem for p in SCENARIOS.glob("*.sh") if not p.name.startswith("_")}
    here = {
        "verification-strategy-resolution",
        "shipped-verification-strategies",
        "spec-verification-section",
        "walk-recording-prints-close",
        "awaiting-live-triage",
        "prerelease-command-shape",
        "triage-claims-held",
        "triage-claims-expired",
        "herdr-restart-idle",
        "herdr-opencode",
        "herdr-opencode-restart",
        "model-binding-set-probe",
        "model-binding-replacement",
        "model-binding-check",
        "cloud-triage-ci-evidence",
        "cloud-triage-state-ref",
        "cloud-triage-privacy-guard",
        "cloud-triage-driver-lease",
        "cloud-triage-version-drift",
        "cloud-triage-repo-agents",
        "cloud-triage-cloud-remedy",
    }
    assert on_disk == here


def test_verification_strategy_resolution(installed: Path, tmp_path: Path) -> None:
    _scenario("verification-strategy-resolution", installed, tmp_path)


def test_shipped_verification_strategies(installed: Path, tmp_path: Path) -> None:
    _scenario("shipped-verification-strategies", installed, tmp_path)


def test_spec_verification_section(installed: Path, tmp_path: Path) -> None:
    _scenario("spec-verification-section", installed, tmp_path)


def test_walk_recording_prints_close(installed: Path, tmp_path: Path) -> None:
    _scenario("walk-recording-prints-close", installed, tmp_path)


def test_awaiting_live_triage(installed: Path, tmp_path: Path) -> None:
    _scenario("awaiting-live-triage", installed, tmp_path)


def test_prerelease_command_shape(installed: Path, tmp_path: Path) -> None:
    _scenario("prerelease-command-shape", installed, tmp_path)


def test_triage_claims_held(installed: Path, tmp_path: Path) -> None:
    _scenario("triage-claims-held", installed, tmp_path)


def test_triage_claims_expired(installed: Path, tmp_path: Path) -> None:
    _scenario("triage-claims-expired", installed, tmp_path)


def test_model_binding_set_probe(installed: Path, tmp_path: Path) -> None:
    _scenario("model-binding-set-probe", installed, tmp_path)


def test_model_binding_replacement(installed: Path, tmp_path: Path) -> None:
    _scenario("model-binding-replacement", installed, tmp_path)


def test_model_binding_check(installed: Path, tmp_path: Path) -> None:
    _scenario("model-binding-check", installed, tmp_path)


def test_herdr_restart_idle(installed: Path, tmp_path: Path) -> None:
    _scenario("herdr-restart-idle", installed, tmp_path)


def test_cloud_triage_ci_evidence(installed: Path, tmp_path: Path) -> None:
    _scenario("cloud-triage-ci-evidence", installed, tmp_path)


def test_cloud_triage_state_ref(installed: Path, tmp_path: Path) -> None:
    _scenario("cloud-triage-state-ref", installed, tmp_path)


def test_cloud_triage_privacy_guard(installed: Path, tmp_path: Path) -> None:
    _scenario("cloud-triage-privacy-guard", installed, tmp_path)


def test_cloud_triage_driver_lease(installed: Path, tmp_path: Path) -> None:
    _scenario("cloud-triage-driver-lease", installed, tmp_path)


def test_cloud_triage_version_drift(installed: Path, tmp_path: Path) -> None:
    _scenario("cloud-triage-version-drift", installed, tmp_path)


def test_cloud_triage_repo_agents(installed: Path, tmp_path: Path) -> None:
    _scenario("cloud-triage-repo-agents", installed, tmp_path)


def test_cloud_triage_cloud_remedy(installed: Path, tmp_path: Path) -> None:
    _scenario("cloud-triage-cloud-remedy", installed, tmp_path)
