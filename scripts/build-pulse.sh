#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
set -Eeuo pipefail
IFS=$'\n\t'
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:---help}"
RELEASE=p1.0.0
SOURCE_PACKAGE=linux-source-6.12
ARCH=amd64
DIST="$ROOT/dist"

usage() {
  cat <<'USAGE'
Pulse Kernel P1.0.0 — independent Linux-derived foundation

  ./scripts/build-pulse.sh --preflight
  ./scripts/build-pulse.sh --build

Use on a Debian 13 x86-64 build system. Build requires a complete authenticated
Debian linux-source-6.12 package and a matching Debian kernel configuration.
No kernel installation occurs. Source archive and compiler metadata are logged.

Optional environment:
  PULSE_BASE_CONFIG=/boot/config-6.12....      Explicit current known-good kernel config
  PULSE_LINUX_SOURCE_TARBALL=/usr/src/...     Authenticated Debian linux-source archive
  PULSE_JOBS=2                                Compile jobs (default 2; RAM intensive)
  PULSE_WORK_ROOT=/path/to/temp               Build work root (default project/work)
USAGE
}

case "$MODE" in --preflight|--build|--help|-h) ;; *) usage; exit 2 ;; esac
if [[ "$MODE" == --help || "$MODE" == -h ]]; then usage; exit 0; fi
if [[ "$(id -u)" == "0" ]]; then echo 'ERROR: compile as an unprivileged user, not root.' >&2; exit 3; fi
if [[ "$(uname -m)" != x86_64 ]]; then echo 'ERROR: initial Pulse P1 target is x86_64 only.' >&2; exit 3; fi
if ! grep -q '^ID=debian$' /etc/os-release || ! grep -q '^VERSION_ID="\?13' /etc/os-release; then
  echo 'ERROR: use a dedicated Debian 13 builder for the validated build procedure.' >&2; exit 3
fi
for cmd in make gcc bc bison flex perl python3 dpkg-deb dpkg-query fakeroot xz sha256sum rsync cpio pahole dpkg-architecture; do
  if ! command -v "$cmd" >/dev/null 2>&1; then echo "ERROR: missing $cmd (see README dependencies)" >&2; exit 3; fi
done
if [[ "$(dpkg-architecture -qDEB_HOST_ARCH)" != "$ARCH" ]]; then echo 'ERROR: Debian host architecture must be amd64.' >&2; exit 3; fi

TARBALL="${PULSE_LINUX_SOURCE_TARBALL:-/usr/src/linux-source-6.12.tar.xz}"
if [[ ! -f "$TARBALL" ]]; then echo "ERROR: missing source archive: $TARBALL (install linux-source-6.12 via APT)" >&2; exit 4; fi
if ! dpkg-query -W -f='${Version}' "$SOURCE_PACKAGE" >/dev/null 2>&1; then
  echo 'ERROR: authenticated Debian linux-source-6.12 installation is required.' >&2; exit 4
fi
PKG_VERSION="$(dpkg-query -W -f='${Version}' "$SOURCE_PACKAGE")"
if ! dpkg --verify "$SOURCE_PACKAGE" >/dev/null; then
  echo 'ERROR: Debian source package files differ from installed package hashes.' >&2; exit 4
fi
# Never allow an arbitrary caller-supplied tarball to inherit APT's trust label.
# An explicit alternate location is only acceptable when its bytes exactly
# match the already APT-verified installed archive.
TRUSTED_SOURCE=/usr/src/linux-source-6.12.tar.xz
if [[ ! -f "$TRUSTED_SOURCE" ]]; then
  echo 'ERROR: authenticated installed Debian source archive is missing.' >&2; exit 4
fi
if ! cmp -s -- "$TARBALL" "$TRUSTED_SOURCE"; then
  echo 'ERROR: specified source differs from the authenticated installed Debian source archive.' >&2; exit 4
