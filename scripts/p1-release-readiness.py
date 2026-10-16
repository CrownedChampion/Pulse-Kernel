#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Pulse P1 release gate. Records evidence but NEVER grants security certification.

A successful test of a single component does not prove signed-boot continuity or
hardware compatibility. This tool intentionally defaults to RELEASE BLOCKED.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

PULSE_RELEASE = 'P1'
BOOT = re.compile(rb'^PULSE_BOOT_OK release=6\.12\.[0-9]+-pulse-p1\.0\.0\r?$', re.M)
GATES = {
    'real_kernel_packages': 'Real image + header Debian packages built and verified',
    'qemu_boot': 'Compiled kernel booted a disposable QEMU initramfs',
    'uefi_signed_boot': 'UEFI Secure Boot plus authenticated kernel/initramfs/cmdline proved',
    'verity_root': 'Kernel boots into authenticated dm-verity immutable root',
    'rollback': 'A/B update failure and rollback tested, with rollback prevention',
    'hardware': 'Supported hardware matrix and driver, networking/audio, suspend/resume validated',
    'sandbox': 'MAC, capabilities, filesystem and process attacks independently tested',
    'vault': 'Secure Rift real create/unlock/lock/recovery and adversarial review',
    'benchmarks': 'Boot latency, responsiveness, gaming, power comparisons measured',
    'velora_latest': 'Latest Velora source/hardware integration verified with rollback',
    'third_party_assessment': 'External security assessment completed by qualified independent reviewers',
    'licenses': 'Full corresponding GPL Linux kernel source, notices and patch provenance audited',
}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kernel-release-dir', help='Directory with genuine .deb build and provenance')
    p.add_argument('--boot-log', help='Serial output from a real QEMU smoke boot')
    p.add_argument('--out', help='New output report JSON path')
    args = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    results = {key: {'pass': False, 'why': label} for key, label in GATES.items()}
    evidence = {}
    if args.kernel_release_dir:
        directory = Path(args.kernel_release_dir).resolve()
        verify = subprocess.run(['bash', str(root / 'scripts/verify-release.sh'), str(directory)],
                                capture_output=True, text=True, timeout=90, check=False)
        if verify.returncode == 0:
            results['real_kernel_packages'] = {'pass': True, 'why': 'Package structure/config/provenance SHA checked (not a boot test)'}
            evidence['kernel_release_provenance_sha256'] = digest(directory / 'provenance.txt')
        else:
            results['real_kernel_packages']['detail'] = verify.stderr[-500:] or verify.stdout[-500:]
    if args.boot_log:
        bootlog = Path(args.boot_log)
        if bootlog.is_file() and BOOT.search(bootlog.read_bytes()):
            if results['real_kernel_packages']['pass']:
                results['qemu_boot'] = {'pass': True, 'why': 'QEMU serial success evidence supplied; compare to submitted kernel hash in external audit'}
                evidence['serial_log_sha256'] = digest(bootlog)
            else:
                results['qemu_boot']['detail'] = 'Boot log without verified corresponding kernel package is insufficient'
        else:
            results['qemu_boot']['detail'] = 'Missing actual serial boot success marker'
    report = {
        'release': PULSE_RELEASE, 'production_ready': False, 'security_certified': False,
        'release_decision': 'BLOCKED', 'evidence': evidence, 'gates': results,
        'explanation': 'All 12 gates require independently reviewed primary evidence; this tool cannot certify a system. Hardware and third-party security sign-off cannot be inferred from logs.'
    }
    data = json.dumps(report, indent=2, sort_keys=True) + '\n'
    if args.out:
        dest = Path(args.out)
        if dest.exists() or dest.is_symlink():
            raise SystemExit('ERROR: report output already exists; refusing overwrite')
        dest.write_text(data)
    print(data, end='')
    return 1  # Release blocker by design until independent verified assessments and all gates are completed.


if __name__ == '__main__':
    sys.exit(main())
