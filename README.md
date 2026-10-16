# Pulse P1 — Kernel & Platform Source Release (integration **NOT CERTIFIED**)

## P1 production-engineering additions (P1 name unchanged)

- Real Linux 6.12 kernel build path updated with mandatory P1 configuration: module signing enforcement (including signing in-tree modules), hardened memory permissions, built-in dm-verity/dm-crypt/SquashFS and disabled kexec. Post-`olddefconfig` config gates fail closed. This kernel build has **NOT run successfully** in this offline workspace because it lacks full authenticated kernel source.
- Fixed `verify-release.sh` to accept the proper P1 kernel release (previous implementation accidentally required P0.1). Alternate kernel source paths are accepted only if their bytes exactly match the authenticated Debian installed source.
- New `scripts/extract-kernel-image.sh` extracts the compiled `vmlinuz` from the verified `linux-image-*.deb` without installing anything. `scripts/boot-smoke.sh` provides a real QEMU TCG boot smoke test with an isolated static-busybox initramfs. **No successful QEMU boot has occurred here**, because QEMU and a full Pulse kernel image are unavailable.
- `scripts/p1-release-readiness.py` emits a 12-gate, fail-closed production checklist. **It never issues a security certificate**, and P1 remains `BLOCKED` pending real signed boot, root verity, hardware, Secure Rift, recovery, benchmarks, and qualified third-party assessment.
- `.github/workflows/p1-ci.yml` performs CI source/tests/userspace checks; `p1-kernel-builder.yml` is an opt-in manual pipeline for a pre-provisioned trusted Debian 13 builder and QEMU boot evidence. Never run unreviewed pull-request code on this self-hosted builder.
- Current tested P1 userspace package: `dist/pulse-platform_1.0.0-3_amd64.deb`. P1 external release label is unchanged; Debian packaging revision increased for traceability.
- The existing Secure Rift root-only LUKS2 prototype is **not** a safe-to-deploy app vault until the authenticated file broker, recovery and adversarial testing are completed.

Read `docs/RELEASE_ACCEPTANCE_P1.md` for explicit production and third-party audit gates. Keep Velora proprietary source and current installation untouched.

**Architecture:** independently developed, **Linux-derived** Pulse open-source kernel project and platform components, separate from proprietary Velora OS. The release target/version label is **P1.0.0**. This is NOT currently a fully bootable, security-certified, production-ready kernel. **Do not install directly on Velora.**

## Builds completed in the preparation environment

- `pulse_probe.ko` Linux GPL diagnostic **kernel module compiled** against local Debian 13 `6.12.107+deb13-amd64` headers; not loadable on Velora's `6.12.74+deb13+1-amd64` without compiling against that target.
- `pulse-platform_1.0.0-3_amd64.deb` standalone Python/C userspace package produced and audited. No root modification on package installation; only binaries/docs placed on disk.
- Pulse Pace-only libc identity interposer rebuilt, with isolation regression tests. Standard Linux apps still get Linux kernel identity.
- Ed25519-signed release manifest creation/verification, SHA-256 integrity, offline copy + re-verify staging, root SquashFS/dm-verity offline build recipe (recipe not executed: image tools unavailable here).
- System integrity audit, read-only hardware/network/audio/Wi-Fi diagnostics, cgroup profile runner, memory PSI monitoring, PulseFS logical catalog and optional sandbox runner.

## Seven subsystems and Secure Rift vault foundation

| Component | Runnable capability | Not production-complete |
|---|---|---|
| **Motion** | Explicit opt-in systemd-run cgroup v2 CPU/I/O workload profiles | Auto-foreground manager, sched_ext algorithms, proven latency improvement |
| **Guard** | Fail-closed Bubblewrap offline sandbox; signed artifacts; verified release | Comprehensive Vela identity + permission broker, LSM confinement for all apps |
| **Memory** | PSI `avg10` interpretation, cache/swap diagnostics | Adaptive reclaim optimization and measured p99 latency |
| **PulseFS** | Logical storage catalog over unmodified host filesystem | Scoped portal grants, Vela SDK, Files UX integration |
| **Frame** | DRM/Vulkan gaming stack inspection + Motion gaming profile | New graphics drivers, compositor, complete Proton/Gamescope Game Mode tests |
| **Link** | Wi-Fi driver/rfkill/NM, Bluetooth, ALSA/PipeWire layered diagnostics | Proven device fixes, all-hardware certification |
| **Wake** | Boot inventory + P1 system integrity audit, signed release staging | Tested signed boot chain, A/B updater/rollback and faster startup |
| **Secure Rift** | Root-only guarded LUKS2/Argon2id encrypted volume create/unlock/lock lifecycle, fail-closed checks, secure metadata checks | Authenticated per-app broker, real LUKS tests, vault GUI, device keys, recovery and independent security review |

