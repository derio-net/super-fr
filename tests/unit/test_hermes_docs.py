"""HERMES.md + README must document Hermes Agent support correctly.

`HERMES.md` is this repo's Hermes project-context file. Hermes loads exactly ONE
project context file (`.hermes.md`/`HERMES.md` → `AGENTS.md` → `CLAUDE.md`,
first match wins) and has no include mechanism — so HERMES.md *shadows*
`AGENTS.md` for every Hermes session. That makes two things load-bearing:

1. it must point at `AGENTS.md` (which must still exist) so the full guide is
   one tool call away rather than silently lost;
2. it must inline the invariants that are unsafe to discover late (isolation,
   never commit to main, change fragment instead of a version edit, regenerate
   mirrors).

The README must document how to install into a Hermes Agent, mirroring the
OpenCode opt-in note — an undocumented install path is invisible to consumers.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HERMES_MD = REPO_ROOT / "HERMES.md"
README = REPO_ROOT / "README.md"


def test_hermes_md_exists() -> None:
    assert HERMES_MD.is_file(), "HERMES.md must exist as the Hermes project context"


def test_hermes_md_points_at_an_agents_guide_that_exists() -> None:
    text = HERMES_MD.read_text()
    assert "AGENTS.md" in text, (
        "HERMES.md shadows AGENTS.md for Hermes sessions — it must point at it "
        "so the canonical guide is not silently lost"
    )
    assert (REPO_ROOT / "AGENTS.md").is_file(), "the pointer must not dangle"


def test_hermes_md_inlines_the_non_negotiables() -> None:
    text = HERMES_MD.read_text()
    for needle, why in [
        ("fr isolation up", "isolation entry is the primary invariant"),
        (".fr-isolation", "the marker/gate must be named"),
        (".changes/", "the release rule (add a change fragment) must be inline"),
        ("sync-hermes.py", "generated mirrors must not be hand-edited"),
    ]:
        assert needle in text, f"HERMES.md must inline {needle!r} — {why}"


def test_hermes_md_states_main_protection_accurately() -> None:
    """Spec 2026-09-26-version-bump-churn §3.C: the ruleset forbids only
    force-push and deletion, so "branch protection blocks direct pushes"
    overstates it; the process forbids direct commits and only the release
    bot commits to `main`."""
    text = " ".join(HERMES_MD.read_text().split())
    assert "Branch protection blocks direct pushes" not in text, (
        "the ruleset does not block direct pushes; only the process forbids them"
    )
    for needle in ("forbids only force-push and deletion", "only the release bot commits"):
        assert needle in text, f"HERMES.md must state {needle!r} (spec §3.C)"


def test_hermes_md_release_rule_never_runs_bump_version_in_a_pr() -> None:
    text = " ".join(HERMES_MD.read_text().split())
    assert "bump-version.py {patch|minor|major}" not in text, (
        "a PR never runs bump-version.py — release.yml assigns the number"
    )
    assert "workflow_dispatch" in text, "the explicit-number escape must be named"


def test_hermes_md_documents_the_first_run_model_question() -> None:
    text = HERMES_MD.read_text()
    assert "fr models" in text and "unbound" in text, (
        "HERMES.md must state that no hermes model bindings ship and fr-goal "
        "asks per tier on first run — otherwise an agent may invent model ids"
    )


def test_readme_documents_hermes_install() -> None:
    text = README.read_text()
    assert "HERMES_SKILLS_INSTALL" in text, (
        "README must document the Hermes opt-in env var, mirroring the OpenCode note"
    )
    assert "~/.hermes" in text or ".hermes" in text, "README must name where Hermes artifacts land"
    assert "`config.yaml` `hooks:`" in text, (
        "README must name Hermes's actual hook configuration file; "
        "cli-config.yaml is obsolete and leaves hooks inert"
    )


def test_readme_documents_hermes_uninstall_path() -> None:
    text = README.read_text()
    assert "fr hermes" in text, (
        "README must mention the `fr hermes install/uninstall` subcommand that "
        "wires and reverses the hooks/rules"
    )
