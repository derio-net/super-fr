# Journal: 2026-10-05-batch-fr-binary-path

<!-- fr:journal kind=repro scope=debug id=repro created=2026-10-05T20:37:56+00:00 -->
### repro · repro · zsh -c resolves a different fr than a shell-less spawn

With a marker dir first on PATH: a direct exec (env fr) runs the marker fr; /bin/zsh -c 'command -v fr' resolves ~/.local/bin/fr (5.5.0) because ~/.zshenv rebuilds path=(... $path); /bin/bash -c resolves the marker. Harness shell tools run zsh -c; plugins/hooks exec fr without zsh, so the two resolve different binaries and nothing reports it (super-fr#746).
