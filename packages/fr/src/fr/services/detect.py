"""What "has CI" means offline (spec 2026-09-28-fr-profiles-services §3.C).

Before #787, `fr acceptance init` scaffolded a pipeline whether or not the
repo had CI, so a CI file's presence alone is weak evidence. This test
discounts the one case fr itself caused:

- GitHub / Gitea: the workflows directory's only YAML file is
  `acceptance-report.yml` — fr's own scaffold, not CI.
- GitLab: `.gitlab-ci.yml` whose only job is `acceptance-report`, with no
  `include:` (which could pull real jobs in) — fr's own scaffold, not CI.

Anything else `fr.acceptance.ci.ci_config` finds counts as CI. Whether a
pipeline actually RUNS is knowable only from the forge; this never calls the
network, because the migration that uses it runs at the CLI-entry gate, often
offline or in a pod.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, cast

import yaml

from fr._hosts import HostBackend
from fr.acceptance.ci import ci_config

CiPresence = Literal["real", "fr-only", "absent"]

FR_WORKFLOW_NAMES: frozenset[str] = frozenset({"acceptance-report.yml", "acceptance-report.yaml"})
FR_GITLAB_JOB = "acceptance-report"

GITLAB_NON_JOB_KEYS: frozenset[str] = frozenset(
    {
        "stages",
        "variables",
        "workflow",
        "default",
        "image",
        "services",
        "before_script",
        "after_script",
        "cache",
    }
)
"""`.gitlab-ci.yml` top-level keywords that are not jobs. `include` is
deliberately absent: it is handled on its own, as evidence of real CI."""


def _gitlab_presence(path: Path) -> CiPresence:
    try:
        data = yaml.safe_load(path.read_text())
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return "real"  # cannot be shown to be fr's own
    if not isinstance(data, dict) or "include" in data:
        return "real"
    jobs = {
        key
        for key in data
        if isinstance(key, str) and key not in GITLAB_NON_JOB_KEYS and not key.startswith(".")
    }
    return "fr-only" if jobs == {FR_GITLAB_JOB} else "real"


def _workflows_presence(path: Path) -> CiPresence:
    names = {p.name for pattern in ("*.yml", "*.yaml") for p in path.glob(pattern) if p.is_file()}
    return "fr-only" if names and names <= FR_WORKFLOW_NAMES else "real"


def detect_ci(root: Path, forge_type: str) -> CiPresence:
    """`real` when `root` carries CI for `forge_type`'s pipeline system,
    `fr-only` when the only CI config is fr's own acceptance scaffold, and
    `absent` when there is none."""
    rel = ci_config(root, cast(HostBackend, forge_type))
    if rel is None:
        return "absent"
    path = root / rel
    if path.is_file():
        return _gitlab_presence(path)
    return _workflows_presence(path)