fi
CONFIG="${PULSE_BASE_CONFIG:-}"
if [[ -z "$CONFIG" ]]; then
  if [[ "$(uname -r)" == 6.12.* && -f "/boot/config-$(uname -r)" ]]; then
    CONFIG="/boot/config-$(uname -r)"
  else
    CONFIG="$(find /boot -maxdepth 1 -type f -name 'config-6.12*' -print | sort -V | tail -n 1 || true)"
  fi
  if [[ -z "$CONFIG" ]]; then
    CONFIG="$ROOT/config/debian-6.12.107-amd64-reference.config"
    echo 'NOTE: no /boot Debian kernel config found; using generic Debian reference config.'
    echo 'NOTE: this is NOT a Velora hardware-certified config.'
  fi
fi
if [[ -z "$CONFIG" || ! -f "$CONFIG" ]]; then
  echo 'ERROR: no Debian 6.12 kernel config. Provide PULSE_BASE_CONFIG=/absolute/path/config.' >&2; exit 4
fi
if ! grep -q '^CONFIG_X86_64=y' "$CONFIG"; then echo 'ERROR: kernel config is not for x86-64.' >&2; exit 4; fi

DISK_KIB=$(df -Pk "${PULSE_WORK_ROOT:-$ROOT}" | awk 'NR==2{print $4}')
if [[ "$DISK_KIB" -lt 15728640 ]]; then
  echo "ERROR: insufficient free build disk (need at least 15 GiB; recommend 25 GiB)." >&2; exit 4
fi
if [[ "$MODE" == --preflight ]]; then
  echo 'PASS: build prerequisites present (source and configuration).'
  echo "  Debian source package : $PKG_VERSION"
  echo "  Source archive        : $TARBALL"
  echo "  Source SHA-256        : $(sha256sum "$TARBALL" | awk '{print $1}')"
  echo "  Kernel config         : $CONFIG"
  echo "  Available disk        : $((DISK_KIB/1048576)) GiB"
  echo 'This preflight does not compile or certify Pulse.'
  exit 0
fi

WORK_BASE="${PULSE_WORK_ROOT:-$ROOT/work}"
mkdir -p "$WORK_BASE" "$DIST"
WORK="$(mktemp -d "$WORK_BASE/pulse-p1.0.0-XXXXXXXX")"
mkdir -p "$WORK/src" "$WORK/obj"
LOG="$WORK/build.log"
exec > >(tee -a "$LOG") 2>&1
trap 'echo "Build failed. See log under: ${WORK}/build.log" >&2' ERR

echo "Pulse P1.0.0 source build: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Workdir: $WORK"
echo 'Checking Debian source archive layout and extracting safely...'
if [[ $(tar -tf "$TARBALL" | sed -n "1p") != linux-source-6.12/ ]]; then
  echo 'ERROR: Debian source archive root is unexpected (expected linux-source-6.12/).' >&2; exit 5
fi
if tar -tf "$TARBALL" | awk '/(^\/|(^|\/)\.\.(\/|$))/{bad=1} END{exit (bad?0:1)}'; then
  echo 'ERROR: archive has unsafe path entries.' >&2; exit 5
fi
# Archive is an installed Debian-package artifact; no untrusted source URL is accepted.
tar -xf "$TARBALL" -C "$WORK/src" --no-same-owner
SOURCE="$WORK/src/linux-source-6.12"
if [[ ! -f "$SOURCE/Makefile" || ! -f "$SOURCE/scripts/config" || ! -d "$SOURCE/arch/x86" ]]; then
  echo 'ERROR: extracted source tree incomplete.' >&2; exit 5
fi
SOURCE_VERSION="$(make --no-print-directory -s -C "$SOURCE" kernelversion)"
if [[ "$SOURCE_VERSION" != 6.12.* ]]; then
  echo "ERROR: unexpected kernel source $SOURCE_VERSION (expected 6.12.x)" >&2; exit 5
fi
cp -- "$CONFIG" "$WORK/obj/.config"
"$SOURCE/scripts/config" --file "$WORK/obj/.config" --set-str LOCALVERSION "-pulse-$RELEASE"
"$SOURCE/scripts/config" --file "$WORK/obj/.config" --disable LOCALVERSION_AUTO
"$ROOT/scripts/p1-harden-config.sh" "$SOURCE" "$WORK/obj"
JOBS="${PULSE_JOBS:-2}"
if ! [[ "$JOBS" =~ ^[1-9][0-9]*$ ]] || (( JOBS > 32 )); then
  echo 'ERROR: PULSE_JOBS must be between 1 and 32.' >&2; exit 5
