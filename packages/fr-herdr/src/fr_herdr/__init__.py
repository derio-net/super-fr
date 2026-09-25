"""herdr adapter — an `fr_dispatch.protocols.Runner` for run-unit work.

`fr triage batch dispatch` launches a batch as one `/fr-goal` in a herdr
pane (spec 2026-09-25-triage-batches §3.C). This is the skeleton: the
package registers under `fr.runners` as `herdr`, and its runner refuses
every item until the run-unit behaviour lands.
"""

from fr_herdr.runner import HerdrRunner

__all__ = ["HerdrRunner"]
