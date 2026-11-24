<!-- fr:journal-schema=4 -->
# Journal: 2026-11-24-install-stable-by-default

<!-- fr:journal kind=repro scope=debug id=65526d9e4f90 created=2026-11-24T13:16:06+00:00 -->
### 65526d9e4f90 · repro · install.sh from a main clone and the cloud setup script install the RC, not the latest stable

Operator ran `scripts/install.sh` in the base clone on `main` (HEAD `0bf258293 release: v9.0.0-rc.1`). `fr --identity` then reported `9.0.0rc1` from the clone, and `installed_plugins.json` listed super-fr `9.0.0-rc.1`. For the same tags, bootstrap.sh resolves the default to v8.2.0 and `--version RC` to v9.0.0-rc.1. `packages/fr/src/fr/data/cloud-setup.sh` runs `checkout -B main origin/main` and then install.sh, so cloud sessions get the RC too.
