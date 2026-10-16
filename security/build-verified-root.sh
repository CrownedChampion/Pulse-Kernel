#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Offline image builder: does not format disks or install/activate a root.
set -Eeuo pipefail
usage(){ echo 'Usage: build-verified-root.sh /absolute/offline/root-tree /absolute/new/output-directory' >&2; exit 2; }
[[ $# == 2 ]] || usage
SRC="$(realpath -e -- "$1")"; OUT="$2"
[[ "$OUT" == /* && "$SRC" == /* ]] || usage
[[ -d "$SRC" && "$SRC" != / && "$SRC" != /proc* && "$SRC" != /sys* && "$SRC" != /dev* ]] || { echo 'unsafe input root' >&2; exit 3; }
[[ ! -e "$OUT" && ! -L "$OUT" ]] || { echo 'output exists' >&2; exit 3; }
for tool in mksquashfs veritysetup sha256sum realpath; do command -v "$tool" >/dev/null || { echo "missing $tool (no image created)" >&2; exit 3; }; done
# Refuse live mount trees; only copies of OS roots accepted.
if [[ "$SRC" == /mnt/* || "$SRC" == /tmp/* || "$SRC" == /home/* || "$SRC" == /srv/* ]]; then :; else
 echo 'input must be an intentionally prepared offline tree under /mnt, /tmp, /home, or /srv' >&2; exit 3
fi
mkdir -m 0700 -- "$OUT"
trap 'echo "VERIFY RESULT BEFORE USE: $OUT" >&2' EXIT
mksquashfs "$SRC" "$OUT/root.squashfs" -noappend -comp zstd -processors 2 -no-progress
veritysetup format --hash sha256 "$OUT/root.squashfs" "$OUT/root.verity" > "$OUT/verity-format.txt"
ROOT_HASH="$(sed -nE 's/^Root hash:[[:space:]]*([a-fA-F0-9]+).*$/\1/p' "$OUT/verity-format.txt" | head -1)"
if [[ ! "$ROOT_HASH" =~ ^[a-fA-F0-9]{64}$ ]]; then echo 'root hash missing/unparseable: DO NOT USE IMAGE' >&2; exit 4; fi
printf '%s\n' "${ROOT_HASH,,}" > "$OUT/root-hash.txt"
( cd "$OUT"; sha256sum root.squashfs root.verity root-hash.txt > SHA256SUMS )
chmod 0444 "$OUT"/*
echo "Created read-only SquashFS + dm-verity hash tree; root hash: $ROOT_HASH"
echo 'Not installed. An independently verified initramfs/UKI and trusted boot entry MUST authenticate this root hash before mounting.'
