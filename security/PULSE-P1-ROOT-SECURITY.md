# Pulse P1 System Integrity Contract

**This is an opt-in, deployment engineering contract — not an enabled security feature on Velora or any existing Linux installation.**

## Enforcement model

1. On a supported UEFI PC, secure UEFI firmware settings (vendor/owner enrolled keys, Secure Boot enabled). A trusted, signed Unified Kernel Image (UKI) or other measured and verified boot chain must include or authenticate the root partition's dm-verity root hash, the initramfs, and its command line. A user-writable unsigned boot command line defeats the chain.
2. The boot image mounts an **offline-built read-only SquashFS** root through Linux **dm-verity**. Validation must be fail-closed on hash mismatch, including before unlocking/decrypting user data. Mount with `ro,nodev` where appropriate; `nosuid` depends on system service requirements and must be tested. Integrity errors must not fall back to writable Linux root mounts.
3. Put durable user files, per-app state, and approved configuration overrides on physically or logically separated writable volumes. Apply kernel/user namespaces, cgroups, seccomp, a tested AppArmor or equivalent MAC policy, and portals to deny general apps the ability to write system-critical files. Prevent direct writes to block devices and boot/EFI partitions using narrow privileged update services and policy confinement. Encryption protects confidentiality; it does not replace integrity verification.
4. Update only by a trusted, signed offline bundle to a verified **inactive** A/B slot, after validating signature, payload digests, required hardware compatibility, storage fit, and anti-rollback release counters. A separately reviewed privileged installer must be the only actor allowed to write inactive system/boot slots, and must fsync/sync, verify hashes, and atomically commit a signed boot entry. Root hash is bound to signed boot metadata. Do not automatically promote failed boots; use a last-known-good fallback. Unauthenticated boot entries cannot be considered a secure fallback.
5. Disable ordinary user access to administrative maintenance tasks; no broad `sudo` exception for regular applications. Platform-admin maintenance is still required for updates and recovery; physical attackers, firmware/kernel zero-days, stolen signing keys, and malicious authorized admins can compromise even hardened systems.
6. Linux apps run through compatibility namespaces/container runtimes, with their expected Linux syscall/ELF and filesystem ABI intact. Pace's optional identity shim changes a user-visible `uname` report but **does not** grant privileges or alter the kernel trust boundary.

## Included runnable tools

- `security/build-verified-root.sh`: creates offline SquashFS + verity hash tree from a prepared root tree **only when `mksquashfs` and `veritysetup` are installed**; does not format partitions, sign boot images, or install a kernel.
- `security/create-signed-bundle.sh`: signs exact root/kernel/initramfs artifact checksums with a separately held Ed25519 private key; never creates a trust anchor implicitly.
- `pulse verify-bundle BUNDLE --trusted-key /trusted/key.pem`: verifies a detached signature against an externally pinned public key, plus SHA-256 and file lengths. Refuses missing signatures, invalid keys and symlinks.
- `pulse stage-bundle BUNDLE /offline/staging/name --trusted-key KEY`: verifies, copies and re-verifies to a *new* staging directory without installing the bundle, editing the host, changing boot entries or updating the running root.
- `pulse status security`: audits limited visible properties of the current OS; its result **must never be interpreted as verified boot certification**.

## Not yet delivered or validated

- A verified, signed Pulse P1 UKI/initramfs and full Pulse kernel compilation.
- Host-specific dm-verity mounting and permanent installer integration.
- Firmware Secure Boot enrollment, TPM measurements, signed vendor/NVIDIA/third-party kernel modules.
- A production A/B updater, read-only Velora root and automatic boot-health rollback.
- Sandboxing of all installed applications, security audit/penetration testing, hardware certification.

## No false promises

Read-only alone is not cryptographic integrity. The bundle verifier is not a bootloader. A successful package unit test is not a security audit. This source release **does not prove malware immunity or production deployment readiness**. Never run integration against an outdated Velora build; use the owner's actual current Velora source, kernel configuration, hardware manifest, and full backup before installing anything.
