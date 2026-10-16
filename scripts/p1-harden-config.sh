#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# Apply proposed hardened options to a *copy* of the Debian kernel config.
# Hardware / vendor module signing compatibility still requires real testing.
set -Eeuo pipefail
[[ $# == 2 ]] || { echo "Usage: $0 /linux-source-6.12 /kernel-object-dir" >&2; exit 2; }
SRC="$1"; OBJ="$2"
[[ -x "$SRC/scripts/config" && -f "$OBJ/.config" ]] || { echo 'ERROR: kernel source/config not found' >&2; exit 3; }
CONFIG_TOOL="$SRC/scripts/config"
for option in HARDENED_USERCOPY RANDOMIZE_BASE STACKPROTECTOR_STRONG STRICT_KERNEL_RWX STRICT_MODULE_RWX SECURITY_LOCKDOWN_LSM SECURITY_APPARMOR SECURITY_LANDLOCK MODULE_SIG MODULE_SIG_FORCE MODULE_SIG_ALL DM_VERITY DM_CRYPT SQUASHFS BLK_DEV_DM; do
  "$CONFIG_TOOL" --file "$OBJ/.config" --enable "$option"
done
# Untrusted arbitrary kexec replaces kernel below the verified boot chain.
"$CONFIG_TOOL" --file "$OBJ/.config" --disable KEXEC
"$CONFIG_TOOL" --file "$OBJ/.config" --disable KEXEC_FILE
# Policy is checked again after olddefconfig resolves kernel dependencies.
echo 'Applied P1 security configuration requests (not a system security certification).'
