"""Tripwire: the README's generated tables match their sources, and it stays short.

`scripts/sync-readme.py` fills the `skills` and `cli` blocks in `README.md` and the
`cli-tree` block in `docs/reference/cli.md` from the skills' front matter and the
`fr` Typer app (spec 2026-11-11-docs-currency R20, R21). Drift detection lives in the
script (`find_drift`); this test calls it, so the CI gate and `--check` cannot disagree.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest
import typer

REPO_ROOT = Path(__file__).resolve().parents[2]

_spec = importlib.util.spec_from_file_location(
    "sync_readme", REPO_ROOT / "scripts" / "sync-readme.py"
)
assert _spec is not None and _spec.loader is not None
sync_readme = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync_readme)

README_LINE_LIMIT = 200


def _skill(root: Path, plugin: str, name: str, description: str) -> None:
    d = root / "plugins" / plugin / "skills" / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: >\n  {description}\n---\n\nbody\n"
    )


def _app() -> typer.Typer:
    app = typer.Typer(help="root")
    sub = typer.Typer(help="Manage things. Second sentence.")

    @sub.command("add")
    def add() -> None:
        """Add a thing | with a pipe."""

    @sub.command("hidden-one", hidden=True)
    def hidden() -> None:
        """Never listed."""

    @app.command("status")
    def status() -> None:
        """Show state.

        Longer paragraph that must not appear.
        """

    app.add_typer(sub, name="things")
    return app


def test_the_repo_is_in_sync() -> None:
    drift = sync_readme.find_drift()
    assert not drift, "\n".join(drift) + (
        "\n\nRun `uv run python scripts/sync-readme.py` (no --check) to fix, then commit."
    )


def test_check_flag_exits_zero_on_the_repo() -> None:
    done = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "sync-readme.py"), "--check"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert done.returncode == 0, done.stderr


def test_the_readme_is_a_front_door() -> None:
    lines = (REPO_ROOT / "README.md").read_text().count("\n")
    assert lines <= README_LINE_LIMIT, (
        f"README.md is {lines} lines; the front door is at most {README_LINE_LIMIT}. "
        "Reference material belongs in docs/reference/ (spec R20)."
    )


def test_skills_table_is_name_plugin_first_sentence(tmp_path: Path) -> None:
    _skill(tmp_path, "super-fr", "fr-b", "Does B. Use when asked.")
    _skill(tmp_path, "super-fr-dispatch", "fr-a", "Does A with `code`. More.")
    rows = sync_readme.skill_rows(tmp_path)
    assert rows == [
        ("fr-a", "super-fr-dispatch", "Does A with `code`."),
        ("fr-b", "super-fr", "Does B."),
    ]
    table = sync_readme.skills_table(rows)
    assert table.splitlines()[0] == "| Skill | Plugin | What it is for |"
    assert "| `fr-a` | super-fr-dispatch | Does A with `code`. |" in table


def test_a_long_first_sentence_is_cut_at_a_clause(tmp_path: Path) -> None:
    long = "Alpha beta, " + "word " * 60 + "end."
    out = sync_readme.first_sentence(long, limit=60)
    assert len(out) <= 61
    assert out.endswith("…")
    assert "\n" not in out


def test_cli_table_lists_top_level_commands_only() -> None:
    table = sync_readme.cli_table(sync_readme.cli_rows(_app()))
    assert "| `fr status` | Show state. |" in table
    assert "| `fr things` | Manage things. |" in table
    assert "fr things add" not in table
    assert "Longer paragraph" not in table


def test_cli_tree_lists_subcommands_and_skips_hidden_ones() -> None:
    tree = sync_readme.cli_tree(_app())
    assert "- `fr status`: Show state." in tree
    assert "- `fr things`: Manage things." in tree
    assert "  - `fr things add`: Add a thing \\| with a pipe." in tree
    assert "hidden-one" not in tree


def test_replace_block_rewrites_only_between_the_markers() -> None:
    text = "before\n<!-- generated:x -->\nold\n<!-- /generated:x -->\nafter\n"
    out = sync_readme.replace_block(text, "x", "new")
    assert out == "before\n<!-- generated:x -->\nnew\n<!-- /generated:x -->\nafter\n"
    assert sync_readme.replace_block(out, "x", "new") == out


def test_replace_block_refuses_a_missing_marker() -> None:
    with pytest.raises(sync_readme.MarkerError):
        sync_readme.replace_block("no markers here\n", "x", "new")


def test_no_flag_writes_and_check_does_not(tmp_path: Path) -> None:
    (tmp_path / "docs" / "reference").mkdir(parents=True)
    readme = tmp_path / "README.md"
    cli = tmp_path / "docs" / "reference" / "cli.md"
    readme.write_text(
        "<!-- generated:skills -->\n<!-- /generated:skills -->\n"
        "<!-- generated:cli -->\n<!-- /generated:cli -->\n"
    )
    cli.write_text("<!-- generated:cli-tree -->\n<!-- /generated:cli-tree -->\n")
    _skill(tmp_path, "super-fr", "fr-a", "Does A.")
    before = readme.read_text()
    assert sync_readme.find_drift(tmp_path, _app())
    assert readme.read_text() == before
    sync_readme.write_all(tmp_path, _app())
    assert "`fr-a`" in readme.read_text()
    assert "- `fr status`" in cli.read_text()
    assert sync_readme.find_drift(tmp_path, _app()) == []
