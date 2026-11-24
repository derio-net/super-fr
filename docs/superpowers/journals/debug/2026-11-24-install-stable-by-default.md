<!-- fr:journal-schema=4 -->
# Journal: 2026-11-24-install-stable-by-default

<!-- fr:journal kind=repro scope=debug id=65526d9e4f90 created=2026-11-24T13:16:06+00:00 -->
### 65526d9e4f90 · repro · install.sh from a main clone and the cloud setup script install the RC, not the latest stable

Operator ran `scripts/install.sh` in the base clone on `main` (HEAD `0bf258293 release: v9.0.0-rc.1`). `fr --identity` then reported `9.0.0rc1` from the clone, and `installed_plugins.json` listed super-fr `9.0.0-rc.1`. For the same tags, bootstrap.sh resolves the default to v8.2.0 and `--version RC` to v9.0.0-rc.1. `packages/fr/src/fr/data/cloud-setup.sh` runs `checkout -B main origin/main` and then install.sh, so cloud sessions get the RC too.

<!-- fr:journal kind=root-cause scope=debug id=5e87812ad7fc created=2026-11-24T13:16:07+00:00 -->
### 5e87812ad7fc · root-cause · Only bootstrap.sh resolves a channel; install.sh and cloud-setup.sh follow main, which the release bot makes an RC

Spec 2026-10-14-exit-gates R22 gave bootstrap.sh the channels (default = newest installable vX.Y.Z). R23 kept install.sh installing "the checkout it runs from" (main in sync with origin/main, or a detached v* tag). release.py commits `release: vX.Y.Z-rc.N` straight onto main while a gate is pending, so main HEAD is the RC. Any installer that follows main follows RCs: install.sh run in a clone on main, and cloud-setup.sh, which hard-codes main. bootstrap.sh also falls back to origin/main when no stable tag is installable.
