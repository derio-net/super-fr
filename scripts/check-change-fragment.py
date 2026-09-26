#!/usr/bin/env python3
"""The `change-fragment` PR gate (spec 2026-09-26-version-bump-churn §3.B, §3.E).

    scripts/check-change-fragment.py <base-ref>

Three rules over the diff `<base>...HEAD` (so against the merge base, never
the base tip — a release on main after the branch point is not this PR's
version edit):

1. **Bump-required paths need a fragment.** If a changed path `requires_bump`,
   the diff must ADD a valid `.changes/<slug>.yaml`. Modifying or deleting an
   existing fragment does not count; any fragment the diff touches must parse.
2. **PRs never change a version value.** Every `version_surfaces()` value is
   read at the merge base and at HEAD; a changed value fails, naming the file.
   A surface the PR adds (a new member's `pyproject.toml`, its `uv.lock` entry,
   a new plugin manifest) passes only when it equals the base version.
3. **Floors name the predicted release.** A `fr_version` floor the diff adds
   under `packages/*/src` whose lower bound is newer than the base version must
   equal `base + the highest bump of the added fragments`.

Stdlib only, so it runs under `uv run --no-project` and plain `python`.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import changes  # noqa: E402
import floors  # noqa: E402
import version_surfaces as vs  # noqa: E402

REPO = Path(__file__).resolve().parent.parent

VERSION_REQUIRED_EXACT = {
    "scripts/install.sh",
    "scripts/install-validator-wrapper.sh",
    "scripts/validate-plans.sh",
}

# Basenames of every file `version_surfaces()` may read. Only a superset filter
# for materialising a ref: which of them are surfaces stays version_surfaces'
# decision, so the surface list itself is not duplicated here.
_SURFACE_BASENAMES = {
    "pyproject.toml",
    "package.json",
    "plugin.json",
    "marketplace.json",
    "uv.lock",
}


def requires_bump(path: str) -> bool:
    if path in VERSION_REQUIRED_EXACT:
        return True
    if path.startswith("plugins/super-fr/skills/") or path.startswith("plugins/super-fr/rules/"):
        return True
    return path.startswith("packages/") and "/src/" in path


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout


def _show(repo: Path, ref: str, path: str) -> str | None:
    """`path`'s text at `ref`, or None when it does not exist there."""
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"], cwd=repo, capture_output=True, text=True
    )
    return result.stdout if result.returncode == 0 else None


@dataclass(frozen=True)
class Diff:
    """What the PR changed, read once and shared by rules 1, 2 and 3.

    `base` is the merge base, `status` maps each changed path to its status
    (A, M, D, T). File contents come from git at `base` / `HEAD`, never the
    working tree, so an uncommitted edit cannot make a red PR look green.
    """

    repo: Path
    base: str
    status: dict[str, str]

    def present(self) -> list[str]:
        """Changed paths that still exist at HEAD."""
        return [p for p, s in self.status.items() if s != "D"]

    def before(self, path: str) -> str | None:
        return None if self.status.get(path) == "A" else _show(self.repo, self.base, path)

    def after(self, path: str) -> str:
        text = _show(self.repo, "HEAD", path)
        if text is None:
            raise FileNotFoundError(f"{path} is not in HEAD")
        return text


def read_diff(repo: Path, base_ref: str) -> Diff:
    """The one diff reader: merge base plus name-status of `<base_ref>...HEAD`."""
    base = _git(repo, "merge-base", base_ref, "HEAD").strip()
    status: dict[str, str] = {}
    for line in _git(repo, "diff", "--name-status", "--no-renames", base, "HEAD").splitlines():
        if line.strip():
            code, path = line.split("\t", 1)
            status[path] = code[0]
    return Diff(repo, base, status)


def surfaces_at(repo: Path, ref: str) -> dict[tuple[str, str], str]:
    """`version_surfaces()` at `ref`: its surface files materialised into a temp dir."""
    names = _git(repo, "ls-tree", "-r", "--name-only", ref).splitlines()
    with tempfile.TemporaryDirectory(prefix="fr-surfaces-") as tmp:
        root = Path(tmp)
        for name in names:
            if name.rsplit("/", 1)[-1] in _SURFACE_BASENAMES:
                text = _show(repo, ref, name)
                if text is not None:
                    (root / name).parent.mkdir(parents=True, exist_ok=True)
                    (root / name).write_text(text)
        return {(s.file, s.locator): s.value for s in vs.version_surfaces(root)}


