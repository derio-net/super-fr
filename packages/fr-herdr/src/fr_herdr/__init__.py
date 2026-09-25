"""herdr adapter — an `fr_dispatch.protocols.Runner` for run-unit work.

`fr triage batch dispatch` launches a batch as one `/fr-goal` in a herdr
pane (spec 2026-09-25-triage-batches §3.C). The package registers under
`fr.runners` as `herdr`; `fr_dispatch.registry.load_runner("herdr")` builds the
runner through `HerdrRunner.from_env()`.
"""

from fr_herdr.runner import HerdrRunner

__all__ = ["HerdrRunner"]
