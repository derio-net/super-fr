"""The skills branch on `fr services` where they assumed CI or an issue tracker."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SK = ROOT / "plugins" / "super-fr" / "skills"


def _t(name: str) -> str:
    return (SK / name / "SKILL.md").read_text()


def test_fr_goal_branches_on_services() -> None:
    t = _t("fr-goal")
    assert "fr services" in t
    assert "ci none" in t and "local suite on a trivial test" in t
    assert "tracking none" in t and "stays out-of-scope" in t
    assert "local suite green (evidence: <log>)" in t
    assert "no tracker is configured" in t


def test_fr_goal_never_asks_to_file_under_tracking_none() -> None:
    """R6: no skill tells an agent to file an issue — the PR body's
    'which out-of-scope findings to file' and review-phase's `deferred`
    branch too."""
    t = _t("fr-goal")
    assert "says `tracking none` → there is no issue to cite: it stays out-of-scope" in t
    assert "which out-of-scope findings to file (none under `tracking none`" in t


def test_fr_acceptance_local_suite_is_the_gate() -> None:
    t = _t("fr-acceptance")
    assert "ci: none" in t and "the local suite is the gate" in t


def test_fr_init_documents_services() -> None:
    t = _t("fr-init")
    assert "--ci" in t and "--tracking" in t
    assert "forge" in t and "tracking" in t
    assert "ask the operator" in t and "re-run" in t


def test_readme_mentions_services() -> None:
    t = (ROOT / "README.md").read_text()
    assert "fr services" in t and "tracking:" in t
