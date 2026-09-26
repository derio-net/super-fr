"""Mechanical writer for devcontainer profiles (driven by the fr-init skill).

Writes three things per profile:
  - .devcontainer/<profile>/devcontainer.json  (committed)
  - .devcontainer/fr-profiles.yaml entry       (committed)
  - ~/.config/fr/secrets/<repo>/<profile>.env  (host-only placeholders;
    existing operator values are NEVER overwritten — only missing keys
    are appended as commented placeholders)
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Literal

import yaml

from fr._hosts import HostBackend
from fr.isolation.types import IsolationError, harden_secret_file, secrets_env_file
from fr.plan_validator_wrapper import (
    ValidatorWrapperError,
    ensure_validator_wrapper,
    plans_dir_exists,
)

# Pinned to an LTS tag, NOT the floating `:ubuntu`. The floating tag now
# resolves to Ubuntu "resolute", where the docker-in-docker feature fails to
# install (`moby` packages absent), breaking any profile scaffolded with
# `--tool docker-in-docker`. Pinning also keeps isolation workspaces
# reproducible. See super-fr#300.
BASE_IMAGE = "mcr.microsoft.com/devcontainers/base:ubuntu-24.04"

# What uv calls a project's environment INSIDE the container. The worktree is
# bind-mounted, and uv defaults to `<project>/.venv` on both sides of that
# mount — one path, two operating systems. A venv's interpreter link is only
# valid where it was made, so host and container each found the other's
# "broken" and replaced it on every alternation, which fr's exec-bridge
# discipline makes the normal case.
#
# RELATIVE on purpose: uv resolves a relative value against each project's own
# root, so every project gets its own. An absolute path is ONE directory shared
# by every project in the container — tried during review of this fix, with two
# independent projects: nothing was destroyed, but project `a` could import a
# package only `b` declared, i.e. tests passing on an undeclared dependency.
# Hidden (pytest's default `norecursedirs` skips `.*`), and uv writes its own
# `.gitignore: *` inside, so it never shows up in git, ruff or a reap check.
# It stays on the bind mount, which is exactly as fast as `.venv` was before.
UV_CONTAINER_PROJECT_ENV = ".venv-container"


# Known tool → devcontainer feature mapping (gh#574, spec §3.A). A tool NOT in
# this table is REFUSED by `resolve_tools` — it used to be recorded in the
# profile's notes and silently left uninstalled; `--feature <ref>` is the
# escape hatch for anything the table does not know. Tools that share a feature
# ref (java, maven) merge their options into ONE feature entry.
@dataclass(frozen=True)
class ToolSpec:
    """One `--tool` name: its devcontainer feature, the options it always sets,
    and the option key a `<tool>@<version>` writes."""

    feature: str
    options: Mapping[str, object] = field(default_factory=lambda: MappingProxyType({}))
    version_option: str = "version"


JAVA_FEATURE = "ghcr.io/devcontainers/features/java:1"

KNOWN_TOOLS: dict[str, ToolSpec] = {
    "uv": ToolSpec("ghcr.io/jsburckhardt/devcontainer-features/uv:1"),
    "node": ToolSpec("ghcr.io/devcontainers/features/node:1"),
    "python": ToolSpec("ghcr.io/devcontainers/features/python:1"),
    "go": ToolSpec("ghcr.io/devcontainers/features/go:1"),
    "rust": ToolSpec("ghcr.io/devcontainers/features/rust:1"),
    "kubectl": ToolSpec("ghcr.io/devcontainers/features/kubectl-helm-minikube:1"),
    "docker-in-docker": ToolSpec("ghcr.io/devcontainers/features/docker-in-docker:2"),
    "terraform": ToolSpec("ghcr.io/devcontainers/features/terraform:1"),
    "java": ToolSpec(JAVA_FEATURE),
    # `installMaven` is a JSON boolean — the java feature's own manifest types it so.
    "maven": ToolSpec(
        JAVA_FEATURE,
        options=MappingProxyType({"installMaven": True}),
        version_option="mavenVersion",
    ),
}


def parse_tool(arg: str) -> tuple[str, str | None]:
    """`<tool>[@<version>]` → (name, version or None). An empty name, an empty
    version, whitespace in the version, or a second `@` is refused."""
    name, sep, version = arg.partition("@")
    if not name or (sep and not version) or "@" in version or any(c.isspace() for c in version):
        raise IsolationError(f"--tool {arg!r} is malformed — expected <tool> or <tool>@<version>.")
    return name, (version if sep else None)


def _untagged(ref: str) -> str:
    """A feature ref without its `:tag` / `@digest` (only in the last path
    segment, so a registry `host:port` survives)."""
    head, slash, last = ref.rpartition("/")
    last = last.partition("@")[0].partition(":")[0]
    return f"{head}{slash}{last}"


def _set_option(
    resolved: dict[str, dict[str, object]], ref: str, key: str, value: object, origin: str
) -> None:
    opts = resolved.setdefault(ref, {})
    if key in opts and opts[key] != value:
        raise IsolationError(
            f"conflicting values for {ref} option {key!r}: {opts[key]!r} and {value!r} "
            f"(from {origin}) — pass one."
        )
    opts[key] = value


def resolve_tools(tools: list[str], features: list[str]) -> dict[str, dict[str, object]]:
    """Resolve `--tool` / `--feature` args to devcontainer `features` (ref → options).

    Pure, and meant to run BEFORE anything is written: an unknown tool raises
    IsolationError naming the known set and pointing at `--feature`.
    """
    parsed = [(arg, *parse_tool(arg)) for arg in tools]
    unknown = [name for _, name, _ in parsed if name not in KNOWN_TOOLS]
    if unknown:
        hints = [f"did you mean {u.lower()!r}?" for u in unknown if u.lower() in KNOWN_TOOLS]
        hint = f" ({'; '.join(hints)})" if hints else ""
        raise IsolationError(
            f"unknown --tool {', '.join(repr(u) for u in unknown)}{hint} — known tools: "
            f"{', '.join(sorted(KNOWN_TOOLS))}. For anything else pass the devcontainer "
            "feature ref directly with --feature <ref>."
        )
    resolved: dict[str, dict[str, object]] = {}
    for arg, name, version in parsed:
        spec = KNOWN_TOOLS[name]
        resolved.setdefault(spec.feature, {})
        for key, value in spec.options.items():
            _set_option(resolved, spec.feature, key, value, arg)
        if version is not None:
            _set_option(resolved, spec.feature, spec.version_option, version, arg)
    for ref in features:
        if not ref or any(c.isspace() for c in ref):
            raise IsolationError(
                f"--feature {ref!r} is not a feature ref — it must be non-empty and "
                "contain no whitespace."
            )
        # A known tool's feature at ANOTHER tag (or untagged) would add a second
        # copy of the same feature; the identical ref merges as before.
        shadowed = sorted(
            name
            for name, spec in KNOWN_TOOLS.items()
            if ref != spec.feature and _untagged(ref) == _untagged(spec.feature)
        )
        if shadowed:
            raise IsolationError(
                f"--feature {ref!r} is a known tool's feature at another tag — use "
                f"{' or '.join(f'--tool {n}' for n in shadowed)} (with @<version> to pin it)."
            )
        resolved.setdefault(ref, {})
    return resolved


# A plausible Java major; anything outside is a miss, never a pin.
JAVA_MAJOR_RANGE = range(6, 41)


def _java_major(raw: str) -> str | None:
    """The Java major in a version string, or None (p4r-f1/f2).

    A `+javaN` suffix (graalvm) wins. Otherwise the first number that does NOT
    continue a word — so `openjdk64-11.0.2` is 11 and `semeru-openj9-17` is 17 —
    with `1.N` read as N. A major outside JAVA_MAJOR_RANGE is a miss."""
    suffix = re.search(r"\+java(\d+)", raw)
    if suffix:
        major = suffix.group(1)
    else:
        m = re.search(r"(?<![A-Za-z0-9])(\d+)(?:\.(\d+))?", raw)
        if not m:
            return None
        major = m.group(2) if m.group(1) == "1" and m.group(2) else m.group(1)
    return major if int(major) in JAVA_MAJOR_RANGE else None


def _java_from_java_version(text: str) -> str | None:
    return _java_major(text.strip().splitlines()[0]) if text.strip() else None


def _java_from_sdkmanrc(text: str) -> str | None:
    for line in text.splitlines():
        key, sep, value = line.strip().partition("=")
        if sep and key.strip() == "java":
            return _java_major(value)
    return None


def _java_from_tool_versions(text: str) -> str | None:
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "java":
            return _java_major(parts[1])
    return None


# pom.xml: maven-compiler-plugin `<configuration>` children first (build/plugins,
# then build/pluginManagement/plugins), then root `<properties>` keys, which
# only feed the plugin's defaults — Maven's own precedence (spec §3.A, p4r-f3).
# Profile-scoped properties are deliberately not read.
POM_JAVA_PROPERTIES = (
    "maven.compiler.release",
    "maven.compiler.target",
    "maven.compiler.source",
    "java.version",
)
POM_COMPILER_PLUGIN_KEYS = ("release", "target")


def _local(tag: object) -> str:
    """An element tag without its `{namespace}`."""
    return str(tag).rpartition("}")[2]


def _child(elem: ET.Element, name: str) -> ET.Element | None:
    return next((c for c in elem if _local(c.tag) == name), None)


def _text(elem: ET.Element | None) -> str:
    return (elem.text or "").strip() if elem is not None else ""


def _java_from_pom(path: Path) -> tuple[str, str] | None:
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return None
    props_elem = _child(root, "properties")
    props = {_local(c.tag): _text(c) for c in props_elem} if props_elem is not None else {}

    def resolve(value: str) -> str | None:
        # ONE level of `${property}` indirection; anything deeper is skipped.
        m = re.fullmatch(r"\$\{([^}]+)\}", value)
        if m:
            value = props.get(m.group(1), "")
        return None if not value or "${" in value else _java_major(value)

    candidates: list[tuple[str, str]] = []
    build = _child(root, "build")
    management = _child(build, "pluginManagement") if build is not None else None
    for parent in (build, management):
        plugins = _child(parent, "plugins") if parent is not None else None
        for plugin in plugins if plugins is not None else ():
            config = _child(plugin, "configuration")
            if _text(_child(plugin, "artifactId")) != "maven-compiler-plugin" or config is None:
                continue
            for key in POM_COMPILER_PLUGIN_KEYS:
                source = f"pom.xml maven-compiler-plugin {key}"
                candidates.append((_text(_child(config, key)), source))
    candidates += [(props.get(key, ""), f"pom.xml {key}") for key in POM_JAVA_PROPERTIES]
    for value, source in candidates:
        major = resolve(value)
        if major:
            return major, source
    return None


# Version files in precedence order; the root pom.xml is consulted after them.
JAVA_VERSION_FILES = (
    (".java-version", _java_from_java_version),
    (".sdkmanrc", _java_from_sdkmanrc),
    (".tool-versions", _java_from_tool_versions),
)


def detect_java_version(repo_root: Path) -> tuple[str, str] | None:
    """The project's Java major and where it came from, or None (gh#574).

    Deterministic sources only — version files, then the root pom.xml. Project
    notes (README, CI setup-java) need judgement and belong to the fr-init
    skill, which passes `--tool java@<major>` explicitly. Never raises.
    """
    for name, parse in JAVA_VERSION_FILES:
        try:
            text = (repo_root / name).read_text()
        except (OSError, UnicodeDecodeError):
            continue
        major = parse(text)
        if major:
            return major, name
    pom = repo_root / "pom.xml"
    return _java_from_pom(pom) if pom.is_file() else None


# Profile names `fr isolation` gives a meaning of its own: a legacy state with
# no `target` infers its mode from the recorded profile (types.py), so a real
# devcontainer profile by either name would be routed to the wrong target
# (spec §3.C, journal p3-f1-reserve-external-profile).
RESERVED_PROFILES: frozenset[str] = frozenset({"host", "external"})

GH_FEATURE = "ghcr.io/devcontainers/features/github-cli:1"

# No official devcontainer feature exists for glab or tea (confirmed against
# the containers.dev registry during the multi-backend design's research —
# only an unrelated "gitlab-ci-local" runner feature turned up). `None` here
# means "no feature — install via POST_CREATE instead" (see
# HOST_CLI_PINS below). See docs/superpowers/specs/
# 2026-07-09-multi-backend-git-host-adapters-design.md §9.
HOST_CLI_FEATURE: dict[HostBackend, str | None] = {
    "github": GH_FEATURE,
    "gitlab": None,
    "gitea": None,
}

# Versioned + checksummed installs, one asset per supported architecture
# (gh#576, spec 2026-09-23-scaffold-batch-574-576-569 §3.B). Pinned to a
# specific released version, NOT "latest", matching BASE_IMAGE's own
# reproducibility rationale. Only amd64 and arm64 are carried: any other
# architecture fails postCreate loudly, naming itself, before any download.
# Every sha256 was taken from the project's published checksums.txt for the
# pinned version (2026-09-23) — never typed. That they still match is not a
# comment's promise: scripts/check-pinned-clis.py re-downloads every asset and
# .github/workflows/pinned-clis.yml runs it weekly.
HostCliArch = Literal["amd64", "arm64"]


@dataclass(frozen=True)
class HostCliPin:
    """One pinned host CLI: per-arch (url, sha256) and how to install the asset."""

    name: str
    version: str
    assets: Mapping[HostCliArch, tuple[str, str]]
    kind: Literal["tarball", "binary"]
    # tarball only: the executable's path inside the archive (glab 1.107.0: bin/glab,
    # read from the real asset with `tar -tzf`, 2026-09-23).
    tarball_member: str = ""

    def __post_init__(self) -> None:
        if (self.kind == "tarball") != bool(self.tarball_member):
            raise ValueError(
                f"{self.name}: tarball_member is required for, and only for, a tarball"
            )


_GLAB_BASE = "https://gitlab.com/api/v4/projects/gitlab-org%2Fcli/packages/generic/glab/1.107.0"
_TEA_BASE = "https://gitea.com/gitea/tea/releases/download/v0.14.2"

HOST_CLI_PINS: dict[str, HostCliPin] = {
    "gitlab": HostCliPin(
        name="glab",
        version="1.107.0",
        assets=MappingProxyType(
            {
                "amd64": (
                    f"{_GLAB_BASE}/glab_1.107.0_linux_amd64.tar.gz",
                    "eb42f56eb1a789cf4f22aa5960ff0ef60cf1e7fc1295327501f9f59030d5ae2c",
                ),
                "arm64": (
                    f"{_GLAB_BASE}/glab_1.107.0_linux_arm64.tar.gz",
                    "8356e442ed42ff6973cbe267dd7371c65f9b810b01e7d70bb557cd284e7b35ba",
                ),
            }
        ),
        kind="tarball",
        tarball_member="bin/glab",
    ),
    "gitea": HostCliPin(
        name="tea",
        version="0.14.2",
        assets=MappingProxyType(
            {
                "amd64": (
                    f"{_TEA_BASE}/tea-0.14.2-linux-amd64",
                    "be4ab135752825ab223cfa87d30e7f328312a24120b70176b67c1bd4aba19cc3",
                ),
                "arm64": (
                    f"{_TEA_BASE}/tea-0.14.2-linux-arm64",
                    "f201f6ba4136f1129e99e6318af07900c0c16a92030648bd186ff27067b34568",
                ),
            }
        ),
        kind="binary",
    ),
}


def render_host_cli_post_create(pin: HostCliPin) -> str:
    """The POSIX-sh install snippet for `pin` (devcontainer runs it under dash).

    A subshell, so its `exit 1` ends only the snippet — and, being the last
    command of postCreateCommand, sets that command's status.
    """
    dl = f"/tmp/{pin.name}.dl"
    arms = " ".join(
        f"{arch}) url='{url}'; sha='{sha}';;" for arch, (url, sha) in pin.assets.items()
    )
    supported = " ".join(pin.assets)
    if pin.kind == "tarball":
        # A fresh dir of its own, and the exact path the release tarball carries:
        # nothing else sitting in a shared /tmp can be what gets installed (p5r-f2).
        xdir = f"/tmp/{pin.name}-x"
        install = (
            f"rm -rf {xdir} && mkdir -p {xdir} && tar -xzf {dl} -C {xdir} && "
            f"sudo install -m 755 {xdir}/{pin.tarball_member} /usr/local/bin/{pin.name}"
        )
    else:
        install = f"sudo install -m 755 {dl} /usr/local/bin/{pin.name}"
    return (
        "( arch=$(dpkg --print-architecture 2>/dev/null || uname -m); "
        'case "$arch" in x86_64) arch=amd64;; aarch64) arch=arm64;; esac; '
        f'case "$arch" in {arms} '
        f"*) echo \"{pin.name} {pin.version}: unsupported architecture '$arch' "
        f'(supported: {supported})" >&2; exit 1;; esac; '
        f'curl -fsSL "$url" -o {dl} && '
        f'echo "$sha  {dl}" | sha256sum -c - && '
        f"{install} )"
    )


# Baseline: vk itself, installed from the repo's main branch at create time.
POST_CREATE = (
    'git config --global --add safe.directory "$PWD" || true; '
    "pipx install uv 2>/dev/null || true; "
    "uv tool install 'git+https://github.com/derio-net/super-fr#subdirectory=packages/fr' || true"
)


def env_file_path(repo_root: Path, profile: str) -> Path:
    return secrets_env_file(repo_root.name, profile)


def scaffold_profile(
    repo_root: Path,
    profile: str,
    purpose: str,
    tools: list[str],
    secrets: list[str],
    default: bool = False,
    force: bool = False,
    commit: bool = True,
    backend: HostBackend = "github",
    host: str | None = None,
    features: list[str] | None = None,
) -> Path:
    """Write the profile and (by default) commit it. Returns the devcontainer.json path.

    The profile must be committed for `fr isolation up` to see it — the
    worktree is cut from the branch's committed tree (super-fr#299 part 2). So
    scaffold commits by default; `commit=False` writes the files only.

    `backend`/`host` are repo-level (not per-profile — a repo lives on one
    host regardless of which devcontainer profile is active), written to
    `.devcontainer/fr-profiles.yaml`'s top-level keys, which
    `fr._hosts.detect_backend` reads. `backend="github"` (the default) is
    NOT written explicitly, matching `detect_backend`'s own fallback — an
    unmodified `fr-profiles.yaml` behaves identically to before this
    feature existed.
    """
    if not (repo_root / ".git").exists():
        raise IsolationError(
            f"{repo_root} is not a git repo — fr init scaffold only runs inside one."
        )

    if profile in RESERVED_PROFILES:
        raise IsolationError(
            f"profile name {profile!r} is reserved — fr infers a workspace's mode from "
            "its recorded profile when the state predates `target` (host → host-worktree, "
            "external → external), so a devcontainer profile by that name would be "
            "misrouted. Pick another name."
        )
    # Before ANY write (gh#574): an unknown tool must leave no file behind.
    resolved = resolve_tools(tools, list(features or []))
    tool_names = {parse_tool(t)[0] for t in tools}

    profile_dir = repo_root / ".devcontainer" / profile
    config_path = profile_dir / "devcontainer.json"
    if config_path.exists() and not force:
        raise IsolationError(
            f"{config_path} already exists — re-run with --force to overwrite "
            "(the host secrets file is preserved either way)."
        )

    # Gated on the TOOLS, not the feature ref: a bare `--feature <java ref>` is
    # taken exactly as written (p4r-f4).
    java_opts = resolved.get(JAVA_FEATURE)
    if tool_names & {"java", "maven"} and java_opts is not None and "version" not in java_opts:
        _apply_detected_java_version(repo_root, java_opts)

    host_feature = HOST_CLI_FEATURE.get(backend)
    feature_map: dict[str, dict[str, object]] = {host_feature: {}} if host_feature else {}
    feature_map.update(resolved)

    post_create = POST_CREATE
    host_pin = HOST_CLI_PINS.get(backend)
    if host_pin is not None:
        post_create = f"{POST_CREATE}; {render_host_cli_post_create(host_pin)}"

    env_file = env_file_path(repo_root, profile)
    config = {
        "name": f"{repo_root.name} — {profile}",
        "image": BASE_IMAGE,
        "features": feature_map,
        "postCreateCommand": post_create,
        # Mount the workspace at its HOST path (not /workspaces/<name>):
        # linked-worktree gitdir back-pointers record host abspaths, so git
        # only works in-container when worktree + base .git share the host
        # layout. Pairs with the base-.git mount that `fr isolation up` adds.
        "workspaceMount": "source=${localWorkspaceFolder},target=${localWorkspaceFolder},type=bind",
        "workspaceFolder": "${localWorkspaceFolder}",
        "runArgs": [
            "--env-file",
            f"${{localEnv:HOME}}/.config/fr/secrets/{repo_root.name}/{profile}.env",
        ],
        "customizations": {"fr": {"profile": profile, "purpose": purpose}},
    }
    if "uv" in tool_names:
        # `containerEnv`, not `remoteEnv`: it is set on the container itself, so
        # EVERY process in it sees it — `devcontainer exec` (what `fr isolation
        # exec` runs), the postCreateCommand, and a raw `docker exec` alike.
        # `remoteEnv` reaches only what the devcontainer CLI launches. Absent
        # rather than empty for every other profile.
        config["containerEnv"] = {"UV_PROJECT_ENVIRONMENT": UV_CONTAINER_PROJECT_ENV}
    profile_dir.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n")

    _update_profiles_yaml(repo_root, profile, purpose, secrets, default, backend, host)
    _ensure_env_placeholders(env_file, repo_root.name, profile, secrets)
    include_validator_wrapper = False
    if plans_dir_exists(repo_root):
        try:
            ensure_validator_wrapper(repo_root)
        except ValidatorWrapperError as err:
            raise IsolationError(str(err)) from err
        include_validator_wrapper = True
    if commit:
        _commit_profile(repo_root, profile, include_validator_wrapper=include_validator_wrapper)
    return config_path


def _apply_detected_java_version(repo_root: Path, java_opts: dict[str, object]) -> None:
    """Pin the java feature to the project's detected major, reporting where it
    came from — or warn that the feature's default will be used (spec §3.A)."""
    detected = detect_java_version(repo_root)
    if detected is None:
        print(
            "java version not detected — the java feature's default (latest) will be "
            "used; pass --tool java@<major> to pin it",
            file=sys.stderr,
        )
        return
    major, source = detected
    java_opts["version"] = major
    print(f"java {major} (from {source})", file=sys.stderr)


