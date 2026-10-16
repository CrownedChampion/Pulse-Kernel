#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# Validates a real compiled Pulse kernel in disposable, firmware-independent QEMU.
# IMPORTANT: This proves only minimal early-userspace boot, NOT secure boot or production.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
usage() { echo "Usage: $0 /absolute/vmlinuz-pulse /absolute/new/serial-boot.log" >&2; exit 2; }
[[ $# == 2 ]] || usage
KERNEL="$(realpath -e -- "$1")"; LOG="$2"
[[ "$LOG" = /* && ! -e "$LOG" && ! -L "$LOG" ]] || usage
for cmd in qemu-system-x86_64 cpio gzip timeout file mktemp; do
  command -v "$cmd" >/dev/null || { echo "ERROR: missing boot-test dependency: $cmd" >&2; exit 3; }
done
[[ -f "$KERNEL" && -s "$KERNEL" && ! -L "$1" ]] || { echo 'ERROR: invalid kernel image' >&2; exit 3; }
BUSYBOX="${PULSE_STATIC_BUSYBOX:-/usr/bin/busybox}"
[[ -f "$BUSYBOX" && ! -L "$BUSYBOX" ]] || { echo 'ERROR: provide trusted static busybox path via PULSE_STATIC_BUSYBOX' >&2; exit 3; }
if ! file -Lb -- "$BUSYBOX" | grep -Eq 'statically linked|static-pie linked'; then
  echo 'ERROR: busybox must be a static binary (install busybox-static)' >&2; exit 3
fi
SECONDS_TIMEOUT="${PULSE_BOOT_TIMEOUT:-180}"
[[ "$SECONDS_TIMEOUT" =~ ^[1-9][0-9]*$ && "$SECONDS_TIMEOUT" -le 600 ]] || { echo 'ERROR: invalid timeout' >&2; exit 3; }
WORK="$(mktemp -d "${TMPDIR:-/tmp}/pulse-p1-qemu-XXXXXXXX")"
trap 'rm -rf -- "$WORK"' EXIT
mkdir -p "$WORK/root/bin" "$WORK/root/proc" "$WORK/root/sys" "$WORK/root/dev" "$WORK/root/tmp"
cp -- "$BUSYBOX" "$WORK/root/bin/busybox"
ln -s busybox "$WORK/root/bin/sh"
cat > "$WORK/root/init" <<'INIT'
#!/bin/sh
export PATH=/bin
/bin/busybox mount -t proc proc /proc 2>/dev/null || true
/bin/busybox mount -t sysfs sysfs /sys 2>/dev/null || true
/bin/busybox mount -t devtmpfs devtmpfs /dev 2>/dev/null || true
VERSION="$(/bin/busybox uname -r)"
SYSNAME="$(/bin/busybox uname -s)"
echo "PULSE_BOOT_OBSERVED release=$VERSION sysname=$SYSNAME"
case "$VERSION" in
  *-pulse-p1.0.0) echo "PULSE_BOOT_OK release=$VERSION" ;;
  *) echo 'PULSE_BOOT_FAILED incorrect-kernel-identity'; /bin/busybox poweroff -f; exit 1 ;;
esac
/bin/busybox sync
/bin/busybox poweroff -f
INIT
chmod 0755 "$WORK/root/init"
( cd "$WORK/root"; find . -print0 | cpio --null --quiet -o -H newc | gzip -n -9 > "$WORK/initramfs.cpio.gz" )
# TCG works without KVM. No host disks, shared folders, networking, or writable target OS.
# QEMU generally exits zero after guest poweroff. Serial proof is required regardless.
set +e
timeout --kill-after=5s "${SECONDS_TIMEOUT}s" \
  qemu-system-x86_64 -machine q35,accel=tcg -cpu max -smp 2 -m 1024 \
  -nodefaults -no-reboot -display none -serial stdio -monitor none \
  -kernel "$KERNEL" -initrd "$WORK/initramfs.cpio.gz" \
  -append 'console=ttyS0,115200 loglevel=4 rdinit=/init panic=-1' \
  >"$WORK/qemu.log" 2>&1
STATUS=$?
set -e
if [[ "$STATUS" -eq 124 || "$STATUS" -eq 137 ]]; then
  echo "ERROR: QEMU timed out after ${SECONDS_TIMEOUT}s" >&2
  tail -n 45 "$WORK/qemu.log" >&2
  exit 4
fi
if [[ "$STATUS" -ne 0 ]] || ! grep -Eq '^PULSE_BOOT_OK release=6\.12\.[0-9]+-pulse-p1\.0\.0\r?$' "$WORK/qemu.log"; then
  echo 'ERROR: kernel did not prove a successful Pulse P1 /init boot' >&2
  tail -n 55 "$WORK/qemu.log" >&2
  exit 4
fi
# Save only confirmed, completed test logs; never report success for a crash/timeout.
cp -- "$WORK/qemu.log" "$LOG"
printf 'PASS: compiled Pulse P1 Linux-derived kernel booted a disposable static-busybox initramfs in QEMU.\n'
printf 'LIMITATION: does NOT establish UEFI Secure Boot, dm-verity, hardware, feature, or security certification.\n'
