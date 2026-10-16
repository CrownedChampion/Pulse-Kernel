#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cat > "$TMP/uname_test.c" <<'C'
#include <stdio.h>
#include <sys/utsname.h>
int main(void) { struct utsname u; if (uname(&u)) return 1; puts(u.sysname); return 0; }
C
cc -Wall -Wextra -Werror -o "$TMP/pace" "$TMP/uname_test.c"
cc -Wall -Wextra -Werror -o "$TMP/linux-app" "$TMP/uname_test.c"
REAL="$($TMP/linux-app)"
[[ "$REAL" == Linux ]] || { echo "Unexpected host uname: $REAL" >&2; exit 1; }
PACE="$($ROOT/identity/pulse-pace "$TMP/pace")"
[[ "$PACE" == Pulse ]] || { echo "Pace wrapper returned $PACE" >&2; exit 1; }
# Inherited environment must never change the identity of another executable.
LINUX="$(PULSE_PACE_IDENTITY=1 PULSE_PACE_EXECUTABLE="$TMP/pace" LD_PRELOAD="$ROOT/identity/libpulse_pace_identity.so" "$TMP/linux-app")"
[[ "$LINUX" == Linux ]] || { echo 'Spoof leaked to another Linux app' >&2; exit 1; }
# Even /bin/uname remains Linux under inherited preload; target check is exact.
KERNEL="$(PULSE_PACE_IDENTITY=1 PULSE_PACE_EXECUTABLE="$TMP/pace" LD_PRELOAD="$ROOT/identity/libpulse_pace_identity.so" uname -s)"
[[ "$KERNEL" == Linux ]] || { echo 'Global uname changed unexpectedly' >&2; exit 1; }
# Refuse wrapping non-Pace programs.
if "$ROOT/identity/pulse-pace" "$TMP/linux-app" >/dev/null 2>&1; then
  echo 'WRAPPER BUG: launched non-Pace program' >&2; exit 1
fi
# Without wrapper, Pace remains Linux like other Linux apps.
[[ "$($TMP/pace)" == Linux ]]
echo 'PASS: Pace opt-in sees Pulse; unrelated Linux apps see Linux; no global ABI change'
