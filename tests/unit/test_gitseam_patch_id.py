"""`Checkout.patch_id`: the content an approval is pinned to (spec
2026-11-19-wave-merge-queue R12, §E), against a real throwaway repo."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.triage.gitseam import Checkout


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _commit(cwd: Path, message: str, *, empty: bool = False) -> str:
    _git(cwd, "add", "-A")
    _git(cwd, "commit", "--quiet", *(["--allow-empty"] if empty else []), "-m", message)
    return _git(cwd, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """`main` with two files, and `feat` branched from it with one code change."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "--quiet", "--initial-branch=main")
    for k, v in (("user.name", "t"), ("user.email", "t@example.com"), ("commit.gpgsign", "false")):
        _git(root, "config", k, v)
    (root / "code.py").write_text("def f():\n    return 1\n")
    (root / "other.txt").write_text("other\n")
    _commit(root, "seed")
    _git(root, "checkout", "--quiet", "-b", "feat")
    (root / "code.py").write_text("def f():\n    return 2\n")
    _commit(root, "feat: change f")
    return root


def test_a_conflict_free_merge_of_main_keeps_the_patch_id(repo: Path) -> None:
    checkout = Checkout(repo)
    before = checkout.patch_id("feat", "main")
    _git(repo, "checkout", "--quiet", "main")
    (repo / "other.txt").write_text("other, moved on main\n")
    _commit(repo, "main moves")
    _git(repo, "checkout", "--quiet", "feat")
    _git(repo, "merge", "--quiet", "--no-edit", "main")

    assert before
    assert checkout.patch_id("feat", "main") == before


def test_an_empty_commit_keeps_the_patch_id(repo: Path) -> None:
    checkout = Checkout(repo)
    before = checkout.patch_id("feat", "main")
    _commit(repo, "nothing", empty=True)

    assert checkout.patch_id("feat", "main") == before


def test_a_code_edit_changes_the_patch_id(repo: Path) -> None:
    checkout = Checkout(repo)
    before = checkout.patch_id("feat", "main")
    (repo / "code.py").write_text("def f():\n    return 3\n")
    _commit(repo, "edit")

    assert checkout.patch_id("feat", "main") != before


def test_a_whitespace_only_edit_changes_the_patch_id(repo: Path) -> None:
    checkout = Checkout(repo)
    before = checkout.patch_id("feat", "main")
    (repo / "code.py").write_text("def f():\n    return 2 \n")
    _commit(repo, "trailing space")

    assert checkout.patch_id("feat", "main") != before


def test_a_binary_edit_changes_the_patch_id(repo: Path) -> None:
    checkout = Checkout(repo)
    (repo / "blob.bin").write_bytes(bytes(range(256)))
    _commit(repo, "add a binary")
    before = checkout.patch_id("feat", "main")
    (repo / "blob.bin").write_bytes(bytes(reversed(range(256))))
    _commit(repo, "edit the binary")

    assert checkout.patch_id("feat", "main") != before


def test_an_empty_diff_has_an_empty_patch_id(repo: Path) -> None:
    assert Checkout(repo).patch_id("main", "main") == ""


# ------------------------------------------------------------------ the command's reader


def _clone_with_a_pr(tmp_path: Path) -> tuple[Path, Path, str]:
    """A bare origin with `main` and `feat` (the PR), and a clone that fetched only `main`:
    the PR's head is unknown to it."""
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "--quiet", "--bare", "--initial-branch=main", str(origin))
    work = tmp_path / "work"
    _git(tmp_path, "clone", "--quiet", str(origin), str(work))
    for k, v in (("user.name", "t"), ("user.email", "t@example.com"), ("commit.gpgsign", "false")):
        _git(work, "config", k, v)
    _git(work, "checkout", "--quiet", "-b", "main")
    (work / "code.py").write_text("x = 1\n")
    _commit(work, "seed")
    _git(work, "push", "--quiet", "origin", "main")
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "--quiet", "--branch", "main", str(origin), str(clone))
    _git(work, "checkout", "--quiet", "-b", "feat")
    (work / "code.py").write_text("x = 2\n")
    head = _commit(work, "feat")
    _git(work, "push", "--quiet", "origin", "feat")
    return work, clone, head


def test_the_reader_fetches_the_pr_branch_and_reads_against_origin_default(
    tmp_path: Path,
) -> None:
    from fr.commands.triage_batch_cmd import patch_id_reader

    work, clone, head = _clone_with_a_pr(tmp_path)
    reader = patch_id_reader(Checkout(clone), {7: "feat"})

    assert reader(7, head) == Checkout(work).patch_id(head, "main") != ""


