"""Runner registry — the `fr.runners` entry-point group.

Adapters register their Runner factory under a short name; `fr apply
--to <name>` resolves through here. The VK adapter registers `vk`; a
future GitHub-Actions runner registers `gha`. Names feed the
`runner:<name>` label template, so they pass through the same bounded
machinery as plan/spec slugs.

`load_runner` is the one place a runner is BUILT outside its own bridge
(spec 2026-09-25-triage-batches §3.C): it loads the entry point and calls
the class's `from_env()`, because constructors differ (`VkRunner` takes an
MCP client) and only `from_env` promises to need nothing but the
environment. A runner without it is refused, never guessed at.
"""

from __future__ import annotations

from importlib.metadata import entry_points
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from fr_dispatch.protocols import Runner

GROUP = "fr.runners"


def available_runners() -> dict[str, object]:
    """Registered runner names → entry points (unloaded)."""
    return {ep.name: ep for ep in entry_points(group=GROUP)}


def runner_names() -> list[str]:
    return sorted(available_runners())


class RunnerLoadError(Exception):
    """A runner name that cannot be turned into a runner here."""


def load_runner(name: str) -> Runner:
    """Build the runner registered as *name* through its `from_env()` classmethod.

    Refuses a name no installed package registers, and a runner class without
    `from_env` ("cannot be constructed outside its own bridge" — `vk` and
    `cncd` today).
    """
    runners = available_runners()
    if name not in runners:
        known = ", ".join(sorted(runners)) or "none"
        raise RunnerLoadError(
            f"runner `{name}` is not installed: no package registers it under the "
            f"{GROUP} entry points (installed: {known})"
        )
    cls = runners[name].load()  # type: ignore[attr-defined]
    factory = getattr(cls, "from_env", None)
    if not callable(factory):
        raise RunnerLoadError(f"runner `{name}` cannot be constructed outside its own bridge")
    return cast("Runner", factory())
