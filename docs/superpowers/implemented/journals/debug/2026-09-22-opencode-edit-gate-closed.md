# Journal: opencode-edit-gate-closed

<!-- fr:journal kind=repro scope=debug id=8fbe944a02d3 created=2026-09-22T07:56:54 -->
### 8fbe944a02d3 · repro · Captured OpenCode writer shape

Evidence captured before diagnosis: this session's only file-writing interface is the apply_patch tool, invoked with a patchText argument containing file paths inside unified patch headers; it does not supply filePath or path. That matches both #550 fail-open paths. No base-clone edit was attempted by this investigation.

<!-- fr:journal kind=root-cause scope=debug id=03b60bdfe968 created=2026-09-22T07:59:51 -->
### 03b60bdfe968 · root-cause · Fixed OpenCode's two fail-open branches

Confirmed cause: the OpenCode adapter returned before inspection unless input.tool was one of four names, so this environment's apply_patch tool was never gated; listed calls with relative or patch-body targets also returned. The adapter now derives targets from direct path fields and patch headers, resolves relatives against the OpenCode worktree, and fails closed when a patch target cannot be derived. Bash remains the declared exception. The Claude Code shell hook does not share this gap: Claude's PreToolUse registration only invokes it for fixed writer tools and carries tool_input.file_path.

<!-- fr:journal kind=finding scope=debug id=opencode-edit-gate-closed created=2026-09-22T08:02:50 state=fixed -->
### opencode-edit-gate-closed · finding [fixed] · Closed OpenCode edit-gate coverage

Implemented target-based gating, patch-header extraction, relative-path resolution, and unresolvable-target denial. Added regression coverage for arbitrary future writers and all observed call shapes. Updated the harness parity scope note and live-verified fresh sessions: absolute edit blocked; GPT-family apply_patch patchText blocked; relative edit blocked; valid worktree edit allowed. The temporary successful worktree edit was restored before recording this entry.

<!-- fr:journal kind=review scope=debug id=d5f2184dda6b created=2026-09-22T08:03:03 -->
### d5f2184dda6b · review · Implementation self-review

Reviewed the target classification boundary and preserve only Bash plus known read-only OpenCode tools as explicit exceptions. Tests pin that arbitrary non-excluded writers cannot bypass the gate. No findings.

<!-- fr:journal kind=review scope=debug id=8b27912b756e created=2026-09-22T13:58:23 -->
### 8b27912b756e · review · Adversarial review corrections

Restored the verified read-only built-in exclusions (bash, glob, grep, list, read); unknown path-carrying tools remain fail-closed. Replaced regex patch parsing with OpenCode's LF-split and prefix grammar, deny headerless patches in every fr-enabled context, recursively collect known path-bearing arguments and arbitrary absolute values, resolve from ctx.directory, normalize before marker checks, and realpath existing targets. Regression coverage pins each reviewed bypass.

<!-- fr:journal kind=finding scope=debug id=opencode-edit-gate-adversarial-followup created=2026-09-22T13:59:17 state=fixed -->
### opencode-edit-gate-adversarial-followup · finding [fixed] · Closed adversarial parser and resolver bypasses

Fresh OpenCode 1.18.32 probes confirmed a worktree-launched no-space Add File targeting the base clone is blocked, base-clone read remains allowed, and base-clone apply_patch is blocked. The acceptance row remains ci with this evidence.