## Secure system root design (not active yet)

- Only signed boot images that cryptographically authenticate the kernel, initramfs, command line and dm-verity root hash; Secure Boot/TPM policy per target device.
- Immutable SquashFS root checked by dm-verity; signed updates to *inactive* slots. Writable user/app data separated, MAC/seccomp namespaces block unauthorized access.
- Normal users/apps cannot alter protected system objects under this fully deployed policy; an authorized recovery/update mechanism is still necessary. No guarantee against all zero-days, firmware compromise, admin abuse or physical attack.
- Never turn this on in Velora without owner-provided **latest** Velora build and explicit deployment approval. Keep signed last-known-good boot entry, data backups and offline recovery.

Detailed engineering requirements: `security/PULSE-P1-ROOT-SECURITY.md`.

## Run tests and inspect this host

```bash
./tests/run-all.sh
./scripts/pulse status all
./scripts/pulse status security
./scripts/pulse wifi-diagnose
./scripts/pulse motion-run gaming -- /usr/bin/true
./scripts/pulse guard-run -- /usr/bin/true   # requires bubblewrap; fails closed otherwise
./scripts/build-platform-deb.sh
```

### Secure Rift — encrypted vault integration foundation

```bash
./scripts/pulse rift check
# Run only on a dedicated TEST MACHINE equipped with cryptsetup & ext4 tools:
sudo ./scripts/pulse rift create private --owner alice --size-gib 2 --confirm-creation
sudo ./scripts/pulse rift unlock private
sudo ./scripts/pulse rift lock private
```

Rift encrypted contents are intentionally **root-only after unlocking**; ordinary apps cannot browse or use the vault until a separately audited Vela/Pulse Guard broker is implemented. No secret data should be entrusted to the present preview; encrypted volumes were NOT exercised in this environment. LUKS2/dm-crypt is widely deployed, but this specific integration is not validated. Documentation: `security/SECURE-RIFT-SECURITY.md`.

### Create a signed offline update (operator supplies protected signing key)

```bash
# CAUTION: Demonstration only. It does not install a kernel.
# Offline bundle directory must already contain correct root/kernel/initramfs binaries.
./security/create-signed-bundle.sh /offline/bundle 1.0.0 /secure/key.pem root.squashfs root.verity root-hash.txt vmlinuz-pulse initramfs-pulse
./scripts/pulse verify-bundle /offline/bundle --trusted-key /independent/trust/public.pem
./scripts/pulse stage-bundle /offline/bundle /offline/new-staging-name --trusted-key /independent/trust/public.pem
```

The externally pinned key cannot be obtained from the update bundle itself. Never distribute the private key.

## Full Linux-derived kernel build (build system only; requires 6.12 source from authenticated Debian repo)

```bash
sudo apt update
sudo apt install linux-source-6.12 build-essential fakeroot bc bison flex \
 libssl-dev libelf-dev libncurses-dev dwarves rsync cpio xz-utils debhelper python3
./scripts/build-pulse.sh --preflight
./scripts/build-pulse.sh --build
```

Outputs (when dependencies and compilation succeed) distinct Pulse `-pulse-p1.0.0` versioned Linux kernel image/headers DEBs; ABI compatible with Linux applications. **No compiled full Pulse kernel binary is included in this release** because complete Linux source was unavailable in the execution environment. A source build on another machine is not a replacement for hardware-specific testing.

## Current limitations

**No QEMU/kernel boot tests**, no stable custom scheduler patch, no Velora current-source access, no actual Pace executable testing, no secure firmware trust enrollment, no protected live root or production A/B deployment, no verified vault encryption/restore test and no Secure Rift app grant broker. The included kernel module is diagnostic, not an immutable-root implementation. Never mistake the number P1 for completed security certification. The release is a development source milestone labeled P1 per product versioning choice.

Licenses/provenance: `LICENSES.md` and individual source file headers; GPL-2.0-only governs Linux-derived kernel code, original userspace MIT. Keep public kernel and proprietary Velora separate.

### Extra Secure Rift VM test (never on the Velora host)

`tests/p1-rift-vm-smoke.sh` exercises an isolated dummy LUKS2 volume on a **disposable test VM only**, requiring root, `PULSE_DISPOSABLE_VM=YES`, and an explicit marker `/etc/pulse-ci-disposable-vm` containing `PULSE P1 DISPOSABLE TEST VM`. It requires cryptsetup and mount capabilities and was **not run here**. This is storage-lifecycle smoke coverage, not authenticated-per-app broker or penetration-testing evidence.
