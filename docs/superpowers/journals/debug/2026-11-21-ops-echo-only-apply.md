<!-- fr:journal-schema=4 -->
# Journal: 2026-11-21-ops-echo-only-apply

<!-- fr:journal kind=repro scope=debug id=repro-1 created=2026-11-21T16:23:58+00:00 -->
### repro-1 · repro · mutating op with echo-only apply passes self-review; apply_ops records it applied

frank#1007 (run 2026-11-16-feat-gpu-speech-service-1006): ops premerge-gpu-switcher-image and premerge-speech-image are mutating: true with apply: echo '…docker buildx build --push…'. fr plan self-review passed both. fr ops apply would run the echo (exit 0) and treat the op as applied; deliver's last lines told the operator 'fr pickup --run' rather than 'fr ops gate --run'.
