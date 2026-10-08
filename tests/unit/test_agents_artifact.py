"""The `agents` artifact kind (spec 2026-10-07-cloud-triage R19, §H, Test Plan 18)."""

from __future__ import annotations

import dataclasses
import subprocess
from pathlib import Path

import pytest
import yaml
from fr.agents import AGENT_NAMES, STAMP_KEY, canonical_text, render_agent, write_agents
from fr.artifacts import MIGRATIONS, MigrationRegistry, iter_paths_of, run_migrations
from fr.artifacts.registry import ARTIFACT_KINDS
from fr.artifacts.validate import validate_repo
from typer.testing import CliRunner

KIND = ARTIFACT_KINDS["agents"]


def _front_matter(text: str) -> dict[str, object]:
    assert text.startswith("---\n")
    block = text.split("\n---\n", 1)[0][4:]
    data = yaml.safe_load(block)
    assert isinstance(data, dict)
    return data


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    return repo


def _issues(repo: Path) -> list[str]:
    return [f"{i.path.name}: {i.message}" for i in validate_repo(repo, kind_name="agents").issues]


# --- render ----------------------------------------------------------------


@pytest.mark.parametrize("name", AGENT_NAMES)
def test_render_adds_only_the_stamp_to_the_front_matter(name: str) -> None:
    canonical = canonical_text(name)
    rendered = render_agent(name, 7)

    fm = _front_matter(rendered)
    assert fm[STAMP_KEY] == 7
    assert fm["name"] == name
    # Everything else is the canonical text, byte for byte.
    assert rendered.replace(f"{STAMP_KEY}: 7\n", "", 1) == canonical


def test_render_refuses_a_name_fr_does_not_ship() -> None:
    with pytest.raises(KeyError):
        render_agent("fr-something-else", 1)


# --- write (fr init) ----------------------------------------------------------


