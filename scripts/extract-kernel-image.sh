#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# Extract a compiled vmlinuz from a genuine matching Pulse P1 .deb without installing.
set -Eeuo pipefail
[[ $# == 2 ]] || { echo 'Usage: extract-kernel-image.sh RELEASE_DIRECTORY /absolute/new/vmlinuz-path' >&2; exit 2; }
RELEASE="$(realpath -e -- "$1")"
DEST="$2"
[[ "$DEST" == /* && ! -e "$DEST" && ! -L "$DEST" ]] || { echo 'ERROR: destination must be new absolute path' >&2; exit 2; }
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
"$ROOT/scripts/verify-release.sh" "$RELEASE"
KR="$(sed -n 's/^KERNEL_RELEASE=//p' "$RELEASE/provenance.txt")"
[[ "$KR" =~ ^6\.12\.[0-9]+-pulse-p1\.0\.0$ ]] || { echo 'ERROR: invalid Pulse kernel identity' >&2; exit 3; }
shopt -s nullglob
PACKAGES=("$RELEASE"/*.deb)
SELECTED=''
for pkg in "${PACKAGES[@]}"; do
  if [[ "$(dpkg-deb --field "$pkg" Package)" == "linux-image-$KR" ]]; then
    [[ -z "$SELECTED" ]] || { echo 'ERROR: duplicate kernel image packages' >&2; exit 3; }
    SELECTED="$pkg"
  fi
done
[[ -n "$SELECTED" ]] || { echo 'ERROR: expected linux-image package missing' >&2; exit 3; }
TMP="$(mktemp -d "${TMPDIR:-/tmp}/pulse-p1-extract-XXXXXXXX")"
trap 'rm -rf -- "$TMP"' EXIT
dpkg-deb --extract "$SELECTED" "$TMP"
SRC="$TMP/boot/vmlinuz-$KR"
[[ -f "$SRC" && -s "$SRC" && ! -L "$SRC" ]] || { echo 'ERROR: image package has no genuine vmlinuz' >&2; exit 3; }
cp -- "$SRC" "$DEST"
sha256sum -- "$DEST"
echo 'Kernel extracted, NOT installed. QEMU boot validation is still required.'