def test_the_reader_says_none_when_git_cannot(tmp_path: Path) -> None:
    from fr.commands.triage_batch_cmd import patch_id_reader

    _, clone, head = _clone_with_a_pr(tmp_path)
    reader = patch_id_reader(Checkout(clone), {7: "feat"})

    assert reader(8, head) is None  # no branch known for the PR
    assert reader(7, "f" * 40) is None  # a head the branch does not hold


# ------------------------------------------------------------------ the known limit (p1-r1)


def test_a_moved_identical_hunk_keeps_the_patch_id(tmp_path: Path) -> None:
    """`git patch-id` drops hunk line numbers, so a change that moves an otherwise
    identical hunk (same lines, same context) within a file keeps the id, and with it the
    approval. R12 states this limit; this test pins it, so the doc claim is tested."""
    root = tmp_path / "moved"
    root.mkdir()
    _git(root, "init", "--quiet", "--initial-branch=main")
    for k, v in (("user.name", "t"), ("user.email", "t@example.com"), ("commit.gpgsign", "false")):
        _git(root, "config", k, v)
    block = ["a", "b", "c", "X", "d", "e", "f"]
    filler = [f"line {n}" for n in range(20)]
    (root / "f.txt").write_text("\n".join([*block, *filler, *block]) + "\n")
    _commit(root, "seed")
    _git(root, "checkout", "--quiet", "-b", "feat")
    edited = ["a", "b", "c", "Y", "d", "e", "f"]
    (root / "f.txt").write_text("\n".join([*edited, *filler, *block]) + "\n")
    _commit(root, "edit the first copy")
    checkout = Checkout(root)
    before = checkout.patch_id("feat", "main")
    (root / "f.txt").write_text("\n".join([*block, *filler, *edited]) + "\n")
    _commit(root, "move the edit to the second copy")

    assert before
    assert checkout.patch_id("feat", "main") == before


# ------------------------------------------------------------------ host-independent (p1-r2)


def _hostile(repo: Path) -> None:
    """Diff configuration a host may carry, each of which would change porcelain `git
    diff`'s output: none of it may change the patch-id."""
    for k, v in (
        ("diff.noprefix", "true"),
        ("diff.mnemonicPrefix", "true"),
        ("diff.renames", "copies"),
        ("diff.algorithm", "histogram"),
        ("diff.context", "9"),
        ("diff.interHunkContext", "20"),
        ("diff.indentHeuristic", "false"),
        ("diff.suppressBlankEmpty", "true"),
        ("diff.external", "false"),
        ("diff.orderFile", str(repo / "order")),
        ("core.quotePath", "false"),
        ("patchid.stable", "true"),
    ):
        _git(repo, "config", k, v)
    (repo / "order").write_text("other.txt\ncode.py\n")


def test_hostile_diff_configuration_does_not_change_the_patch_id(repo: Path) -> None:
    (repo / "other.txt").write_text("other, on feat\n")
    (repo / "naïve.txt").write_text("x\n")
    _commit(repo, "two more files")
    plain = Checkout(repo).patch_id("feat", "main")
    _hostile(repo)

    assert plain
    assert Checkout(repo).patch_id("feat", "main") == plain


def test_a_textconv_attribute_does_not_hide_a_binary_edit(repo: Path) -> None:
    """A textconv driver that maps every blob to the same text (as a size-only or
    metadata-only converter would) must not make a same-size binary edit look unchanged."""
    _git(repo, "config", "diff.same.textconv", "sh -c 'echo same'")
    _git(repo, "config", "diff.same.binary", "false")
    info = repo / ".git" / "info"
    info.mkdir(parents=True, exist_ok=True)
    (info / "attributes").write_text("*.bin diff=same\n")
    (repo / "blob.bin").write_bytes(bytes(range(256)))
    _commit(repo, "add a binary")
    checkout = Checkout(repo)
    before = checkout.patch_id("feat", "main")
    (repo / "blob.bin").write_bytes(bytes(reversed(range(256))))
    _commit(repo, "same size, other bytes")

    assert checkout.patch_id("feat", "main") != before


def test_an_external_diff_driver_is_never_run(repo: Path, tmp_path: Path) -> None:
    marker = tmp_path / "ran"
    _git(repo, "config", "diff.external", f"sh -c 'touch {marker}'")
    _git(repo, "config", "diff.ext.command", f"sh -c 'touch {marker}'")
    info = repo / ".git" / "info"
    info.mkdir(parents=True, exist_ok=True)
    (info / "attributes").write_text("*.py diff=ext\n")

    assert Checkout(repo).patch_id("feat", "main")
    assert not marker.exists()