fi
make --no-print-directory -C "$SOURCE" O="$WORK/obj" olddefconfig
python3 "$ROOT/scripts/config-audit.py" "$WORK/obj/.config"
python3 "$ROOT/scripts/config-audit.py" "$WORK/obj/.config" --requirements "$ROOT/config/p1-security-policy.json"
KERNEL_RELEASE="$(make --no-print-directory -s -C "$SOURCE" O="$WORK/obj" kernelrelease)"
if [[ "$KERNEL_RELEASE" != 6.12.*-pulse-$RELEASE ]]; then
  echo "ERROR: kernel release mismatch $KERNEL_RELEASE" >&2; exit 5
fi
if [[ -e "$DIST/$KERNEL_RELEASE" ]]; then
  echo "ERROR: release directory already exists ($DIST/$KERNEL_RELEASE). Refusing overwrite before compilation." >&2
  exit 6
fi
{
  echo 'PULSE_RELEASE=p1.0.0'
  echo "KERNEL_RELEASE=$KERNEL_RELEASE"
  echo "DEBIAN_SOURCE_PACKAGE=$SOURCE_PACKAGE"
  echo "DEBIAN_SOURCE_VERSION=$PKG_VERSION"
  echo "UPSTREAM_VERSION=$SOURCE_VERSION"
  echo "DEBIAN_SOURCE_TAR_SHA256=$(sha256sum "$TARBALL" | awk '{print $1}')"
  echo "BUILD_CONFIG_SHA256=$(sha256sum "$WORK/obj/.config" | awk '{print $1}')"
  echo "BASE_CONFIG_SHA256=$(sha256sum "$CONFIG" | awk '{print $1}')"
  echo "GCC=$(gcc -dumpfullversion)"
  echo "BUILD_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo 'SOURCE_ORIGIN=APT Debian 13 installed linux-source-6.12; trust depends on configured Debian archive keys'
} > "$WORK/provenance.txt"
echo 'Beginning full kernel build; this may take hours on modest hardware.'
fakeroot make -j "$JOBS" --no-print-directory -C "$SOURCE" O="$WORK/obj" bindeb-pkg

OUT="$DIST/$KERNEL_RELEASE"
if [[ -e "$OUT" ]]; then
  echo "ERROR: output directory already exists: $OUT (will not overwrite)" >&2; exit 6
fi
mkdir "$OUT"
# bindeb-pkg normally places .deb files in the parent of the object directory.
mapfile -d '' PACKAGES < <(find "$WORK" -maxdepth 4 -type f -name '*.deb' -print0)
if (( ${#PACKAGES[@]} == 0 )); then echo 'ERROR: no Debian kernel packages produced.' >&2; exit 6; fi
for pkg in "${PACKAGES[@]}"; do cp -p "$pkg" "$OUT/"; done
cp "$WORK/provenance.txt" "$OUT/"
cp "$WORK/obj/.config" "$OUT/pulse-kernel.config"
# Preserve corresponding Linux source with distributed binaries for GPL compliance.
cp -- "$TARBALL" "$OUT/linux-source-6.12.tar.xz"
mkdir "$OUT/pulse-build-tools"
cp "$ROOT/scripts/build-pulse.sh" "$ROOT/scripts/config-audit.py" "$ROOT/scripts/verify-release.sh" "$ROOT/scripts/boot-smoke.sh" "$ROOT/scripts/extract-kernel-image.sh" "$ROOT/scripts/p1-harden-config.sh" "$OUT/pulse-build-tools/"
cp "$ROOT/config/required-config.json" "$ROOT/config/p1-security-policy.json" "$OUT/pulse-build-tools/"
cp "$LOG" "$OUT/build.log"
(
  cd "$OUT"
  sha256sum -- *.deb pulse-kernel.config provenance.txt linux-source-6.12.tar.xz pulse-build-tools/* > SHA256SUMS
)
"$ROOT/scripts/verify-release.sh" "$OUT"
echo "PULSE P1.0.0 BUILD PRODUCED: $OUT"
echo 'Status: binaries compiled. Still UNTESTED for boot, security and Velora integration.'
