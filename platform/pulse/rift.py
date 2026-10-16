"""Secure Rift encrypted-vault foundation for Pulse P1.

This is root-operated volume lifecycle tooling, NOT the final graphical vault,
Vela capability broker or a proof of end-to-end malware resistance. Use LUKS2
via cryptsetup; never implement proprietary encryption or retain passphrases.

The decrypted ext4 filesystem is mounted ROOT-ONLY; the final user-facing
Rift service must pass narrowly scoped descriptors via an authenticated broker,
not expose the mount to all processes sharing a user's UID.
"""
# SPDX-License-Identifier: MIT
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import stat
import subprocess

VAULTS = Path('/var/lib/secure-rift/vaults')
MOUNTS = Path('/run/secure-rift')
NAME_RE = re.compile(r'^[a-z][a-z0-9-]{0,31}$')
UUID_RE = re.compile(r'^[a-fA-F0-9-]{36}$')
SAFE_PATH = '/usr/sbin:/usr/bin:/sbin:/bin'
REQUIRED_TOOLS = ('cryptsetup', 'mkfs.ext4', 'mount', 'umount', 'findmnt')


def name_check(name):
    if not isinstance(name, str) or not NAME_RE.fullmatch(name):
        raise ValueError('vault name must be 1–32 lower-case ASCII letters/numbers/hyphens, starting with a letter')
    return name


def _root():
    if os.geteuid() != 0:
        raise PermissionError('Secure Rift lifecycle operations require the dedicated privileged service/root')
    os.umask(0o077)


def _path_check(path, expected_mode, create=False):
    """Ensure directory belongs to root and has controlled permissions, no symlinks."""
    if create:
        try:
            path.mkdir(mode=expected_mode)
        except FileExistsError:
            pass
    try:
        s = path.lstat()
    except FileNotFoundError as exc:
        raise ValueError(f'required protected directory is absent: {path}') from exc
    if not stat.S_ISDIR(s.st_mode) or s.st_uid != 0 or (s.st_mode & 0o022):
        raise PermissionError(f'unsafe directory ownership/type/permissions: {path}')
    if stat.S_IMODE(s.st_mode) != expected_mode:
        raise PermissionError(f'expected mode {expected_mode:04o} for protected directory: {path}')


def _dirs(create=False):
    _path_check(VAULTS.parent, 0o700, create=create)
    _path_check(VAULTS, 0o700, create=create)
    _path_check(MOUNTS, 0o700, create=create)


def _tool(program):
    """Require a root-controlled executable, not something supplied by cwd/PATH."""
    path = shutil.which(program, path=SAFE_PATH)
    if not path:
        raise RuntimeError(f'{program} unavailable; Secure Rift fails closed')
    target = Path(path).resolve(strict=True)
    s = target.stat()
    if s.st_uid != 0 or not stat.S_ISREG(s.st_mode) or (s.st_mode & 0o022):
        raise PermissionError(f'unsafe executable permissions: {program}')
    return str(target)


def _run(program, *args, capture=False):
    exe = _tool(program)
    env = {'PATH': SAFE_PATH, 'LANG': 'C', 'LC_ALL': 'C', 'HOME': '/root'}
    # No user-derived shell, no passphrase in arguments/environment, no logs of stdin.
    p = subprocess.run([exe, *[str(x) for x in args]], check=False,
                       stdin=None, stdout=subprocess.PIPE if capture else None,
                       stderr=subprocess.PIPE if capture else None,
                       env=env, timeout=300)
    if p.returncode:
        raise RuntimeError(f'{program} failed (exit {p.returncode}); no security fallback was applied')
    return p.stdout.decode('ascii', errors='replace').strip() if capture else None


def _regular_root_file(path):
    s = path.lstat()
    if not stat.S_ISREG(s.st_mode) or s.st_uid != 0 or stat.S_IMODE(s.st_mode) != 0o600 or s.st_nlink != 1:
        raise PermissionError('vault file/metadata is not a root-owned 0600 regular file with one link')
    return s


def _paths(name):
    name = name_check(name)
    return (VAULTS / f'{name}.luks', VAULTS / f'{name}.json', MOUNTS / name,
            f'secure-rift-{name}')


