#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
set -Eeuo pipefail
if [[ $# -ne 1 ]]; then echo 'Usage: verify-release.sh path/to/kernel-artifact-directory' >&2; exit 2; fi
OUT="$(realpath -- "$1")"
[[ -d "$OUT" ]] || { echo "Missing release path: $OUT" >&2; exit 2; }
[[ -f "$OUT/SHA256SUMS" && -f "$OUT/provenance.txt" && -f "$OUT/pulse-kernel.config" ]] || {
  echo 'ERROR: required provenance, configuration, or checksums missing.' >&2; exit 3;
}
( cd "$OUT" && sha256sum --check --status SHA256SUMS ) || {
  echo 'ERROR: release checksum verification failed.' >&2; exit 3;
}
KERNEL_RELEASE="$(sed -n 's/^KERNEL_RELEASE=//p' "$OUT/provenance.txt")"
if [[ ! "$KERNEL_RELEASE" =~ ^6\.12\.[0-9]+-pulse-p1\.0\.0$ ]]; then
  echo "ERROR: wrong Pulse kernel release: $KERNEL_RELEASE" >&2; exit 3
fi
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
python3 "$ROOT/scripts/config-audit.py" "$OUT/pulse-kernel.config" || exit 3
python3 "$ROOT/scripts/config-audit.py" "$OUT/pulse-kernel.config" --requirements "$ROOT/config/p1-security-policy.json" || exit 3
shopt -s nullglob
packages=("$OUT"/*.deb)
(( ${#packages[@]} > 0 )) || { echo 'ERROR: no .deb artifacts found.' >&2; exit 3; }
found_image=0
found_headers=0
for pkg in "${packages[@]}"; do
  name="$(dpkg-deb --field "$pkg" Package)"
  arch="$(dpkg-deb --field "$pkg" Architecture)"
  if [[ "$arch" != amd64 && "$arch" != all ]]; then echo "ERROR: unexpected architecture: $arch" >&2; exit 3; fi
  if [[ "$name" == "linux-image-$KERNEL_RELEASE" ]]; then
    dpkg-deb --contents "$pkg" | grep -F "/boot/vmlinuz-$KERNEL_RELEASE" >/dev/null || {
      echo 'ERROR: expected kernel boot image not present in Linux image package.' >&2; exit 3;
    }
    ((found_image+=1))
  fi
  if [[ "$name" == "linux-headers-$KERNEL_RELEASE" ]]; then ((found_headers+=1)); fi
  echo "PASS: $(basename "$pkg"): $name ($arch)"
done
(( found_image == 1 && found_headers == 1 )) || {
  echo 'ERROR: built kernel image and headers packages both required.' >&2; exit 3;
}
echo "PASS: $KERNEL_RELEASE image, headers, config and checksums verified."
echo 'NOT VERIFIED: actual boot, hardware, Secure Boot signatures, security regression, or Velora compatibility.'
