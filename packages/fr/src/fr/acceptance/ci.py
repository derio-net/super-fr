"""Does this repo have CI? — the one answer `init` and the `ci` status share.

A matrix row's `ci` status means "a CI run is the evidence", and `fr acceptance
init` scaffolds a pipeline for the forge's CI system. Both used to key off the
forge backend alone (gh#775), so a GitLab project with no CI got a
`.gitlab-ci.yml` it never asked for and rows went to `ci` with nothing to run
them. The fact they were missing is whether the repo already carries a CI
config for its backend; this module is the only place that looks.

gh#774 later replaces the detection with a declared `ci:` service (`type:
none` switches CI off); the callers ask `ci_config` and need not change.
"""

from __future__ import annotations

from pathlib import Path

from fr._hosts import HostBackend

# Where each backend's CI system reads its pipeline definitions. Gitea Actions
# falls back to `.github/workflows/` when `.gitea/workflows/` is absent.
CI_CONFIG_PATHS: dict[HostBackend, tuple[str, ...]] = {
    "github": (".github/workflows",),
    "gitea": (".gitea/workflows", ".github/workflows"),
    "gitlab": (".gitlab-ci.yml",),
}

# The file `fr acceptance init` scaffolds, per backend.
SCAFFOLD_PATHS: dict[HostBackend, str] = {
    "github": ".github/workflows/acceptance-report.yml",
    "gitea": ".gitea/workflows/acceptance-report.yml",
    "gitlab": ".gitlab-ci.yml",
}


def ci_config(root: Path, backend: HostBackend) -> str | None:
    """The repo-relative CI config `root` carries for `backend`, or None.

    A workflows directory counts only when it holds a `.yml`/`.yaml` file: an
    empty directory runs nothing."""
    for rel in CI_CONFIG_PATHS[backend]:
        path = root / rel
        if path.is_file():
            return rel
        if path.is_dir() and any(
            p.is_file() for pattern in ("*.yml", "*.yaml") for p in path.glob(pattern)
        ):
            return rel
    return None


def no_ci_message(backend: HostBackend) -> str:
    looked = ", ".join(CI_CONFIG_PATHS[backend])
    return f"this repo has no CI config for its {backend} backend (looked for {looked})"