def _uuid(image):
    result = _run('cryptsetup', 'luksUUID', image, capture=True)
    if not UUID_RE.fullmatch(result):
        raise ValueError('unexpected or missing LUKS UUID')
    return result.lower()


def _metadata(name):
    image, meta, _, _ = _paths(name)
    _dirs()
    _regular_root_file(image)
    _regular_root_file(meta)
    with meta.open('r', encoding='utf-8') as f:
        data = json.load(f)
    if (data.get('schema') != 1 or data.get('name') != name or
        not isinstance(data.get('owner_uid'), int) or data['owner_uid'] < 1000 or
        not isinstance(data.get('luks_uuid'), str) or not UUID_RE.fullmatch(data['luks_uuid'])):
        raise ValueError('invalid Secure Rift metadata')
    if _uuid(image) != data['luks_uuid']:
        raise ValueError('encrypted volume UUID differs from protected metadata; refusing unlock')
    return data


def _mapped(mapper):
    return Path('/dev/mapper', mapper).exists()


def _mount_source(path):
    # Fail if findmnt is absent; exact mountpoint only (not a parent mount).
    cmd = [_tool('findmnt'), '--json', '--mountpoint', str(path), '--output', 'SOURCE,TARGET']
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
                       env={'PATH': SAFE_PATH, 'LANG': 'C'}, timeout=10)
    if p.returncode:
        return None
    rows = json.loads(p.stdout.decode('utf-8')).get('filesystems', [])
    return rows[0].get('source') if len(rows) == 1 and rows[0].get('target') == str(path) else None


def _confirm_mount(path, mapper):
    source = _mount_source(path)
    if source is None:
        return False
    intended = Path('/dev/mapper', mapper)
    if not intended.exists():
        raise RuntimeError('mount exists but expected mapper missing; refusing destructive action')
    try:
        if not os.path.samefile(source, intended):
            raise RuntimeError('mount is not backed by expected Rift volume; refusing action')
    except FileNotFoundError as exc:
        raise RuntimeError('cannot authenticate mount source') from exc
    return True


def status():
    return {
        'name': 'Secure Rift', 'model': 'LUKS2/dm-crypt with Argon2id passphrase; root-restricted mounts',
        'cryptsetup_available': bool(shutil.which('cryptsetup', path=SAFE_PATH)),
        'dm_crypt_available': Path('/sys/module/dm_crypt').exists(),
        'plaintext_exposed_to_user_apps_by_default': False,
        'permission_broker_complete': False,
        'secure_boot_chain_required_for_full_assurance': True,
        'notes': 'Root lifecycle tooling only. Locked volumes encrypt file content; after unlock root/kernel compromise can expose secrets.',
    }


def check():
    """Safe unprivileged preflight; does not open or create any vault."""
    return {'supported_tools': {tool: bool(shutil.which(tool, path=SAFE_PATH)) for tool in REQUIRED_TOOLS},
            'kernel_dm_crypt': Path('/sys/module/dm_crypt').exists(),
            'kernel_dm_integrity': Path('/sys/module/dm_integrity').exists(),
            'minimum_volume_gib': 1,
            'passphrase_policy': 'cryptsetup terminal prompt; never pass the secret as a command-line argument',
            'vault_access_model': 'root-only until authenticated per-app broker is built',
            'ready_for_production': False}


