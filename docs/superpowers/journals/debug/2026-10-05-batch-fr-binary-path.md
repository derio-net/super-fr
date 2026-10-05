# Journal: 2026-10-05-batch-fr-binary-path

<!-- fr:journal kind=repro scope=debug id=repro created=2026-10-05T20:37:56+00:00 -->
### repro · repro · zsh -c resolves a different fr than a shell-less spawn

With a marker dir first on PATH: a direct exec (env fr) runs the marker fr; /bin/zsh -c 'command -v fr' resolves ~/.local/bin/fr (5.5.0) because ~/.zshenv rebuilds path=(... $path); /bin/bash -c resolves the marker. Harness shell tools run zsh -c; plugins/hooks exec fr without zsh, so the two resolve different binaries and nothing reports it (super-fr#746).

<!-- fr:journal kind=root-cause scope=debug id=rc-746 created=2026-10-05T20:38:43+00:00 -->
### rc-746 · root-cause · Every fr integration chooses its fr by PATH lookup in its own process

Hooks (command -v fr; fr ...) and fr-opencode-plugin (execFile("fr") in claim.ts/idle.ts) resolve fr from the harness process PATH; the shell tool resolves it after zsh re-reads ~/.zshenv, which rebuilds PATH. Nothing records or compares which fr ran, so skew is silent. Non-PATH env vars survive .zshenv, so an env-carried pin is the one channel both sides see. Note: version alone cannot detect the evidence case (branch fr and global fr share a version number until release); identity must include install location.

<!-- fr:journal kind=decision scope=debug id=mismatch-policy created=2026-10-05T20:59:56+00:00 -->
### mismatch-policy · decision · Operator: refuse a bare-PATH fr that disagrees with the session pin; warn for a venv fr

Asked because a blanket refusal would block AGENTS.md's 'uv run fr in a worktree' convention. Operator chose: integrations pin the fr they resolved (Claude Code SessionStart -> CLAUDE_ENV_FILE; OpenCode plugin -> process.env); fr refuses (exit 2, naming both binaries) when it runs from no project venv and differs from the pin; an fr run from a venv (uv run fr, a uv-run wrapper) warns one line and continues; FR_SKIP_IDENTITY=1 bypasses.

<!-- fr:journal kind=finding scope=debug id=fix-746 created=2026-10-05T21:19:23+00:00 state=fixed -->
### fix-746 · finding [fixed] · Integrations pin their fr; fr refuses a PATH-skewed one

fr/binary_identity.py (identity = version + package dir; judge/enforce at CLI entry before the migration gate), fr --identity, plugins/super-fr/hooks/fr-binary-pin.sh (SessionStart -> CLAUDE_ENV_FILE), fr-opencode-plugin src/pin.ts (shell.env). Tests red first: tests/unit/test_fr_binary_identity.py, tests/unit/test_hooks_binary_pin.py, packages/fr-opencode-plugin/test/pin.test.ts. Live 2026-10-05: FR_HARNESS_FR survives zsh -c .zshenv while command -v fr moves to ~/.local/bin; a same-version (5.5.0) fr from another package dir refuses exit 2; FR_SKIP_IDENTITY=1 passes; uv run fr warns and runs; hook-written pin naming the same fr passes. Full suite 8457 passed.
