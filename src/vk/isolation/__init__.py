"""vk isolation — pluggable isolated workspaces for autonomous runs.

v1 target: git worktree + devcontainer, driven over an exec-bridge
(`vk isolation exec`). Agent-agnostic by design: the surface is plain
shell, so any agent or a human drives it identically. See
docs/superpowers/specs/2026-06-04-vk-isolation-suite-design.md.
"""