def test_write_agents_writes_both_stamped_files(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    written = write_agents(repo)

    assert sorted(p.name for p in written) == sorted(f"{n}.md" for n in AGENT_NAMES)
    for name in AGENT_NAMES:
        path = repo / ".claude" / "agents" / f"{name}.md"
        assert path.read_text(encoding="utf-8") == render_agent(name, KIND.current_version)
    assert write_agents(repo) == [], "a second write changes nothing"


def test_write_agents_replaces_a_symlink_with_the_rendered_file(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    agents = repo / ".claude" / "agents"
    agents.mkdir(parents=True)
    target = tmp_path / "elsewhere.md"
    target.write_text("---\nname: fr-spec-reviewer\n---\n")
    (agents / "fr-spec-reviewer.md").symlink_to(target)

    write_agents(repo)

    path = agents / "fr-spec-reviewer.md"
    assert not path.is_symlink()
    assert target.read_text() == "---\nname: fr-spec-reviewer\n---\n", "the target is untouched"


def test_fr_init_agents_writes_both_files(tmp_path: Path) -> None:
    from fr.cli import app

    repo = _repo(tmp_path)
    result = CliRunner().invoke(app, ["init", "agents", "--repo", str(repo), "--no-commit"])

    assert result.exit_code == 0, result.output
    for name in AGENT_NAMES:
        assert (repo / ".claude" / "agents" / f"{name}.md").is_file()


# --- locate and validate -------------------------------------------------------


def test_iter_paths_of_locates_exactly_the_two_files(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    write_agents(repo)
    (repo / ".claude" / "agents" / "my-own-agent.md").write_text("---\nname: my-own-agent\n---\n")

    found = [p.name for p in iter_paths_of(repo, KIND)]

    assert sorted(found) == sorted(f"{n}.md" for n in AGENT_NAMES)


def test_validate_passes_the_rendered_files(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    write_agents(repo)

    assert _issues(repo) == []


def test_validate_passes_a_repo_with_neither(tmp_path: Path) -> None:
    """A repo that never ran `fr init agents` is not broken: the kind is optional
    until a repo has one of the two."""
    assert _issues(_repo(tmp_path)) == []


def test_validate_fails_one_missing(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    write_agents(repo)
    (repo / ".claude" / "agents" / "fr-phase-executor.md").unlink()

    issues = _issues(repo)

    assert len(issues) == 1
    assert "fr-phase-executor.md" in issues[0] and "missing" in issues[0]


def test_validate_fails_an_unstamped_one(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    write_agents(repo)
    path = repo / ".claude" / "agents" / "fr-spec-reviewer.md"
    path.write_text(canonical_text("fr-spec-reviewer"), encoding="utf-8")

    issues = _issues(repo)

    assert len(issues) == 1
    assert issues[0].startswith("fr-spec-reviewer.md") and STAMP_KEY in issues[0]


def test_validate_fails_a_mismatched_name(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    write_agents(repo)
    path = repo / ".claude" / "agents" / "fr-spec-reviewer.md"
    path.write_text(
        path.read_text().replace("name: fr-spec-reviewer", "name: fr-phase-executor", 1)
    )

    issues = _issues(repo)

    assert len(issues) == 1 and "name" in issues[0]


def test_validate_fails_a_name_fr_does_not_ship(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    write_agents(repo)
    (repo / ".claude" / "agents" / "fr-custom.md").write_text(
        f"---\nname: fr-custom\n{STAMP_KEY}: 1\n---\n"
    )

    issues = _issues(repo)

    assert len(issues) == 1 and issues[0].startswith("fr-custom.md")
    assert "not an agent fr ships" in issues[0]


def test_validate_fails_a_stale_one(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path)
    write_agents(repo)
    import fr.artifacts.validate as validate_mod

    bumped = dataclasses.replace(KIND, current_version=KIND.current_version + 1)
    monkeypatch.setattr(validate_mod, "ARTIFACT_KINDS", {**ARTIFACT_KINDS, "agents": bumped})
    monkeypatch.setattr(validate_mod, "artifact_kind", lambda name: bumped)

    issues = _issues(repo)

    assert len(issues) == 2 and all("stale" in i for i in issues)


# --- migrate -------------------------------------------------------------------


def test_the_unstamped_repair_re_renders_the_file(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    write_agents(repo)
    path = repo / ".claude" / "agents" / "fr-spec-reviewer.md"
    path.write_text(canonical_text("fr-spec-reviewer"), encoding="utf-8")

    report = run_migrations(repo, dry_run=False)

    assert report.ok, report
    assert path.read_text() == render_agent("fr-spec-reviewer", KIND.current_version)
    assert _issues(repo) == []


def test_no_schema_migration_is_registered_while_the_kind_is_at_one() -> None:
    assert KIND.current_version == 1
    assert MIGRATIONS.schema_migrations("agents") == ()


def test_a_version_bump_re_renders_both_files_from_the_wheel(tmp_path: Path) -> None:
    from fr.artifacts.agents_kind import rerender_migration

    repo = _repo(tmp_path)
    write_agents(repo)
    bumped = dataclasses.replace(KIND, current_version=2)
    reg = MigrationRegistry(kinds={"agents": bumped})
    reg.register(rerender_migration(1, 2))

    report = run_migrations(repo, dry_run=False, registry=reg)

    assert report.ok, report
    for name in AGENT_NAMES:
        path = repo / ".claude" / "agents" / f"{name}.md"
        assert path.read_text(encoding="utf-8") == render_agent(name, 2)
    assert [m.to_version for m in reg.chain("agents", 1)] == [2]


def test_the_re_render_refuses_a_name_fr_does_not_ship_and_leaves_it_byte_identical(
    tmp_path: Path,
) -> None:
    from fr.artifacts.agents_kind import rerender_migration

    repo = _repo(tmp_path)
    write_agents(repo)
    foreign = repo / ".claude" / "agents" / "fr-custom.md"
    original = f"---\nname: fr-custom\n{STAMP_KEY}: 1\n---\nmine\n".encode()
    foreign.write_bytes(original)
    bumped = dataclasses.replace(KIND, current_version=2)
    reg = MigrationRegistry(kinds={"agents": bumped})
    reg.register(rerender_migration(1, 2))

    report = run_migrations(repo, dry_run=False, registry=reg)

    assert [f.path.name for f in report.failed] == ["fr-custom.md"]
    assert foreign.read_bytes() == original
    for name in AGENT_NAMES:
        assert (repo / ".claude" / "agents" / f"{name}.md").read_text() == render_agent(name, 2)
