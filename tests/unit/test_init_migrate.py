"""fr init migrate — in-place vk→fr spelling migration (#272).

Dry-run by default, --yes to write; idempotent; prints (never runs) the
host-side secrets-move block.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from fr.cli import app
from typer.testing import CliRunner

runner = CliRunner()


@pytest.fixture()
def legacy_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    r = tmp_path / "myrepo"
    r.mkdir()
    subprocess.run(["git", "init", "-q", str(r)], check=True)
    (r / ".devcontainer").mkdir()
    (r / ".devcontainer" / "vk-profiles.yaml").write_text(
        "default: dev\nprofiles:\n  dev:\n    purpose: test\n  admin:\n    purpose: ops\n"
    )
    for profile in ("dev", "admin"):
        d = r / ".devcontainer" / profile
        d.mkdir()
        (d / "devcontainer.json").write_text(
            json.dumps(
                {
                    "image": "x",
                    "runArgs": [
                        "--env-file",
                        f"${{localEnv:HOME}}/.config/vk/secrets/myrepo/{profile}.env",
                    ],
                    "customizations": {"vk": {"profile": profile, "purpose": "p"}},
                },
                indent=2,
            )
            + "\n"
        )
    subprocess.run(["git", "-C", str(r), "add", "-A"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(r),
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            "commit",
            "-qm",
            "legacy profiles",
        ],
        check=True,
    )
    state = r / ".git" / "vk" / "isolation"
    state.mkdir(parents=True)
    (state / "feat__x.json").write_text("{}")
    return r


def migrate(repo: Path, *extra: str):
    return runner.invoke(app, ["init", "migrate", "--repo", str(repo), *extra])


def test_dry_run_previews_without_mutating(legacy_repo: Path) -> None:
    res = migrate(legacy_repo)
    assert res.exit_code == 0, res.output
    assert "vk-profiles.yaml" in res.output and "fr-profiles.yaml" in res.output
    assert "customizations" in res.output
    assert ".git/vk/isolation" in res.output
    # nothing mutated
    assert (legacy_repo / ".devcontainer" / "vk-profiles.yaml").is_file()
    assert not (legacy_repo / ".devcontainer" / "fr-profiles.yaml").exists()
    cfg = json.loads((legacy_repo / ".devcontainer" / "dev" / "devcontainer.json").read_text())
    assert "vk" in cfg["customizations"]


def test_yes_applies_all_surfaces(legacy_repo: Path) -> None:
    res = migrate(legacy_repo, "--yes")
    assert res.exit_code == 0, res.output

    # profiles yaml renamed via git mv (tracked → stays tracked)
    assert not (legacy_repo / ".devcontainer" / "vk-profiles.yaml").exists()
    assert (legacy_repo / ".devcontainer" / "fr-profiles.yaml").is_file()
    tracked = subprocess.run(
        ["git", "-C", str(legacy_repo), "ls-files", ".devcontainer/fr-profiles.yaml"],
        capture_output=True,
        text=True,
    ).stdout
    assert "fr-profiles.yaml" in tracked

    for profile in ("dev", "admin"):
        cfg = json.loads(
            (legacy_repo / ".devcontainer" / profile / "devcontainer.json").read_text()
        )
        assert "fr" in cfg["customizations"] and "vk" not in cfg["customizations"]
        assert cfg["customizations"]["fr"]["profile"] == profile  # content preserved
        assert "/.config/fr/secrets/" in " ".join(cfg["runArgs"])

    assert not (legacy_repo / ".git" / "vk" / "isolation").exists()
    assert (legacy_repo / ".git" / "fr" / "isolation" / "feat__x.json").is_file()

    # host secrets block printed, not executed
    assert "cp -an" in res.output and ".config/fr/secrets" in res.output
    assert not (Path(legacy_repo).parent / "home" / ".config" / "fr").exists()


def test_rerun_is_idempotent(legacy_repo: Path) -> None:
    assert migrate(legacy_repo, "--yes").exit_code == 0
    res = migrate(legacy_repo, "--yes")
    assert res.exit_code == 0, res.output
    assert "nothing to migrate" in res.output.lower()


def test_jsonc_devcontainer_skipped_not_mangled(legacy_repo: Path) -> None:
    """devcontainer.json may be JSONC; a json round-trip loses comments —
    such files are skipped with a hand-migrate warning (review finding #4)."""
    jsonc = legacy_repo / ".devcontainer" / "dev" / "devcontainer.json"
    original = "// hand-tuned\n" + jsonc.read_text()
    jsonc.write_text(original)
    res = migrate(legacy_repo, "--yes")
    assert res.exit_code == 0, res.output
    assert "SKIP" in res.output and "JSONC" in res.output
    assert jsonc.read_text() == original  # untouched
    # the other (strict-JSON) profile still migrated
    admin = legacy_repo / ".devcontainer" / "admin" / "devcontainer.json"
    assert "/.config/fr/secrets/" in admin.read_text()


def test_untracked_profiles_yaml_plain_rename(tmp_path: Path) -> None:
    r = tmp_path / "repo"
    r.mkdir()
    subprocess.run(["git", "init", "-q", str(r)], check=True)
    (r / ".devcontainer").mkdir()
    (r / ".devcontainer" / "vk-profiles.yaml").write_text("default: dev\n")
    res = migrate(r, "--yes")
    assert res.exit_code == 0, res.output
    assert (r / ".devcontainer" / "fr-profiles.yaml").is_file()
