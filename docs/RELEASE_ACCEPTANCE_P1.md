# Pulse P1 — Production Acceptance Contract

The release identifier stays **P1** until the project owner authorizes a change.
The full Linux kernel is Linux-derived and subject to the kernel GPL obligations.

## A genuine kernel, not just packages

A Linux 6.12 derived `vmlinuz-*-pulse-p1.0.0` and matching headers must compile from a pinned, authenticated kernel source. Packaging a Python utility, a Linux header-built module or renaming a Debian kernel DOES NOT satisfy this gate. The checked-in source is not a vendored copy of upstream Linux. P1 cannot compile offline without an authenticated matching upstream source tarball.

`./scripts/build-pulse.sh --build` attempts real `bindeb-pkg`. It audits security configuration after `olddefconfig` and fails if dependencies silently disable mandatory hardening. `./scripts/extract-kernel-image.sh` refuses an unverified release and extracts the *compiled* kernel directly from its .deb. `./scripts/boot-smoke.sh` uses a static busybox initramfs and QEMU TCG to boot a real kernel, verify kernelrelease includes `-pulse-p1.0.0`, and record serial output. This proves a minimal virtualized Linux boot only.

## Signed boot and immutable operating system root

A release requires authenticating the boot kernel, initramfs, kernel command line and root dm-verity hash through a signed firmware-measured chain. Full UEFI Secure Boot key provisioning, a signed Unified Kernel Image with approved key enrollment, a squashfs + dm-verity authenticated root, and recovery mechanisms require device-specific integration and testing. A signed update manifest alone is NOT verified boot. A read-only root alone is NOT tamper-resistant under kernel/firmware compromise.

Kernel config's `MODULE_SIG_ALL=y` signs in-tree modules and `MODULE_SIG_FORCE=y` blocks untrusted kernel modules but requires vendor/third-party GPU modules to be cryptographically signed and trusted under the target machine's policy. The user may not be able to load out-of-tree NVIDIA drivers until the trust workflow is integrated and tested. `KEXEC=n` disallows bypass by replacing the running kernel via kexec, but not arbitrary firmware-level attacks.

## Additional mandatory gates

- Signed A/B update, controlled admin maintenance, deterministic rollback and data preservation with injected failures.
- Suspend, resume, graphics, audio, Wi-Fi, Bluetooth, storage, peripherals, and fault-injection on explicit supported hardware.
- LSM/AppArmor, seccomp, Landlock, privilege boundaries, and denial of cross-process and system data access, including Linux app containers and Pace.
- Secure Rift LUKS2 encryption, rollback-resistant keys/grants where available, safe key recovery, file-broker verification, malware adversarial testing. Mounted plaintext cannot be guaranteed inaccessible to privileged compromise.
- Measured boot/readiness, input latency p95/p99, memory pressure, gameplay frame times, thermals on matching baseline and real hardware.
- Independent qualified security assessment and written scope/findings by external assessors. Pulse's own tests, penetration scripts, and signatures **are not security certification**.
- GPL-compatible source releases, notices, driver firmware license manifests and security response plan.
- The **actual current** proprietary Velora release is required to test integration. Never infer compatibility from an old Velora build, and retain a bootable working fallback. Never change Velora without owner approval.

`python3 scripts/p1-release-readiness.py` intentionally returns `BLOCKED` and cannot issue certification. Its checklist is a gate, not a certification service. This P1 source tree is not yet a production-ready, security-certified kernel.

## Offline constrained environment

The local development environment has Debian 13 headers but no full authenticated Linux source tarball, QEMU, cryptsetup, dm-verity tools, or internet DNS. That environment **cannot** demonstrate a compiled full bootable kernel, dm-verity authenticated boot or Secure Rift encrypted real-volume behavior. Build and validate these on a connected dedicated Debian 13 builder, then on physical Velora-supported devices.