def _commit_profile(
    repo_root: Path, profile: str, *, include_validator_wrapper: bool = False
) -> None:
    """Scoped commit of just the profile files on the current branch (HEAD).

    Stages only what scaffold wrote — `.devcontainer/<profile>/` and
    `.devcontainer/fr-profiles.yaml` — so the operator's other working-tree
    changes are never swept in. The host secrets env-file lives outside the
    repo and is never committed. No-ops cleanly when nothing is staged: a
    git-ignored `.devcontainer` warns; an unchanged re-scaffold is silent.
    """
    paths = [f".devcontainer/{profile}", ".devcontainer/fr-profiles.yaml"]
    if include_validator_wrapper:
        paths.append("scripts/validate-plans.sh")
    _git(repo_root, "add", "--", *paths)
    # `git diff --cached --quiet` → rc 0 means nothing staged (ignored/unchanged).
    if _git(repo_root, "diff", "--cached", "--quiet", "--", *paths).returncode == 0:
        if _git(repo_root, "check-ignore", "-q", f".devcontainer/{profile}").returncode == 0:
            print(
                f"warning: .devcontainer is git-ignored — profile {profile!r} written "
                "but not committed; `fr isolation up` won't see it.",
                file=sys.stderr,
            )
        return
    # Pathspec on `commit` records ONLY these paths — any other staged changes
    # the operator had stay staged, never swept into the scaffold commit.
    result = _git(
        repo_root,
        "commit",
        "-m",
        f"chore(fr): scaffold {profile} devcontainer profile",
        "--",
        *paths,
    )
    if result.returncode != 0:
        # Don't leave the profile half-staged on failure (e.g. no git identity).
        _git(repo_root, "reset", "-q", "--", *paths)
        raise IsolationError(f"git commit failed: {result.stderr.strip() or result.stdout.strip()}")


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo_root), *args], capture_output=True, text=True)


