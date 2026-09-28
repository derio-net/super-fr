"""The `profiles` kind's 1 -> 2 migration — spec
`2026-09-28-fr-profiles-services-design.md` §3.D, R3.

Version 1 carried the forge as flat top-level `backend:`/`host:`; version 2
nests it under `forge:` beside `ci:` and `tracking:`. The migration rewrites the
body TEXTUALLY — every line but the two dropped keys is kept byte-for-byte —
reads v1 only through the frozen `fr.services.legacy.ProfilesV1`, and writes
once through `write_text_atomic`.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml
from fr.artifacts import MIGRATIONS, artifact_kind, run_migrations
from fr.artifacts.registry import PRE_FRAMEWORK_VERSION
from fr.services.resolve import resolve_services

PROFILES_REL = ".devcontainer/fr-profiles.yaml"

BODY = """\
# fr-profiles — header comment, must survive
profiles:
  dev:
    purpose: 'day-to-day: tests'   # inline comment kept
    secrets: []

  admin:
    secrets:
    - GH_TOKEN
default: dev
"""


def _repo(
    tmp_path: Path,
    *,
    remote: str | None,
    profiles: str | bytes,
    files: dict[str, str] | None = None,
) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    if remote:
        subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", remote], check=True)
    path = repo / PROFILES_REL
    path.parent.mkdir()
    path.write_bytes(profiles if isinstance(profiles, bytes) else profiles.encode())
    for rel, text in (files or {}).items():
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    return repo


def _migrate(repo: Path) -> dict[str, object]:
    report = run_migrations(repo, dry_run=False)
    assert report.ok, report.failed
    data = yaml.safe_load((repo / PROFILES_REL).read_text())
    assert isinstance(data, dict)
    return data


FR_ONLY_GITLAB_CI = """\
stages: [test]
acceptance-report:
  stage: test
  script: [fr acceptance check]
