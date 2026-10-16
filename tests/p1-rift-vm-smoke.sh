#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# DESTRUCTIVE IN TEST VM ONLY: disposable LUKS2/dm-crypt smoke on a newly created file.
# Never run in host/proprietary Velora; no real secrets or user vaults are opened.
set -Eeuo pipefail
[[ "$EUID" == 0 ]] || { echo 'Requires root inside an isolated disposable VM' >&2; exit 3; }
[[ "${PULSE_DISPOSABLE_VM:-}" == YES ]] || { echo 'Refusing: PULSE_DISPOSABLE_VM=YES required' >&2; exit 3; }
[[ -f /etc/pulse-ci-disposable-vm && ! -L /etc/pulse-ci-disposable-vm ]] || { echo 'Refusing: VM-only test marker missing' >&2; exit 3; }
[[ "$(cat /etc/pulse-ci-disposable-vm)" == 'PULSE P1 DISPOSABLE TEST VM' ]] || { echo 'Invalid VM marker' >&2; exit 3; }
for tool in cryptsetup mkfs.ext4 mount umount findmnt openssl fallocate; do command -v "$tool" >/dev/null || { echo "Missing tool: $tool" >&2; exit 3; }; done
ROOT="$(mktemp -d /tmp/pulse-rift-vm-XXXXXX)"
NAME="pulse-rift-smoke-$$"
IMAGE="$ROOT/volume.luks"
KEY="$ROOT/test-only.key"
MOUNT="$ROOT/mnt"
cleanup() {
  set +e
  if mountpoint -q "$MOUNT"; then umount "$MOUNT"; fi
  if cryptsetup status "$NAME" >/dev/null 2>&1; then cryptsetup close "$NAME"; fi
  rm -rf -- "$ROOT"
}
trap cleanup EXIT
chmod 0700 "$ROOT"
mkdir -m 0700 "$MOUNT"
# Dummy key is generated fresh and never logged. It is NOT a real user vault key.
umask 077
openssl rand -out "$KEY" 64
fallocate -l 256M "$IMAGE"
cryptsetup luksFormat --batch-mode --type luks2 --pbkdf argon2id --pbkdf-memory 131072 \
  --key-file "$KEY" "$IMAGE"
[[ "$(cryptsetup luksDump "$IMAGE" | sed -n 's/^Version:[[:space:]]*//p' | head -1)" == 2 ]] || exit 4
cryptsetup open --key-file "$KEY" "$IMAGE" "$NAME"
mkfs.ext4 -q -F "/dev/mapper/$NAME"
mount -t ext4 -o nodev,nosuid,noexec "/dev/mapper/$NAME" "$MOUNT"
printf 'PULSE P1 TEST DATA, NOT A REAL SECRET\n' > "$MOUNT/message.txt"
sync
umount "$MOUNT"
cryptsetup close "$NAME"
cryptsetup open --key-file "$KEY" "$IMAGE" "$NAME"
mount -t ext4 -o ro,nodev,nosuid,noexec "/dev/mapper/$NAME" "$MOUNT"
grep -Fxq 'PULSE P1 TEST DATA, NOT A REAL SECRET' "$MOUNT/message.txt"
umount "$MOUNT"
cryptsetup close "$NAME"
echo 'PASS: LUKS2 disposable-file encrypt/open/mount/write/close/reopen/readonly test. NOT a vault security certification.'
