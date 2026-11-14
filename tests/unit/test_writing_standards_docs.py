"""Writing standards for the published docs (spec 2026-11-13-writing-standards-docs)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]


def _page_globs() -> list[str]:
    return list(yaml.safe_load((REPO / ".fr/docs.yaml").read_text())["pages"])


SCRIPT = REPO / "scripts/check-writing-standards.sh"

# The page-group mapping the spec fixes (R1): standard -> the `.fr/docs.yaml` globs it covers.
GROUPS = {
    "ste": ["docs/*.md", "docs/reference/*.md"],
    "plain-language": ["docs/explainers/*.md"],
}

# The only pages whose front matter departs from their group's standard (R3).
EXCEPTIONS = {
    "docs/explainers/why-fr.md": "elements-of-style",
    "docs/explainers/index.md": "none",
    "docs/reference/cli.md": "none",
}


def _script_groups() -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for line in SCRIPT.read_text().splitlines():
        words = line.split()
        if words[:2] == ["run", "--default"]:
            groups[words[2]] = words[3:]
    return groups


def _front_matter(path: Path) -> dict[str, object]:
    text = path.read_text()
    assert text.startswith("---\n"), path
    return yaml.safe_load(text[4 : text.index("\n---\n", 4)]) or {}


def test_the_script_exists_and_is_executable() -> None:
    assert SCRIPT.is_file()
    assert SCRIPT.stat().st_mode & 0o111


def test_the_script_maps_each_group_to_its_standard() -> None:
    assert _script_groups() == GROUPS


def test_the_script_covers_exactly_the_docs_config_pages() -> None:
    covered = [glob for globs in _script_groups().values() for glob in globs]
    assert sorted(covered) == sorted(_page_globs())


def test_only_the_three_exceptions_carry_a_writing_standard_key() -> None:
    carried = {}
    for glob in _page_globs():
        for page in sorted(REPO.glob(glob)):
            meta = _front_matter(page)
            if "writing_standard" in meta:
                carried[page.relative_to(REPO).as_posix()] = meta["writing_standard"]
    assert carried == EXCEPTIONS


# A stand-in for `uv` (no network): it logs its cwd and arguments, one call per
# line, and exits with $FAKE_STE_EXIT for the ste group, $FAKE_OTHER_EXIT otherwise.
FAKE_UV = """#!/usr/bin/env bash
printf '%s\\t%s\\n' "$PWD" "$*" >> "$FAKE_UV_LOG"
case " $* " in
  *" --default ste "*) exit "$FAKE_STE_EXIT" ;;
  *) exit "$FAKE_OTHER_EXIT" ;;
esac
"""


def _run_script(
    tmp_path: Path, cwd: Path, ste_exit: int, other_exit: int
) -> tuple[int, list[list[str]], Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "uv"
    fake.write_text(FAKE_UV)
    fake.chmod(0o755)
    blog_craft = tmp_path / "blog-craft"
    blog_craft.mkdir()
    log = tmp_path / "uv.log"
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "FAKE_UV_LOG": str(log),
        "FAKE_STE_EXIT": str(ste_exit),
        "FAKE_OTHER_EXIT": str(other_exit),
    }
    proc = subprocess.run(
        ["bash", str(SCRIPT), os.path.relpath(blog_craft, cwd)],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    calls = [line.split("\t", 1) for line in log.read_text().splitlines()] if log.exists() else []
    return proc.returncode, calls, blog_craft


def _assert_both_groups_ran_at_the_toplevel(calls: list[list[str]], blog_craft: Path) -> None:
    checker = blog_craft.resolve() / "tools/validate_writing_standard.py"
    prefix = f"run --isolated --no-project --with pyyaml python {checker} --default "
    assert [cwd for cwd, _ in calls] == [str(REPO), str(REPO)]
    assert sorted(args.removeprefix(prefix).split()[0] for _, args in calls) == sorted(GROUPS)
    assert all(args.startswith(prefix) for _, args in calls)


def test_the_script_runs_every_group_from_the_toplevel_and_exits_with_the_highest_code(
    tmp_path: Path,
) -> None:
    code, calls, blog_craft = _run_script(tmp_path, REPO / "tests", ste_exit=2, other_exit=1)
    assert code == 2
    _assert_both_groups_ran_at_the_toplevel(calls, blog_craft)


def test_the_script_exits_zero_when_every_group_passes(tmp_path: Path) -> None:
    code, calls, blog_craft = _run_script(tmp_path, REPO / "tests", ste_exit=0, other_exit=0)
    assert code == 0
    _assert_both_groups_ran_at_the_toplevel(calls, blog_craft)


@pytest.mark.parametrize(("ste_exit", "other_exit"), [(1, 0), (0, 1)])
def test_a_fail_in_either_group_fails_the_script(
    tmp_path: Path, ste_exit: int, other_exit: int
) -> None:
    code, calls, _ = _run_script(tmp_path, REPO / "tests", ste_exit, other_exit)
    assert code == 1
    assert len(calls) == 2


def test_the_script_checks_its_own_repo_whatever_the_callers_directory(tmp_path: Path) -> None:
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    code, calls, blog_craft = _run_script(tmp_path, outside, ste_exit=0, other_exit=0)
    assert code == 0
    _assert_both_groups_ran_at_the_toplevel(calls, blog_craft)


def test_site_build_checks_the_writing_standards_after_the_build() -> None:
    """R6: ci.yml's site-build job runs the script over the blog-craft checkout it
    already makes, after the build, and names no blog-craft SHA itself."""
    ci_text = (REPO / ".github/workflows/ci.yml").read_text()
    steps = yaml.safe_load(ci_text)["jobs"]["site-build"]["steps"]
    runs = [s.get("run", "") for s in steps]
    build = next(i for i, r in enumerate(runs) if "scripts/build-site.py" in r)
    checks = [
        i
        for i, r in enumerate(runs)
        if r.strip() == "bash scripts/check-writing-standards.sh .blog-craft"
    ]
    assert len(checks) == 1, runs
    assert checks[0] > build
    sha = (REPO / ".github/blog-craft.ref").read_text().strip()
    assert sha not in ci_text


def test_the_docs_accuracy_lens_is_required_for_every_published_page() -> None:
    """R15: `.fr/lenses.yaml` defines `docs-accuracy` and requires it for exactly the
    page globs `.fr/docs.yaml` names."""
    config = yaml.safe_load((REPO / ".fr/lenses.yaml").read_text())
    lens = config["lenses"]["docs-accuracy"]
    assert lens["title"].strip()
    assert "`covers:`" in lens["brief"]
    assert "file:line" in lens["brief"]
    rules = [r for r in config["require"] if "docs-accuracy" in r["lenses"]]
    assert len(rules) == 1
    assert sorted(rules[0]["paths"]) == sorted(_page_globs())


def test_the_authoring_rule_says_how_a_page_stays_accurate() -> None:
    """R16: the rule names the lens, and says a page edited outside a run is checked
    against its `covers:` code by hand."""
    rule = " ".join((REPO / ".claude/rules/explainers-currency.md").read_text().split()).casefold()
    assert "`docs-accuracy`" in rule
    assert "outside an fr-goal run" in rule
    assert "`covers:` code" in rule