"""


def test_the_profiles_kind_is_at_version_two() -> None:
    kind = artifact_kind("profiles")
    assert kind.current_version == 2
    assert kind.locator == PROFILES_REL


def test_the_chain_from_one_is_one_hop_to_two() -> None:
    chain = MIGRATIONS.chain("profiles", PRE_FRAMEWORK_VERSION)
    assert [s.to_version for s in chain] == [2]


def test_github_with_real_ci(tmp_path: Path) -> None:
    repo = _repo(
        tmp_path,
        remote="https://github.com/derio-net/demo.git",
        profiles="backend: github\n" + BODY,
        files={
            ".github/workflows/ci.yml": "on: push\n",
            ".github/workflows/acceptance-report.yml": "on: push\n",
        },
    )
    data = _migrate(repo)
    assert data["forge"] == {"type": "github"}
    assert data["ci"] == {"type": "github-actions"}
    assert data["tracking"] == {"type": "github"}
    assert data["schema_version"] == 2
    assert "backend" not in data and "host" not in data


def test_gitlab_with_fr_only_ci_keeps_the_host_and_has_no_ci(tmp_path: Path) -> None:
    repo = _repo(
        tmp_path,
        remote="https://gitlab.example.com/grp/demo.git",
        profiles="backend: gitlab\nhost: gitlab.example.com\n" + BODY,
        files={".gitlab-ci.yml": FR_ONLY_GITLAB_CI},
    )
    data = _migrate(repo)
    assert data["forge"] == {"type": "gitlab", "host": "gitlab.example.com"}
    assert data["ci"] == {"type": "none"}
    assert data["tracking"] == {"type": "gitlab"}


def test_gitea(tmp_path: Path) -> None:
    repo = _repo(
        tmp_path,
        remote="https://gitea.example.org/o/demo.git",
        profiles=BODY + "backend: gitea\nhost: gitea.example.org\n",
        files={".gitea/workflows/build.yml": "on: push\n"},
    )
    data = _migrate(repo)
    assert data["forge"] == {"type": "gitea", "host": "gitea.example.org"}
    assert data["ci"] == {"type": "gitea-actions"}
    assert data["tracking"] == {"type": "gitea"}


def test_no_backend_key_infers_the_forge_from_origin(tmp_path: Path) -> None:
    repo = _repo(tmp_path, remote="git@gitlab.com:grp/demo.git", profiles=BODY)
    data = _migrate(repo)
    assert data["forge"] == {"type": "gitlab"}
    assert data["ci"] == {"type": "none"}
    assert data["tracking"] == {"type": "gitlab"}


def test_every_other_line_is_kept_byte_for_byte(tmp_path: Path) -> None:
    repo = _repo(
        tmp_path,
        remote="https://github.com/derio-net/demo.git",
        profiles="backend: github\n" + BODY,
    )
    _migrate(repo)
    after = (repo / PROFILES_REL).read_text()
    # The header comment stays on top; the stamp lands below it (the shared
    # yaml stamp writer's rule); the original lines follow untouched.
    assert after.startswith("# fr-profiles — header comment, must survive\nschema_version: 2\n")
    body_after = after.replace("schema_version: 2\n", "", 1)
    assert body_after.startswith(BODY)
    assert body_after[len(BODY) :] == (
        "forge:\n  type: github\nci:\n  type: none\ntracking:\n  type: github\n"
    )


def test_crlf_stays_crlf(tmp_path: Path) -> None:
    text = ("backend: gitlab\nhost: gitlab.example.com\n" + BODY).replace("\n", "\r\n")
    repo = _repo(tmp_path, remote=None, profiles=text.encode())
    _migrate(repo)
    raw = (repo / PROFILES_REL).read_bytes()
    assert b"\n" not in raw.replace(b"\r\n", b"")
    assert b"forge:\r\n  type: gitlab\r\n  host: gitlab.example.com\r\n" in raw


def test_a_file_without_a_final_newline(tmp_path: Path) -> None:
    repo = _repo(tmp_path, remote=None, profiles="default: dev\nbackend: github")
    data = _migrate(repo)
    assert data["default"] == "dev"
    assert data["forge"] == {"type": "github"}


def test_an_explicit_version_one_stamp_is_restamped(tmp_path: Path) -> None:
    repo = _repo(tmp_path, remote=None, profiles="schema_version: 1\nbackend: github\n" + BODY)
    data = _migrate(repo)
    assert data["schema_version"] == 2
    assert (repo / PROFILES_REL).read_text().count("schema_version") == 1


def test_a_body_already_wholly_v2_lets_the_runner_stamp(tmp_path: Path) -> None:
    """The crash window: `fn` wrote the body, the runner died before the stamp."""
    v2_body = BODY + "forge:\n  type: gitlab\nci:\n  type: none\ntracking:\n  type: gitlab\n"
    repo = _repo(tmp_path, remote=None, profiles=v2_body)
    report = run_migrations(repo, dry_run=False)
    assert report.ok, report.failed
    header, rest = v2_body.split("\n", 1)
    assert (repo / PROFILES_REL).read_text() == f"{header}\nschema_version: 2\n{rest}"


def test_a_half_merged_body_is_refused_byte_identical(tmp_path: Path) -> None:
    text = "backend: github\n" + BODY + "forge:\n  type: github\n"
    repo = _repo(tmp_path, remote=None, profiles=text)
    before = (repo / PROFILES_REL).read_bytes()
    report = run_migrations(repo, dry_run=False)
    assert [f.path for f in report.failed] == [repo / PROFILES_REL]
    assert (repo / PROFILES_REL).read_bytes() == before


@pytest.mark.parametrize(
    "extra",
    ["forge_type: gitlab\n", "backend: bitbucket\n"],
    ids=["unknown-key", "unknown-backend"],
)
def test_a_v1_file_it_cannot_read_is_refused_byte_identical(tmp_path: Path, extra: str) -> None:
    repo = _repo(tmp_path, remote=None, profiles=extra + BODY)
    before = (repo / PROFILES_REL).read_bytes()
    report = run_migrations(repo, dry_run=False)
    assert [f.path for f in report.failed] == [repo / PROFILES_REL]
    assert (repo / PROFILES_REL).read_bytes() == before


def test_migrating_is_idempotent(tmp_path: Path) -> None:
    repo = _repo(tmp_path, remote=None, profiles="backend: github\n" + BODY)
    _migrate(repo)
    once = (repo / PROFILES_REL).read_bytes()
    report = run_migrations(repo, dry_run=False)
    assert report.applied == ()
    assert (repo / PROFILES_REL).read_bytes() == once


@pytest.mark.parametrize(
    ("remote", "profiles", "files"),
    [
        ("https://github.com/o/r.git", "backend: github\n", {".github/workflows/ci.yml": "x: 1\n"}),
        ("https://github.com/o/r.git", "", {".github/workflows/acceptance-report.yml": "x: 1\n"}),
        ("https://gitlab.com/o/r.git", "", {".gitlab-ci.yml": FR_ONLY_GITLAB_CI}),
        ("https://gitlab.com/o/r.git", "backend: gitlab\n", {".gitlab-ci.yml": "build: {}\n"}),
        ("https://gitea.example.org/o/r.git", "backend: gitea\n", {}),
    ],
    ids=["gh-real", "gh-fr-only", "gl-fr-only", "gl-real", "gitea-absent"],
)
def test_the_legacy_resolved_ci_is_what_the_migration_writes(
    tmp_path: Path, remote: str, profiles: str, files: dict[str, str]
) -> None:
    """R7 + phase-1 review p1r-later-tests: `fr services` on an unmigrated file
    must show the value the migration then writes, so migrating changes
    nothing a reader can see."""
    repo = _repo(tmp_path, remote=remote, profiles=profiles + BODY, files=files)
    before = resolve_services(repo)
    assert before.ci.source == "legacy"
    data = _migrate(repo)
    assert data["ci"] == {"type": before.ci.type}
    after = resolve_services(repo)
    assert (after.forge.type, after.ci.type, after.tracking.type) == (
        before.forge.type,
        before.ci.type,
        before.tracking.type,
    )
    assert after.ci.source == "declared"


# --- the CLI-entry gate over an unmigrated file (phase-1 review p1r-later-tests)


def _invoke_gated(monkeypatch: pytest.MonkeyPatch, repo: Path, argv: list[str]) -> tuple[int, str]:
    """Invoke `fr` with the gate LIVE and non-interactive — the agent / CI case.
    `conftest` skips the gate suite-wide; these invocations must see it."""
    import sys

    from fr.artifacts import trigger
    from fr.cli import app
    from typer.testing import CliRunner

    monkeypatch.delenv("FR_SKIP_MIGRATION", raising=False)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setattr(sys, "argv", ["fr", *argv])
    monkeypatch.setattr(trigger, "is_interactive", lambda **k: False)
    monkeypatch.chdir(repo)
    result = CliRunner().invoke(app, argv, env={"VK_REPO_ROOT": str(repo)})
    return result.exit_code, result.output


GATE_REFUSAL = "were written for a different fr"


@pytest.mark.parametrize(
    "argv",
    [["services", "--json"], ["status"], ["isolation", "status"]],
    ids=["services", "status", "isolation-status"],
)
def test_the_exempt_commands_run_over_an_unmigrated_v1_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, argv: list[str]
) -> None:
    repo = _repo(
        tmp_path,
        remote="https://gitlab.example.com/grp/demo.git",
        profiles="backend: gitlab\nhost: gitlab.example.com\n" + BODY,
        files={".gitlab-ci.yml": "build:\n  script: [make]\n"},
    )
    before = (repo / PROFILES_REL).read_bytes()
    code, out = _invoke_gated(monkeypatch, repo, argv)
    assert GATE_REFUSAL not in out, out
    assert (repo / PROFILES_REL).read_bytes() == before, "an exempt command must not migrate"
    if argv[0] == "services":
        import json

        assert code == 0, out
        data = json.loads(out)
        assert data["forge"] == {"type": "gitlab", "host": "gitlab.example.com", "source": "legacy"}
        assert data["ci"]["type"] == "gitlab-ci" and data["ci"]["source"] == "legacy"


def test_a_gated_command_refuses_over_an_unmigrated_v1_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path, remote=None, profiles="backend: github\n" + BODY)
    before = (repo / PROFILES_REL).read_bytes()
    code, out = _invoke_gated(monkeypatch, repo, ["models", "get", "--harness", "claude-code"])
    assert code != 0
    assert GATE_REFUSAL in out
    assert (repo / PROFILES_REL).read_bytes() == before


# --- phase-2 review --------------------------------------------------------


@pytest.mark.parametrize(
    "remote",
    ["https://forge.unknown-host.example/o/r.git", None],
    ids=["unknown-origin", "no-origin"],
)
def test_an_unknown_forge_is_not_locked_in_as_declared(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    remote: str | None,
) -> None:
    """r1: the `github` FALLBACK is not a declaration. With no `backend:`, no
    `host:` and an origin fr does not recognise, `forge:`/`tracking:` stay
    undeclared, so the source stays `default` and the warning keeps firing."""
    from fr import _hosts

    repo = _repo(tmp_path, remote=remote, profiles=BODY)
    data = _migrate(repo)
    assert data["schema_version"] == 2
    assert "forge" not in data and "tracking" not in data and "ci" not in data
    services = resolve_services(repo)
    assert services.forge.source == "default" and services.tracking.source == "default"
    if remote:
        _hosts._WARNED_UNKNOWN_HOSTS.discard("forge.unknown-host.example")
        _hosts.detect_backend(repo)
        assert "not a recognized forge" in capsys.readouterr().err


def test_an_unknown_forge_with_fr_only_ci_still_declares_ci_none(tmp_path: Path) -> None:
    """r1: detection that IS conclusive for the fallback type is written, so the
    value `fr services` showed before migrating (fr's scaffold discounted) holds."""
    repo = _repo(
        tmp_path,
        remote="https://forge.unknown-host.example/o/r.git",
        profiles=BODY,
        files={".github/workflows/acceptance-report.yml": "on: push\n"},
    )
    before = resolve_services(repo).ci.type
    data = _migrate(repo)
    assert "forge" not in data
    assert data["ci"] == {"type": "none"} and before == "none"
    assert resolve_services(repo).ci.type == "none"


def test_a_host_without_backend_is_scaffolds_github(tmp_path: Path) -> None:
    """`fr init scaffold --host ghe.example.com` (backend github, the default)
    wrote `host:` alone — so the pair declares a GitHub Enterprise forge."""
    repo = _repo(
        tmp_path,
        remote="https://ghe.example.com/o/r.git",
        profiles="host: ghe.example.com\n" + BODY,
    )
    before = resolve_services(repo).forge
    data = _migrate(repo)
    assert data["forge"] == {"type": "github", "host": "ghe.example.com"}
    assert before.type == "github" and before.host == "ghe.example.com"


def test_an_invalid_service_block_is_refused_naming_the_block(tmp_path: Path) -> None:
    """r5: no legacy key is present, so the refusal must not say "mixes"."""
    repo = _repo(tmp_path, remote=None, profiles=BODY + "ci:\n  type: travis\n")
    before = (repo / PROFILES_REL).read_bytes()
    report = run_migrations(repo, dry_run=False)
    [failure] = report.failed
    assert "mixes" not in str(failure.error)
    assert "travis" in str(failure.error)
    assert (repo / PROFILES_REL).read_bytes() == before


def test_a_bom_round_trips(tmp_path: Path) -> None:
    repo = _repo(tmp_path, remote=None, profiles=b"\xef\xbb\xbfbackend: github\n" + BODY.encode())
    _migrate(repo)
    raw = (repo / PROFILES_REL).read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf") and raw.count(b"\xef\xbb\xbf") == 1
    assert b"backend" not in raw


def test_a_host_nested_under_a_profile_is_kept(tmp_path: Path) -> None:
    text = "backend: gitlab\nprofiles:\n  dev:\n    host: db.example.com\n    secrets: []\n"
    repo = _repo(tmp_path, remote=None, profiles=text)
    data = _migrate(repo)
    assert data["profiles"] == {"dev": {"host": "db.example.com", "secrets": []}}
    assert data["forge"] == {"type": "gitlab"}


def test_a_legacy_key_with_a_continuation_line(tmp_path: Path) -> None:
    text = "backend: gitlab\nhost:\n  gitlab.example.com\n" + BODY
    repo = _repo(tmp_path, remote=None, profiles=text)
    data = _migrate(repo)
    assert data["forge"] == {"type": "gitlab", "host": "gitlab.example.com"}
    assert (repo / PROFILES_REL).read_text().count("gitlab.example.com") == 1


def test_an_empty_file(tmp_path: Path) -> None:
    repo = _repo(tmp_path, remote="https://github.com/o/r.git", profiles="")
    data = _migrate(repo)
    assert data == {
        "schema_version": 2,
        "forge": {"type": "github"},
        "ci": {"type": "none"},
        "tracking": {"type": "github"},
    }


@pytest.mark.parametrize(
    "text",
    [
        '"backend": github\n' + BODY,
        "  backend: github\n  default: dev\n",
        "{backend: github, default: dev}\n",
    ],
    ids=["quoted-key", "indented-document", "flow-style"],
)
def test_a_layout_the_line_rewrite_cannot_handle_is_refused_byte_identical(
    tmp_path: Path, text: str
) -> None:
    """r4/r6: refused — with a message about the layout — and left untouched."""
    repo = _repo(tmp_path, remote=None, profiles=text)
    before = (repo / PROFILES_REL).read_bytes()
    report = run_migrations(repo, dry_run=False)
    [failure] = report.failed
    assert "layout" in str(failure.error)
    assert (repo / PROFILES_REL).read_bytes() == before