def _update_profiles_yaml(
    repo_root: Path,
    profile: str,
    purpose: str,
    secrets: list[str],
    default: bool,
    backend: HostBackend = "github",
    host: str | None = None,
) -> None:
    path = repo_root / ".devcontainer" / "fr-profiles.yaml"
    data = yaml.safe_load(path.read_text()) if path.is_file() else {}
    data = data or {}
    data.setdefault("profiles", {})
    entry: dict[str, object] = {"purpose": purpose, "secrets": secrets}
    data["profiles"][profile] = entry
    if default or "default" not in data:
        data["default"] = profile if default else data.get("default", profile)
    # Repo-level (not per-profile) keys `fr._hosts.detect_backend` reads.
    # "github" is NOT written explicitly — matches detect_backend's own
    # fallback, so a repo that scaffolds nothing special behaves
    # identically to before this feature existed.
    if backend != "github":
        data["backend"] = backend
    if host:
        data["host"] = host
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def _ensure_env_placeholders(env_file: Path, repo: str, profile: str, secrets: list[str]) -> None:
    env_file.parent.mkdir(parents=True, exist_ok=True)
    existing = env_file.read_text() if env_file.is_file() else ""
    lines = [] if existing else [f"# fr isolation secrets — {repo}/{profile}", ""]
    present = {
        ln.lstrip("# ").split("=", 1)[0].strip() for ln in existing.splitlines() if "=" in ln
    }
    for key in secrets:
        if key in present:  # set or placeholder already present — never touch
            continue
        lines.append(f"# {key}=")
    if lines or not existing:
        env_file.write_text(
            existing + ("\n" if existing and lines else "") + "\n".join(lines) + "\n"
        )
    harden_secret_file(env_file)  # 0600 file / 0700 dirs — never a world-readable store
