# Journal: 2026-10-05-batch-fr-binary-path

<!-- fr:journal kind=repro scope=debug id=repro created=2026-10-05T20:37:56+00:00 -->
### repro · repro · zsh -c resolves a different fr than a shell-less spawn

With a marker dir first on PATH: a direct exec (env fr) runs the marker fr; /bin/zsh -c 'command -v fr' resolves ~/.local/bin/fr (5.5.0) because ~/.zshenv rebuilds path=(... $path); /bin/bash -c resolves the marker. Harness shell tools run zsh -c; plugins/hooks exec fr without zsh, so the two resolve different binaries and nothing reports it (super-fr#746).

<!-- fr:journal kind=root-cause scope=debug id=rc-746 created=2026-10-05T20:38:43+00:00 -->
### rc-746 · root-cause · Every fr integration chooses its fr by PATH lookup in its own process

Hooks (command -v fr; fr ...) and fr-opencode-plugin (execFile("fr") in claim.ts/idle.ts) resolve fr from the harness process PATH; the shell tool resolves it after zsh re-reads ~/.zshenv, which rebuilds PATH. Nothing records or compares which fr ran, so skew is silent. Non-PATH env vars survive .zshenv, so an env-carried pin is the one channel both sides see. Note: version alone cannot detect the evidence case (branch fr and global fr share a version number until release); identity must include install location.
