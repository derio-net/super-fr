"""cncd adapter — the CNC control plane's `fr_dispatch.protocols.Runner`.

A thin HTTP client (stdlib only): `dispatch()` POSTs the plan folder to
a cncd server's `POST /v1/ingest` (cnc-fr spec 2026-07-02, §3.5). No fr
internals move here; the framework side (`fr_dispatch`) sees only the
Runner protocol, exactly as with the VK adapter.
"""

from fr_cncd.runner import CncdError, CncdRunner

__all__ = ["CncdError", "CncdRunner"]