def base_version(surfaces: dict[tuple[str, str], str]) -> str:
    return surfaces[(vs.ROOT_PYPROJECT, "project.version")]


def fragment_slug(repo: Path) -> str:
    branch = os.environ.get("GITHUB_HEAD_REF") or ""
    if not branch:
        branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()
    if not branch or branch == "HEAD":
        return "<branch-slug>"
    return branch.replace("/", "-")


def check_fragments(diff: Diff) -> tuple[list[str], list[changes.Fragment]]:
    """Rule 1. Returns (errors, the valid fragments this diff adds)."""
    errors: list[str] = []
    added: list[changes.Fragment] = []
    for path in diff.present():
        if not changes.is_fragment_path(path):
            continue
        try:
            bump, summary = changes.parse_text(diff.after(path), path)
        except changes.FragmentError as exc:
            errors.append(f"invalid fragment — {exc}")
            continue
        if diff.status[path] == "A":
            added.append(changes.Fragment(diff.repo / path, bump, summary))

    required = [p for p in diff.status if requires_bump(p)]
    if required and not added:
        slug = fragment_slug(diff.repo)
        lines = [
            "user-observable changes need a change fragment added by this PR "
            "(modifying an existing one does not count).",
            f"  fix: add .changes/{slug}.yaml with bump: patch "
            "(or minor/major if warranted) and a one-line summary",
            "  paths requiring a release:",
            *(f"    - {p}" for p in required),
        ]
        errors.append("\n".join(lines))
    return errors, added


def check_versions(base: dict[tuple[str, str], str], head: dict[tuple[str, str], str]) -> list[str]:
    """Rule 2: no surface value changes; an added surface equals the base version."""
    version = base_version(base)
    bad: list[str] = []
    for (file, locator), value in head.items():
        before = base.get((file, locator))
        if before is None and value != version:
            bad.append(f"    - {file} ({locator}): added at {value}, base version is {version}")
        elif before is not None and value != before:
            bad.append(f"    - {file} ({locator}): {before} -> {value}")
    if not bad:
        return []
    return [
        "\n".join(
            [
                "this PR changes a version value; PRs never edit a version.",
                "  fix: revert the version edit — main assigns the number",
                *bad,
            ]
        )
    ]


def check_floors(diff: Diff, base: str, predicted: str) -> list[str]:
    """Rule 3: an added floor newer than base must name the predicted release."""
    bad: list[str] = []
    for path in diff.present():
        if not floors.is_floor_path(path):
            continue
        for floor in floors.new_floors(diff.before(path), diff.after(path)):
            if not floors.lower_bound_ok(floor.lower, base, predicted):
                bad.append(
                    f"    - {path}:{floor.line}: >={floor.lower} names an unreleased version; "
                    f"this PR releases as {predicted} (base {base} + its fragment)"
                )
    if not bad:
        return []
    return [
        "\n".join(
            [
                "an fr_version floor names a release other than the one this PR predicts.",
                f"  fix: floor it at >={predicted}, or change the fragment's bump",
                *bad,
            ]
        )
    ]


def check(repo: Path, base_ref: str) -> list[str]:
    """Every gate failure for `<base_ref>...HEAD` in `repo`; empty means pass."""
    repo = Path(repo)
    diff = read_diff(repo, base_ref)
    errors, added = check_fragments(diff)
    base_surfaces = surfaces_at(repo, diff.base)
    errors += check_versions(base_surfaces, surfaces_at(repo, "HEAD"))
    base = base_version(base_surfaces)
    predicted = changes.bumped(base, changes.aggregate(added))
    errors += check_floors(diff, base, predicted)
    return errors


def main(argv: list[str] | None = None, repo: Path | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: scripts/check-change-fragment.py <base-ref>", file=sys.stderr)
        return 2
    errors = check(repo or REPO, args[0])
    if not errors:
        print("ok — change-fragment gate passed")
        return 0
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
