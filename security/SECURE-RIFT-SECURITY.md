# Secure Rift — P1 vault security and integration contract

**State:** encrypted-container lifecycle prototype implemented; **not yet a production vault app or security-certified storage system.** Requires `cryptsetup`, dm-crypt, `mkfs.ext4`, mount tooling and a full secure-boot chain before use with real secrets. P1 does not install or enable a vault automatically.

## Threat model and honest guarantees

- **Offline stolen disk:** LUKS2 encrypted volumes protect plaintext against an attacker who obtains the locked image but not the passphrase/recovery key. Use a **unique, high-entropy passphrase** (preferably 6+ randomly generated words or an equivalently strong random secret). Data confidentiality depends on key strength, cipher/KDF implementation, and uncompromised boot/runtime.
- **Compromised ordinary user app:** the prototype exposes no readable mount to ordinary user apps. A future broker must use *real kernel-enforced* app identities and process credentials plus explicit per-document grants, not same-UID checks or a decorative permission prompt. Prevent unauthorized access, IPC spoofing, malicious mounts, link traversal, file picker privilege escalation, and persistent grants without user consent.
- **Compromised kernel/root, compromised firmware or unlocked session:** no ordinary Linux vault can guarantee secrets remain inaccessible. Root/kernel may inspect cryptographic keys, process memory, screenshots, clipboard or data while opened. TPM alone does not protect against a running compromised OS.
- **Ciphertext tampering:** AES-XTS disk encryption **does not authenticate arbitrary data modifications**. Future authenticated dm-integrity and recovery validation are an engineering gate if active tamper detection is required; use checked authenticated backups meanwhile. Do not conflate OS dm-verity with user-vault data integrity.
- **Deletion/ransomware:** encryption is not a backup. Use an encrypted, offline, versioned backup, integrity checks and tested restore procedures. Opening a vault does not prevent a malicious authorized application from destroying files it can edit.
- **Locking:** lock attempts a normal `umount` then `cryptsetup close`. If files are busy, it *refuses* to force-unmount or pretend keys were erased. Plaintext may remain in process RAM, page cache, swaps, crash dumps, screenshots, exported temporary files or backups after access; document these surfaces and test secure session teardown.

## Cryptography and privileges

| Component | Current choice / mandatory rule |
|---|---|
| Encryption | LUKS2 using audited `cryptsetup` / Linux dm-crypt; kernel-native modern cryptography, no Pulse-designed cipher |
| Derivation | Argon2id with 256 MiB memory and ~5-second work target on creation; tune/test against supported hardware; `luksFormat` prompts from terminal |
| Storage | Dedicated root-owned regular image under `/var/lib/secure-rift/vaults`, mode 0600, preallocated to prevent sparse-image ENOSPC |
| Plaintext mount | `ext4`, `nosuid,nodev,noexec,noatime`, `/run/secure-rift/<name>` parent mode 0700 root, never mounted directly into untrusted user's Home |
| Process privilege | Root/service-only encrypted-volume lifecycle; no app receives cryptsetup privileges, `CAP_SYS_ADMIN`, raw block access or passphrase copies |
| Keys | Never stored as plaintext, logged, passed in environment, process args or source; encrypt keyslots and make independent LUKS-header backups to protected offline media |
| Protection of system | Separate signed boot/root integrity enforcement, AppArmor, locked-down administrative policy and signed inactive-slot updates are prerequisites for strong runtime assurance |

**Critical design note:** Rift's root-only mount is intentionally inaccessible to ordinary apps. Actual Velora/Vela document use requires a separate, audited and authenticated file-descriptor portal. Never 'fix' a denied permission by `chmod 777`, bind-mounting into Home, disabling the MAC policy, or globally turning off sandboxes.

## Commands for a dedicated, isolated test machine (NOT Velora production)

Run the unprivileged read-only check first:

```bash
pulse rift check
```

After installing `cryptsetup-bin`, `e2fsprogs`, `util-linux` on a supported test system and separately verifying access to a physically backed encrypted backup:

```bash
sudo pulse rift create private --owner alice --size-gib 2 --confirm-creation
sudo pulse rift unlock private
# The decrypted filesystem is available ONLY to the privileged service/root.
# App grants/GUI are NOT shipped: do not use this preview for real secrets.
sudo pulse rift lock private
```

Creation reserves all requested storage and cryptsetup prompts for a new passphrase (and again on unlock). Both operations **refuse** unprivileged execution. Avoid running via remote automation that cannot provide a secure TTY. Never specify a secret in a shell argument.

## Work still required before Secure Rift product release

1. `rift-brokerd` security service: dedicated restricted privilege domain, per-app verified code identity (signed Vela manifest / LSM label / enforced cgroup process identity), one-shot scoped document grants, revocation, per-operation audit and persistent-grant policy. Test process/UID spoofing, TOCTOU, symlinks, hardlinks, `openat2` restrictions and capability revocation.
2. Velora Files UI: locked-by-default logical category, explicit password or hardware key unlock, reauthentication for secrets, no broad index/thumbnail/copy-to-temp leaks, clipboard and screenshot controls within platform limits, high-contrast and accessible prompts.
3. Device-protected unlock options: evaluate FIDO2 security keys, optional TPM2 measured-policy and explicit user PIN, with independent offline recovery key; do not blindly auto-unseal after boot. Implement and test revocation/lost-key recovery.
4. Vault data integrity and availability: assess dm-integrity+LUKS2 authenticated encryption support, recovery/repair behavior, snapshot consistency, fsck/mount fault injection, power loss, out-of-space, interrupted locks, backup/restore, boot regression and corrupted-header recovery.
5. RAM/key hygiene: minimize unlocked duration; screen-lock/suspend/logout auto-lock service with correct busy-file policy; no plaintext swap or crash dumps; process memory policies and secure erase limits accurately documented.
6. Real-world assurance: full Linux build + real cryptsetup creation/open/write/close/reboot tests on isolated hardware; adversarial filesystem/credential audits; reproducible fixes, fuzzing and independent security review.

## Velora integration boundary

Use the latest owner-supplied Velora source/build only; currently reported kernel baseline `6.12.74+deb13+1-amd64` is **not** a tested integration artifact. Keep proprietary Velora services separate from GPL Linux-derived kernel code. Leave the known-good kernel bootable, never overwrite partition data or existing user files, and get explicit permission before touching the live OS.
