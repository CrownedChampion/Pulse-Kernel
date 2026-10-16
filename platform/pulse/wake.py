"""Pulse Wake: boot measurements and security gate, read-only by default."""
from .common import read, command
from . import security

def status():
    return {'boot_timing': command(['systemd-analyze', 'time']),
            'boot_loader': command(['bootctl', 'status']),
            'boot_id': (read('/proc/sys/kernel/random/boot_id') or '').strip(),
            'system_integrity': security.status(),
            'boot_update_policy': 'Only signed offline updates to inactive verified root slot; boot handoff requires platform-specific integration, not installed by this package',
            'automatic_rollback_implemented': False}
