"""One resolver order for every shipped default (spec 2026-11-19-event-driven-a-la-carte
R15, R16).

    repo .fr/<kind>/<name>.yaml            (workflows, verifications; never lenses)
    $FR_SHIPPED_DEFAULTS_DIR/<kind>/
    $FR_SHIPPED_<KIND>_DIR                 (kept until R14's release, with a notice)
    the wheel, fr/defaults/<kind>/
    the marketplace clone, plugins/super-fr/defaults/<kind>/
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr import _shipped

WORKFLOW = (
    "workflow: fr-goal\nschema: 1\nunit: run\n"
    "steps:\n  - id: {id}\n    kind: cli\n    run: 'true'\n"
)
LENS = "lens: tests\ntitle: from {id}\nbrief: |\n  {id}\n"


@pytest.fixture
def clean(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    for var in (_shipped.DEFAULTS_ENV_VAR, *_shipped.LEGACY_ENV_VARS.values()):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(_shipped, "_LEGACY_NOTICED", set())
    return home


def _workflow(directory: Path, step: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "fr-goal.yaml").write_text(WORKFLOW.format(id=step))


def _steps(repo: Path) -> list[str]:
    from fr.workflow.resolve import resolve_workflow

    return [s.id for s in resolve_workflow("fr-goal", repo).steps]


# ── the order itself ────────────────────────────────────────────────────────


@pytest.mark.parametrize("kind", ["workflows", "verifications", "lenses"])
def test_the_order_is_defaults_root_then_legacy_then_wheel_then_marketplace(
    kind: str, clean: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wheel = tmp_path / "wheel"
    monkeypatch.setenv(_shipped.DEFAULTS_ENV_VAR, str(tmp_path / "root"))
    monkeypatch.setenv(_shipped.LEGACY_ENV_VARS[kind], str(tmp_path / "legacy"))

    assert _shipped.shipped_dirs(kind, packaged=wheel) == [
        tmp_path / "root" / kind,
        tmp_path / "legacy",
        wheel,
        clean / _shipped.MARKETPLACE_ROOT / "plugins" / "super-fr" / "defaults" / kind,
    ]


def test_with_no_variable_the_wheel_precedes_the_marketplace(clean: Path) -> None:
    assert _shipped.shipped_dirs("workflows", packaged=Path("/w")) == [
        Path("/w"),
        clean / _shipped.MARKETPLACE_ROOT / "plugins/super-fr/defaults/workflows",
    ]


def test_an_explicit_shipped_root_replaces_both_variables(
    clean: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(_shipped.DEFAULTS_ENV_VAR, str(tmp_path / "root"))
    monkeypatch.setenv(_shipped.LEGACY_ENV_VARS["workflows"], str(tmp_path / "legacy"))

    dirs = _shipped.shipped_dirs("workflows", packaged=None, shipped_root=tmp_path / "x")

    assert dirs[0] == tmp_path / "x"
    assert tmp_path / "root" / "workflows" not in dirs
    assert tmp_path / "legacy" not in dirs


def test_the_wheel_copy_is_reached_at_fr_defaults_kind() -> None:
    found = _shipped.packaged_kind_dir("workflows")

    assert found is not None
    assert found.parts[-2:] == ("defaults", "workflows")
    assert (found / "fr-goal.yaml").is_file()


def test_an_unknown_kind_is_refused() -> None:
    with pytest.raises(ValueError, match="agents"):
        _shipped.shipped_dirs("agents", packaged=None)


# ── the legacy variables: still honoured, with one notice ───────────────────


def test_a_legacy_variable_still_resolves_and_prints_one_notice(
    clean: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    _workflow(tmp_path / "legacy", "from-legacy")
    monkeypatch.setenv("FR_SHIPPED_WORKFLOWS_DIR", str(tmp_path / "legacy"))

    assert _steps(tmp_path / "repo") == ["from-legacy"]
    assert _steps(tmp_path / "repo") == ["from-legacy"]

    err = capsys.readouterr().err
    assert err.count("FR_SHIPPED_WORKFLOWS_DIR") == 1
    assert "FR_SHIPPED_DEFAULTS_DIR" in err


def test_no_notice_without_a_legacy_variable(
    clean: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    _workflow(tmp_path / "root" / "workflows", "from-root")
    monkeypatch.setenv("FR_SHIPPED_DEFAULTS_DIR", str(tmp_path / "root"))

    assert _steps(tmp_path / "repo") == ["from-root"]
    assert capsys.readouterr().err == ""


def test_the_defaults_root_beats_the_legacy_variable(
    clean: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _workflow(tmp_path / "root" / "workflows", "from-root")
    _workflow(tmp_path / "legacy", "from-legacy")
    monkeypatch.setenv("FR_SHIPPED_DEFAULTS_DIR", str(tmp_path / "root"))
    monkeypatch.setenv("FR_SHIPPED_WORKFLOWS_DIR", str(tmp_path / "legacy"))

    assert _steps(tmp_path / "repo") == ["from-root"]


def test_a_defaults_root_without_the_kind_falls_through_to_the_legacy_variable(
    clean: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "root" / "lenses").mkdir(parents=True)
    _workflow(tmp_path / "legacy", "from-legacy")
    monkeypatch.setenv("FR_SHIPPED_DEFAULTS_DIR", str(tmp_path / "root"))
    monkeypatch.setenv("FR_SHIPPED_WORKFLOWS_DIR", str(tmp_path / "legacy"))

    assert _steps(tmp_path / "repo") == ["from-legacy"]


# ── repo beats shipped; the wheel beats the marketplace ─────────────────────


def test_a_repo_fr_workflows_manifest_beats_the_defaults_root(
    clean: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    _workflow(repo / ".fr" / "workflows", "from-repo")
    _workflow(tmp_path / "root" / "workflows", "from-root")
    monkeypatch.setenv("FR_SHIPPED_DEFAULTS_DIR", str(tmp_path / "root"))

    assert _steps(repo) == ["from-repo"]


def test_the_wheel_beats_the_marketplace_defaults_path(clean: Path, tmp_path: Path) -> None:
    _workflow(clean / _shipped.MARKETPLACE_ROOT / "plugins/super-fr/defaults/workflows", "stale")

    assert _steps(tmp_path / "repo") != ["stale"]


def test_the_marketplace_defaults_path_is_used_when_the_wheel_has_none(
    clean: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.workflow import resolve

    _workflow(clean / _shipped.MARKETPLACE_ROOT / "plugins/super-fr/defaults/workflows", "clone")
    monkeypatch.setattr(resolve, "packaged_shipped_workflows_dir", lambda: None)

    assert _steps(tmp_path / "repo") == ["clone"]


def test_a_repo_verification_beats_the_defaults_root(
    clean: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.verification.resolve import list_strategies, resolve_strategy

    repo = tmp_path / "repo"
    shipped = tmp_path / "root" / "verifications" / "candidate.yaml"
    shipped.parent.mkdir(parents=True)
    from_wheel = _shipped.packaged_kind_dir("verifications")
    assert from_wheel is not None
    text = (from_wheel / "candidate.yaml").read_text()
    shipped.write_text(text)
    monkeypatch.setenv("FR_SHIPPED_DEFAULTS_DIR", str(tmp_path / "root"))

    assert dict(list_strategies(repo))["candidate"] == "env"
    (repo / ".fr" / "verifications").mkdir(parents=True)
    (repo / ".fr" / "verifications" / "candidate.yaml").write_text(text)
    assert dict(list_strategies(repo))["candidate"] == "repo"
    assert resolve_strategy("candidate", repo).verification == "candidate"


# ── lenses take no repo directory ───────────────────────────────────────────


def test_lenses_resolve_from_the_defaults_root(
    clean: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.lenses.resolve import shipped_lens_dir

    root = tmp_path / "root"
    (root / "lenses").mkdir(parents=True)
    (root / "lenses" / "tests.yaml").write_text(LENS.format(id="root"))
    monkeypatch.setenv("FR_SHIPPED_DEFAULTS_DIR", str(root))

    assert shipped_lens_dir() == root / "lenses"


def test_lenses_never_read_a_repo_directory(
    clean: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A repo `.fr/lenses/` directory is not a lens source: `.fr/lenses.yaml`'s disable
    and replace entries stay the only repo override (R15)."""
    from fr.lenses.resolve import effective_lenses

    repo = tmp_path / "repo"
    (repo / ".fr" / "lenses").mkdir(parents=True)
    (repo / ".fr" / "lenses" / "tests.yaml").write_text(LENS.format(id="repo-dir"))
    (repo / ".fr" / "lenses" / "extra.yaml").write_text(
        LENS.format(id="repo-dir").replace("lens: tests", "lens: extra")
    )
    monkeypatch.chdir(repo)

    lenses = effective_lenses(repo)

    assert "extra" not in lenses
    assert lenses["tests"].source == "shipped"
    assert lenses["tests"].title != "from repo-dir"


def test_lenses_keep_the_lenses_yaml_override(
    clean: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.lenses.resolve import effective_lenses

    repo = tmp_path / "repo"
    (repo / ".fr").mkdir(parents=True)
    (repo / ".fr" / "lenses.yaml").write_text("disable: [simplicity]\n")
    monkeypatch.chdir(repo)

    lenses = effective_lenses(repo)

    assert "simplicity" not in lenses
    assert {"security", "tests", "errors"} <= set(lenses)
