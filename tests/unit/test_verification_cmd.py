"""`fr verification list|check` and the workflow `verification:` default
(spec 2026-10-06 §A, R2/R5)."""

from __future__ import annotations

import os
from pathlib import Path

from fr.cli import app
from fr.verification.check import check_strategy
from fr.verification.model import parse_strategy
from fr.workflow.check import check_workflow
from fr.workflow.model import parse_manifest
from typer.testing import CliRunner

REPO_ROOT = Path(__file__).resolve().parents[2]
runner = CliRunner()


def _invoke(repo: Path, argv: list[str], shipped: Path | None = None):
    env = {**os.environ, "VK_REPO_ROOT": str(repo)}
    if shipped is not None:
        env["FR_SHIPPED_VERIFICATIONS_DIR"] = str(shipped)
    return runner.invoke(app, argv, env=env)


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "docs" / "superpowers" / "verifications").mkdir(parents=True)
    return tmp_path


def test_list_prints_each_name_with_its_source(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "docs/superpowers/verifications/staging.yaml").write_text(
        "verification: staging\nschema: 1\nwhen: pre-merge\ndriver: operator\n"
    )

    result = _invoke(repo, ["verification", "list"])

    assert result.exit_code == 0, result.output
    lines = {line.split()[0]: line.split()[1] for line in result.output.splitlines() if line}
    assert lines["staging"] == "repo"
    assert lines["candidate"] in {"wheel", "marketplace", "env"}
    assert {"candidate", "client-live", "prerelease", "live"} <= set(lines)


def test_check_all_is_clean_on_the_shipped_set(tmp_path: Path) -> None:
    result = _invoke(_repo(tmp_path), ["verification", "check", "--all"])

    assert result.exit_code == 0, result.output
    assert "candidate: ok" in result.output


def test_check_all_exits_2_on_a_malformed_repo_manifest_naming_file_and_field(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    bad = repo / "docs/superpowers/verifications/broken.yaml"
    bad.write_text("verification: broken\nschema: 1\nwhen: later\ndriver: agent\n")

    result = _invoke(repo, ["verification", "check", "--all"])

    assert result.exit_code == 2, result.output
    assert "broken.yaml" in result.output
    assert "when" in result.output


def test_check_one_name(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    assert _invoke(repo, ["verification", "check", "live"]).exit_code == 0
    missing = _invoke(repo, ["verification", "check", "ghost"])
    assert missing.exit_code == 2
    assert "ghost" in missing.output


def test_check_with_neither_a_name_nor_all_is_a_usage_error(tmp_path: Path) -> None:
    assert _invoke(_repo(tmp_path), ["verification", "check"]).exit_code == 2


def test_check_all_fails_when_nothing_is_discoverable(tmp_path: Path, monkeypatch) -> None:
    from fr.verification import resolve as vresolve

    monkeypatch.setattr(vresolve, "packaged_shipped_verifications_dir", lambda: None)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    result = _invoke(_repo(tmp_path / "r"), ["verification", "check", "--all"])

    assert result.exit_code == 2
    assert "no verification strategies found" in result.output


def test_semantic_checks_on_a_parsed_strategy() -> None:
    post_with_install = parse_strategy(
        "verification: p\nschema: 1\nwhen: post-merge\ndriver: operator\ninstall: a {prefix}\n",
        source="p",
    )
    agent_no_scenario = parse_strategy(
        "verification: a\nschema: 1\nwhen: pre-merge\ndriver: agent\n", source="a"
    )
    source_none = parse_strategy(
        "verification: s\nschema: 1\nwhen: pre-merge\ndriver: operator\ninstall: i {source}\n",
        source="s",
    )

    assert any("post-merge" in e for e in check_strategy(post_with_install))
    assert any("scenario" in e for e in check_strategy(agent_no_scenario))
    assert any("{source}" in e for e in check_strategy(source_none))


# ── the workflow shape's `verification:` default (R5) ─────────────────


def _shape(extra: str = "") -> str:
    return (
        "workflow: x\nschema: 1\nunit: run\n" + extra + "steps:\n  - id: a\n    kind: cli\n"
        "    run: echo hi\n"
    )


def test_a_workflow_manifest_accepts_an_optional_verification_default() -> None:
    assert parse_manifest(_shape()).verification is None
    assert parse_manifest(_shape("verification: candidate\n")).verification == "candidate"


def test_check_workflow_refuses_a_verification_that_does_not_resolve(tmp_path: Path) -> None:
    m = parse_manifest(_shape("verification: ghost\n"))

    errors = check_workflow(m, repo_root=tmp_path)

    assert any("ghost" in e and "verification" in e for e in errors)
    assert (
        check_workflow(parse_manifest(_shape("verification: candidate\n")), repo_root=tmp_path)
        == []
    )


def test_the_shipped_shapes_declare_candidate_and_it_resolves() -> None:
    for name in ("fr-goal", "fr-goal-light"):
        path = REPO_ROOT / "plugins" / "super-fr" / "workflows" / f"{name}.yaml"
        m = parse_manifest(path.read_text())
        assert m.verification == "candidate", name
        assert check_workflow(m, repo_root=REPO_ROOT) == [], name


def test_workflow_check_cli_refuses_an_unresolvable_verification(tmp_path: Path) -> None:
    repo = tmp_path
    d = repo / "docs" / "superpowers" / "workflows"
    d.mkdir(parents=True)
    (d / "bad.yaml").write_text(
        _shape("verification: ghost\n").replace("workflow: x", "workflow: bad")
    )

    result = _invoke(repo, ["workflow", "check", "bad"])

    assert result.exit_code == 1
    assert "ghost" in result.output
