"""VibeKanban adapter — the first `fr_dispatch.protocols.Runner`.

MCP client, card/workspace dispatch, repo config, slot accounting,
dedup, PR-state reconciliation, and the bridge daemon
(`python -m fr_vk.bridge`). Everything VK-shaped lives here; the
framework side (`fr_dispatch`) sees only the Runner protocol.
"""

from fr_vk._mcp_client import VkMcpClient, VkMcpError
from fr_vk.runner import VkRunner

__all__ = ["VkMcpClient", "VkMcpError", "VkRunner"]
