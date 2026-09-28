"""Does this repo have CI? — the one answer `init` and the `ci` status share.

A matrix row's `ci` status means "a CI run is the evidence", and `fr acceptance
init` scaffolds a pipeline for the forge's CI system. Both used to key off the
forge backend alone (gh#775), so a GitLab project with no CI got a
`.gitlab-ci.yml` it never asked for and rows went to `ci` with nothing to run
them. The fact they were missing is whether the repo already carries a CI
config for its backend; this module is the only place that looks.

gh#774 adds a declared `ci:` service (`type: none` switches CI off):
`ci_active`/`ci_reason` resolve it, with `ci_config` as the undeclared probe.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from fr._hosts import HostBackend

# Where each backend's CI system reads its pipeline definitions. Gitea Actions
# falls back to `.github/workflows/` when `.gitea/workflows/` is absent.
CI_CONFIG_PATHS: dict[HostBackend, tuple[str, ...]] = {
    "github": (".github/workflows",),
    "gitea": (".gitea/workflows", ".github/workflows"),
    "gitlab": (".gitlab-ci.yml",),
}

# The file `fr acceptance init` scaffolds, per ci service type (#774): the
# pipeline follows the declared `ci` service, not the forge.
SCAFFOLD_PATHS: dict[str, str] = {
    "github-actions": ".github/workflows/acceptance-report.yml",
    "gitea-actions": ".gitea/workflows/acceptance-report.yml",
    "gitlab-ci": ".gitlab-ci.yml",
}

# The platform whose issue tracker a ci type's "Acceptance debt" step files
# into (github-actions↔github, ...): the step calls that platform's CLI with
# the pipeline's own credentials, so it is only kept for that tracker.
DEBT_PLATFORM: dict[str, str] = {
    "github-actions": "github",
    "gitlab-ci": "gitlab",
    "gitea-actions": "gitea",
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


def ci_none_reason(root: Path, services: Any) -> str | None:
    """Why the resolved `ci` is none, when that is more specific than "no CI
    config found": a declaration, or fr's own scaffold being the only CI file
    (a v1 file's legacy detection discounts it). None otherwise."""
    ci = services.ci
    if ci.type != "none":
        return None
    if ci.source == "declared":
        return "this repo declares `ci: {type: none}` in .devcontainer/fr-profiles.yaml"
    if ci.source == "legacy":
        from fr.services.detect import detect_ci

        if detect_ci(root, services.forge.type) == "fr-only":
            return (
                "the only CI file found is fr's own acceptance scaffold, which does not count "
                "as CI; declare `ci:` in .devcontainer/fr-profiles.yaml (see `fr services`)"
            )
    return None


def ci_reason(root: Path) -> str | None:
    """Why this repo cannot hold a `ci` row, or None when it has CI.

    Asks the resolved `ci` service (#774), strictly: a malformed declaration is
    a refusal naming .devcontainer/fr-profiles.yaml, never a fall-through to
    the raw probe. A declared type wins outright (`none` refuses); undeclared,
    it is #787's probe of the forge's own CI config."""
    from fr.services.model import ServicesError
    from fr.services.resolve import resolve_services

    try:
        services = resolve_services(root)
    except ServicesError as exc:
        return str(exc)
    if services.ci.type != "none":
        return None
    return ci_none_reason(root, services) or no_ci_message(cast(HostBackend, services.forge.type))


def ci_active(root: Path) -> bool:
    return ci_reason(root) is None