def create(name, owner, size_gib, confirmed=False):
    """Create fresh non-sparse LUKS2 image. Explicit privilege and confirmation required."""
    _root()
    if not confirmed:
        raise ValueError('explicit --confirm-creation required; operation allocates a new encrypted vault')
    image, meta, mountpoint, mapper = _paths(name)
    if isinstance(size_gib, bool) or not isinstance(size_gib, int) or not 1 <= size_gib <= 1024:
        raise ValueError('size must be 1–1024 GiB')
    account = pwd.getpwnam(owner)
    if account.pw_uid < 1000:
        raise ValueError('vault owner must be an unprivileged local user (UID >= 1000)')
    _dirs(create=True)
    for p in (image, meta, mountpoint):
        if p.exists() or p.is_symlink():
            raise FileExistsError(f'refusing to overwrite existing vault material or mountpoint: {p}')
    if _mapped(mapper):
        raise RuntimeError('vault mapper name already in use')
    for tool in REQUIRED_TOOLS:
        _tool(tool)
    fd = os.open(image, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        # Fully reserve storage; sparse allocation can cause catastrophic ENOSPC mid-write.
        os.posix_fallocate(fd, 0, size_gib * (1024 ** 3))
        os.fsync(fd)
    finally:
        os.close(fd)
    try:
        _run('cryptsetup', '--type', 'luks2', '--pbkdf', 'argon2id',
             '--pbkdf-memory', '262144', '--iter-time', '5000',
             '--verify-passphrase', 'luksFormat', image)
        _run('cryptsetup', 'open', image, mapper)
        try:
            _run('mkfs.ext4', '-F', '-m', '0', '/dev/mapper/' + mapper)
        finally:
            _run('cryptsetup', 'close', mapper)
        data = {'schema': 1, 'name': name, 'owner_uid': account.pw_uid,
                'owner_gid': account.pw_gid, 'luks_uuid': _uuid(image),
                'format': 'LUKS2', 'pbkdf': 'argon2id', 'filesystem': 'ext4',
                'default_mount_access': 'root-only'}
        meta_fd = os.open(meta, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        try:
            with os.fdopen(meta_fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, sort_keys=True)
                f.write('\n')
                f.flush()
                os.fsync(f.fileno())
        except BaseException:
            # Do not leave a false complete-looking metadata record.
            if meta.exists(): meta.unlink()
            raise
        # The encrypted image is deliberately retained if later work fails.
        return {'name': name, 'owner_uid': account.pw_uid, 'created': True,
                'locked': True, 'access': 'root-only; no per-app grant broker installed'}
    except BaseException:
        raise RuntimeError('Secure Rift vault setup incomplete; investigate protected image before retrying. No auto-deletion performed.') from None


def unlock(name, readonly=False):
    """Unlock only to a root-restricted mount. No general user/app access granted."""
    _root()
    image, _, mountpoint, mapper = _paths(name)
    _metadata(name)
    if _mapped(mapper):
        raise RuntimeError('vault mapper is already open')
    _path_check(MOUNTS, 0o700)
    if mountpoint.exists() or mountpoint.is_symlink():
        raise RuntimeError('vault mountpoint already exists; refusing ambiguous mount')
    mountpoint.mkdir(mode=0o700)
    try:
        args = ['open']
        if readonly: args.append('--readonly')
        args += [str(image), mapper]
        _run('cryptsetup', *args)
        try:
            options = 'ro' if readonly else 'rw'
            _run('mount', '-t', 'ext4', '-o', options + ',nosuid,nodev,noexec,noatime',
                 '/dev/mapper/' + mapper, mountpoint)
            if not _confirm_mount(mountpoint, mapper):
                raise RuntimeError('mount activation could not be independently confirmed')
        except BaseException:
            if _mount_source(mountpoint):
                # Never close a still-mounted mapper on cleanup.
                _run('umount', mountpoint)
            _run('cryptsetup', 'close', mapper)
            raise
        return {'name': name, 'unlocked': True, 'readonly': readonly,
                'access': 'root-only; app access denied until broker integration'}
    except BaseException:
        # Directory isn't a secret; leave it if a mount could not be safely removed.
        if not _mount_source(mountpoint):
            mountpoint.rmdir()
        raise


def lock(name):
    """Refuse force-unmount; held files keep the vault open rather than risk data loss."""
    _root()
    _, _, mountpoint, mapper = _paths(name)
    _metadata(name)
    if not _mapped(mapper):
        raise RuntimeError('vault is not open')
    if mountpoint.is_symlink():
        raise PermissionError('unsafe mountpoint')
    if _confirm_mount(mountpoint, mapper):
        _run('umount', mountpoint)  # fails if busy; never -l or -f
    elif _mount_source(mountpoint):
        raise RuntimeError('unrecognized active mount; refusing to close mapper')
    _run('cryptsetup', 'close', mapper)
    if mountpoint.is_dir() and not _mount_source(mountpoint):
        mountpoint.rmdir()
    return {'name': name, 'locked': True, 'kernel_plaintext_mapping_closed': True,
            'caution': 'Applications may retain previously obtained plaintext in memory or external copies'}
