"""PulseFS V0.2 read-only logical storage catalog; never rewrites host paths."""
import hashlib
import os
from pathlib import Path
from .common import read

HOME = ('Desktop', 'Documents', 'Downloads', 'Pictures', 'Videos', 'Music')


def roots():
    home = Path.home()
    mapping = {k: home / k for k in HOME}
    xdg = read(home / '.config/user-dirs.dirs') or ''
    for line in xdg.splitlines():
        if not line.startswith('XDG_') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        dirname = key.replace('XDG_', '').replace('_DIR', '').title()
        if dirname not in mapping:
            continue
        value = value.strip().strip('"')
        if value.startswith('$HOME/'):
            mapping[dirname] = home / value[len('$HOME/'):]
    return mapping


def catalog():
    out = []
    for label, path in roots().items():
        # Not a file access grant: catalog describes known locations only.
        item = {'logical_location': f'Home/{label}',
                'item_id': hashlib.sha256((label + ':' + str(path)).encode()).hexdigest()[:24],
                'exists': path.is_dir(), 'kind': 'directory'}
        out.append(item)
    mounts = []
    for line in (read('/proc/self/mountinfo') or '').splitlines():
        a = line.split(' - ', 1)[0].split(' ')
        if len(a) > 4 and a[4].startswith(('/media/', '/run/media/', '/mnt/')):
            mounts.append({'mountpoint': a[4].replace('\\040', ' '), 'kind': 'external-or-manual'})
    return {
        'interface': 'PulseFS catalog prototype (no filesystem driver / no virtual mount)',
        'logical_sections': ['Home', 'Applications', 'Games', 'Compatibility', 'Devices', 'System', 'Secure Rift'],
        'secure_rift': {'kind': 'encrypted_private_vault', 'locked_by_default': True, 'location': 'Secure Rift',
                        'access': 'denied by default; Vela identity/broker grants not yet implemented',
                        'physical_path_exposed': False},
        'home_items': out,
        'devices': mounts,
        'policy': 'No host hierarchy rename, no FUSE in data plane, no automatic file grants',
        'unimplemented': ['revocable broker grants', 'Vela SDK portal', 'game library discovery', 'GUI'],
    }
