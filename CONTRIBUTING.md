# Contributing to Pulse P1

Pulse is an independent Linux-derived, open-source kernel project; Velora proprietary code never enters this repository.

- Keep the public release identifier **P1** until the owner changes it.
- Preserve original Linux kernel and third-party copyright, license and exact source provenance. See `LICENSES.md`.
- Start from a pinned Debian 13 authenticated `linux-source-6.12`; keep kernel patch sets minimal, readable, upstream-compatible and reviewable.
- Run `./tests/run-all.sh` and `./scripts/build-platform-deb.sh` before proposing changes. A complete kernel build and VM boot require a separately provisioned builder.
- Do not weaken kernel security mitigations to boost benchmark scores; include baseline measurements and kernel/hardware versions with perf claims.
- Do not enable unsandboxed compatibility fallbacks or claim unverified system immutability, malware immunity, cryptographic certification, or full hardware support.
- GitHub-hosted CI runs source checks. The dedicated kernel builder is manual and restricted to trusted maintainers on `main`: never execute unreviewed pull-request code with self-hosted runner credentials or access to signing keys.
- Do not commit: private UEFI signing keys, TPM material, Secure Rift keys, personal/hardware identifiers, Velora proprietary assets, production passwords, binary kernel packages, or build caches.
