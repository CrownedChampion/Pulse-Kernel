// SPDX-License-Identifier: MIT
/* Pulse scoped *product identity* interposer for the Pace executable only.
 * Leaves all kernel syscalls, privileges, and process.platform unchanged.
 * This is opt-in and not a security boundary. Direct SYS_uname bypasses it.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <limits.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <sys/syscall.h>
#include <sys/utsname.h>
#include <unistd.h>

static int is_scoped_pace(void) {
    const char *enable = secure_getenv("PULSE_PACE_IDENTITY");
    const char *want = secure_getenv("PULSE_PACE_EXECUTABLE");
    char actual[PATH_MAX];
    ssize_t n;
    if (!enable || strcmp(enable, "1") || !want || want[0] != '/')
        return 0;
    n = readlink("/proc/self/exe", actual, sizeof(actual)-1);
    if (n <= 0 || (size_t)n >= sizeof(actual)-1)
        return 0;
    actual[n] = '\0';
    return strcmp(actual, want) == 0;
}

int uname(struct utsname *buf) {
    /* Linux syscall gives authoritative real values without recursion. */
    long ret = syscall(SYS_uname, buf);
    if (ret == -1)
        return -1;
    if (is_scoped_pace()) {
        memcpy(buf->sysname, "Pulse", sizeof("Pulse"));
    }
    return 0;
}
