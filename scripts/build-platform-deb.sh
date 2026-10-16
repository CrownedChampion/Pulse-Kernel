#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Package already-tested Pulse P1 userspace only. No kernel/boot changes.
set -Eeuo pipefail
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
for cmd in dpkg-deb python3 make cc openssl; do command -v "$cmd" >/dev/null || { echo "Missing $cmd" >&2; exit 2; }; done
[[ "$(uname -m)" == x86_64 ]] || { echo 'x86_64 build host required' >&2; exit 2; }
make -C "$R/identity"
"$R/tests/run-all.sh"
mkdir -p "$R/dist"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/DEBIAN" "$TMP/usr/lib/python3/dist-packages/pulse" \
 "$TMP/usr/lib/pulse/identity" "$TMP/usr/bin" "$TMP/usr/share/doc/pulse-platform" \
 "$TMP/usr/share/pulse/security" "$TMP/usr/share/pulse"
cp "$R/platform/pulse/"*.py "$TMP/usr/lib/python3/dist-packages/pulse/"
cp "$R/identity/libpulse_pace_identity.so" "$TMP/usr/lib/pulse/identity/"
cp "$R/identity/pulse-pace" "$TMP/usr/bin/pulse-pace"
cat > "$TMP/usr/bin/pulse" <<'RUN'
#!/usr/bin/env bash
exec /usr/bin/python3 -m pulse "$@"
RUN
chmod 755 "$TMP/usr/bin/pulse" "$TMP/usr/bin/pulse-pace"
cp "$R/README.md" "$R/SECURITY.md" "$R/LICENSES.md" "$R/docs/RELEASE_ACCEPTANCE_P1.md" "$R/security/PULSE-P1-ROOT-SECURITY.md" "$TMP/usr/share/doc/pulse-platform/"
cp "$R/security/"*.sh "$TMP/usr/share/pulse/security/"
cp "$R/security/SECURE-RIFT-SECURITY.md" "$TMP/usr/share/doc/pulse-platform/"
cat > "$TMP/usr/share/pulse/identity.json" <<'ID'
{"product":"Pulse","version":"1.0.0","lineage":"Linux-derived","default_legacy_identity":"Linux","pace_opt_in_identity":"Pulse","kernel_sysname_global_change":false,"trust_certified":false}
ID
cat > "$TMP/DEBIAN/control" <<'CONTROL'
Package: pulse-platform
Version: 1.0.0-3
Section: admin
Priority: optional
Architecture: amd64
Maintainer: Pulse Kernel Project <kernel@localhost.invalid>
Depends: python3 (>= 3.11), libc6 (>= 2.36), bash, openssl
Recommends: systemd
Suggests: bubblewrap, cryptsetup-bin, e2fsprogs, util-linux, squashfs-tools
Description: Pulse P1 Linux-derived platform security and hardware utilities
 Read-only system diagnostics, opt-in systemd resource profiles, offline
 Ed25519 update verification/staging, Secure Rift LUKS2 vault lifecycle,
 Pace-scoped identity and optional
 fail-closed offline sandbox. No full bootable kernel is shipped by this
 package. No automatic changes to boot, partitioning or host security policy.
CONTROL
chmod -R go-w "$TMP"
OUT="$R/dist/pulse-platform_1.0.0-3_amd64.deb"
[[ ! -e "$OUT" ]] || { echo "Refusing to overwrite $OUT" >&2; exit 4; }
dpkg-deb --root-owner-group --build "$TMP" "$OUT"
( cd "$R/dist"; sha256sum "$(basename "$OUT")" > "$(basename "$OUT").sha256" )
echo "Built Pulse P1 userspace .deb: $OUT"
