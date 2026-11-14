"""Two defects a live walk of 7.0.0rc5 found at the plan step (debug journal
2026-11-14-placement-repair-and-design-slug).

1. `fr repair --yes` under quiet and stealth asked the PRODUCT checkout's git about the
   superpowers dir, which sits in the `fr` worktree or the tracking clone: git exits 128
   and the guard raised a `CalledProcessError` traceback. `paths_dirty` now asks each
   path's own checkout, and a git failure is a refusal.
2. A row citing `spec:<stem>-design#R<n>` resolves (the resolver tries `<slug>.md`) but
   matched no spec: `origin_fragment` compared it with the stem minus `-design`. Every
   reader of the rows citing a spec saw none, so `fr plan self-review` refused the plan.
   Not placement-specific; the stealth walk's agent happened to spell it that way.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml
from fr.archive import paths_dirty
from fr.artifacts.paths import KIND_DIRS
from fr.requirements import is_cited, origin_fragment

from tests.unit.test_placement_plan_paths import SLUG, SPEC, _create, _fr, quiet  # noqa: F401

SPEC_REF = f"derio-net/q:{KIND_DIRS['spec']}/{SPEC}"


def _git(cwd: Path, *argv: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *argv], check=True, capture_output=True)


def _repo(path: Path) -> Path:
    path.mkdir(parents=True)
    _git(path, "init", "-q", "-b", "main")
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "t")
    (path / "a.txt").write_text("a\n")
    _git(path, "add", "-A")
    _git(path, "commit", "-qm", "seed")
    return path


# --- 1. paths_dirty asks the checkout that holds each path ------------------------------


def test_paths_dirty_reads_a_path_held_by_another_checkout(tmp_path: Path) -> None:
    product = _repo(tmp_path / "product")
    other = _repo(tmp_path / "other")
    assert paths_dirty(product, other / "a.txt") is False
    (other / "a.txt").write_text("changed\n")
    assert paths_dirty(product, other / "a.txt") is True
    assert paths_dirty(product, product / "a.txt") is False


def test_paths_dirty_refuses_rather_than_raising_when_git_cannot_answer(
    tmp_path: Path,
) -> None:
    product = _repo(tmp_path / "product")
    stray = tmp_path / "not-a-repo"
    stray.mkdir()
    from fr.archive import GitStatusError

    with pytest.raises(GitStatusError, match="cannot read the git status"):
        paths_dirty(product, stray)


def test_fr_repair_yes_under_quiet_rewrites_the_absolute_spec_ref(
    quiet: tuple[Path, Path],  # noqa: F811
    tmp_path: Path,
) -> None:
    worktree, feature = quiet
    plan_dir = _create(worktree, tmp_path, SPEC)
    meta = plan_dir / "_meta.yaml"
    doc = yaml.safe_load(meta.read_text())
    doc["spec"] = str(feature / KIND_DIRS["spec"] / SPEC)  # what rc4's `plan create` left
    meta.write_text(yaml.safe_dump(doc, sort_keys=False))
    _git(feature, "add", "-A")  # the fixture's spec, and the stale ref
    _git(feature, "commit", "-qm", "a stale absolute spec ref")

    code, out = _fr(worktree, "repair")
    assert code == 0, out
    assert "would repair" in out, out
    code, out = _fr(worktree, "repair", "--yes")
    assert code == 0, out
    assert "Traceback" not in out, out
    assert yaml.safe_load(meta.read_text())["spec"] == SPEC


def test_fr_repair_yes_under_quiet_refuses_a_dirty_feature_root(
    quiet: tuple[Path, Path],  # noqa: F811
    tmp_path: Path,
) -> None:
    worktree, _ = quiet
    plan_dir = _create(worktree, tmp_path, SPEC)
    (plan_dir / "_prose.md").write_text("an uncommitted edit\n")
    code, out = _fr(worktree, "repair", "--yes")
    assert code == 2, out
    assert "uncommitted changes" in out, out


# --- 2. a logical origin spelled with the spec file's `-design` stem --------------------


@pytest.mark.parametrize("slug", [SLUG, f"{SLUG}-design"])
def test_a_logical_origin_names_its_spec_with_or_without_design(slug: str) -> None:
    assert origin_fragment(f"spec:{slug}#R1", SPEC_REF) == "R1"


def test_is_cited_reads_a_design_spelled_origin() -> None:
    from fr.acceptance.model import Matrix, Row

    row = Row.model_validate(
        {
            "id": "q-hello",
            "capability": "hello",
            "acceptance": "the tool says hello",
            "origin": [f"spec:{SLUG}-design#R1"],
            "status": "not-implemented",
        }
    )
    assert is_cited("R1", Matrix(rows=[row]), SPEC_REF)


def test_a_design_spelled_origin_is_written_canonically_in_the_runs_fragment(
    quiet: tuple[Path, Path],  # noqa: F811
) -> None:
    worktree, feature = quiet
    code, out = _fr(
        worktree, "acceptance", "add", "--id", "q-two", "--capability", "two",
        "--acceptance", "a second row", "--origin", f"spec:{SLUG}-design#R1",
        "--status", "not-implemented", "--notes", "n", "--repo", "derio-net/q",
    )  # fmt: skip
    assert code == 0, out
    frags = feature / KIND_DIRS["acceptance-fragment"]
    assert not (frags / f"{SLUG}-design.yaml").exists(), sorted(p.name for p in frags.iterdir())
    rows = {r["id"]: r for r in yaml.safe_load((frags / f"{SLUG}.yaml").read_text())["rows"]}
    assert rows["q-two"]["origin"] == [f"spec:{SLUG}#R1"]


def test_plan_self_review_passes_a_plan_whose_rows_spell_the_design_stem(
    quiet: tuple[Path, Path],  # noqa: F811
    tmp_path: Path,
) -> None:
    worktree, feature = quiet
    # A row as the stealth walk's agent wrote it, committed before this fix: the
    # fragment named after the `-design` stem, the origin spelled the same way.
    frags = feature / KIND_DIRS["acceptance-fragment"]
    own = frags / f"{SLUG}.yaml"
    doc = yaml.safe_load(own.read_text())
    doc["rows"][0]["origin"] = [f"spec:{SLUG}-design#R1"]
    (frags / f"{SLUG}-design.yaml").write_text(
        yaml.safe_dump({**doc, "feature": f"{SLUG}-design"}, sort_keys=False)
        if "feature" in doc
        else yaml.safe_dump(doc, sort_keys=False)
    )
    own.unlink()
    _git(frags, "add", "-A")
    _git(frags, "commit", "-qm", "a design-spelled row")
    plan_dir = _create(worktree, tmp_path, SPEC)
    code, out = _fr(worktree, "plan", "self-review", str(plan_dir))
    assert "serves no ask" not in out, out
    assert "no matrix row citing the spec" not in out, out
    assert code == 0, out
