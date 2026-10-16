"""Pulse P1: machine-readable OS trust audit and signed offline release verification.

This module does NOT change boot state, permissions, firmware, or the running root.
Installations depend on a separately reviewed, independently trusted boot chain.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
from .common import read

MAX_MANIFEST = 1024 * 1024
MAX_IMAGE = 32 * 1024 ** 3
NAME = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$')
REQUIRED = {'root-image', 'verity-tree', 'root-hash', 'kernel', 'initramfs'}


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def verify_manifest(bundle, public_key):
    """Verify Ed25519 detached signature AND checksums. Public key must be provisioned separately.

    No automatic trust-on-first-use and no public key shipped inside an untrusted bundle.
    The manifest's names are flat so it cannot escape the bundle directory.
    """
    bundle = Path(bundle)
    public_key = Path(public_key)
    if not public_key.is_file() or public_key.is_symlink():
        raise ValueError('trusted public key unavailable: refusing unauthenticated update')
    if not bundle.is_dir() or bundle.is_symlink():
        raise ValueError('bundle is not an ordinary directory')
    manifest = bundle / 'manifest.json'
    signature = bundle / 'manifest.sig'
    for p in (manifest, signature):
        if not p.is_file() or p.is_symlink() or p.stat().st_size > MAX_MANIFEST:
            raise ValueError('missing/unsafe manifest or signature')
    if not shutil.which('openssl'):
        raise RuntimeError('OpenSSL required; fail closed')
    cmd = ['openssl', 'pkeyutl', '-verify', '-pubin', '-inkey', str(public_key),
           '-rawin', '-in', str(manifest), '-sigfile', str(signature)]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=15, check=False)
    if result.returncode:
        raise ValueError('manifest signature invalid or not trusted')
    if manifest.stat().st_size > MAX_MANIFEST:
        raise ValueError('manifest changed during verification')
    data = json.loads(manifest.read_bytes())
    if data.get('product') != 'Pulse' or data.get('format') != 1 or not isinstance(data.get('version'), str):
        raise ValueError('unexpected signed manifest schema')
    artifacts = data.get('artifacts')
    if not isinstance(artifacts, dict) or not REQUIRED <= artifacts.keys() or len(artifacts) > 16:
        raise ValueError('missing kernel/root/initramfs artifact set')
    verified = {}
    for role, info in artifacts.items():
        if not NAME.fullmatch(role) or not isinstance(info, dict):
            raise ValueError('invalid artifact role')
        filename, expected, length = info.get('file'), info.get('sha256'), info.get('size')
        if not isinstance(filename, str) or not NAME.fullmatch(filename) or filename in ('manifest.json', 'manifest.sig'):
            raise ValueError('unsafe artifact filename')
        if not isinstance(expected, str) or not re.fullmatch('[a-f0-9]{64}', expected):
            raise ValueError('invalid SHA-256')
        if type(length) is not int or length < 1 or length > MAX_IMAGE:
            raise ValueError('invalid artifact size')
        p = bundle / filename
        if p.is_symlink() or not p.is_file() or p.stat().st_size != length:
            raise ValueError(f'artifact missing, symlinked, or wrong size: {role}')
        if sha256(p) != expected:
            raise ValueError(f'artifact integrity failure: {role}')
        verified[role] = filename
    if len(set(verified.values())) != len(verified):
        raise ValueError('duplicate artifacts are forbidden')
    root_hash_file = bundle / verified['root-hash']
    rh = root_hash_file.read_text('ascii').strip() if root_hash_file.stat().st_size < 256 else ''
    if not re.fullmatch('[a-f0-9]{64}', rh):
        raise ValueError('signed root hash absent or malformed')
    if data.get('dm_verity_root_hash') != rh:
        raise ValueError('signed root hash mismatch')
    return {'version': data['version'], 'roles': verified, 'integrity': 'Ed25519 signature + SHA-256 verified',
            'caution': 'Valid signature does not prove a verified boot chain or hardware trust'}


def stage_bundle(bundle, public_key, destination):
    """Prepare an OFFLINE directory containing verified artifacts. No boot or mount writes."""
    bundle, destination = Path(bundle), Path(destination)
    result = verify_manifest(bundle, public_key)
    # Require destination path does not exist; refuse symlinked parent chain.
    parent = destination.parent.resolve(strict=True)
    if not parent.is_dir() or destination.exists() or destination.is_symlink():
        raise ValueError('destination must not already exist')
    if str(parent).startswith(('/boot', '/usr', '/etc', '/sys', '/proc', '/dev', '/run')):
        raise ValueError('refusing direct system/boot staging: use offline staging directory')
    if not NAME.fullmatch(destination.name):
        raise ValueError('unsafe staging directory name')
    tmp = Path(tempfile.mkdtemp(prefix='.pulse-stage-', dir=parent))
    try:
        for name in [*result['roles'].values(), 'manifest.json', 'manifest.sig']:
            source = bundle / name
            if source.is_symlink() or not source.is_file():
                raise ValueError('source changed during staging')
            target = tmp / name
            with source.open('rb') as src, target.open('xb') as dst:
                while True:
                    chunk = src.read(1024 * 1024)
                    if not chunk: break
                    dst.write(chunk)
                dst.flush()
                os.fsync(dst.fileno())
            os.chmod(target, 0o600)
        again = verify_manifest(tmp, public_key)
        if again['roles'] != result['roles']:
            raise ValueError('staged artifact changed')
        os.rename(tmp, destination)
        fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)
        return result
    finally:
        if tmp.exists():
            shutil.rmtree(tmp)


def read_secure_boot():
    directory = Path('/sys/firmware/efi/efivars')
    for path in directory.glob('SecureBoot-*') if directory.exists() else []:
        try:
            # EFI efivarfs begins with four attribute bytes.
            val = path.read_bytes()
            return 'enabled' if len(val) >= 5 and val[4] == 1 else 'disabled'
        except OSError:
            return 'unreadable'
    return 'unavailable'


def verity_devices():
    devices = []
    for entry in sorted(Path('/sys/block').glob('dm-*')):
        uuid = read(entry / 'dm/uuid') or ''
        if uuid.strip().upper().startswith('VERITY-'):
            devices.append({'device': entry.name, 'uuid_prefix': 'VERITY'})
    return devices


def root_readonly(mountinfo=None):
    lines = (mountinfo if mountinfo is not None else read('/proc/self/mountinfo') or '').splitlines()
    roots = [line for line in lines if len(line.split(' - ')[0].split(' ')) >= 6 and line.split(' - ')[0].split(' ')[4] == '/']
    if not roots:
        return False
    # A read-only root mount is necessary but not sufficient. Overlay roots are not trusted.
    mount = roots[-1]
    if ' - overlay ' in mount:
        return False
    return 'ro' in mount.split(' - ')[0].split(' ')[5].split(',')


def status():
    lockdown = (read('/sys/kernel/security/lockdown') or '').strip()
    apparmor = (read('/sys/module/apparmor/parameters/enabled') or '').strip()
    verity = verity_devices()
    ro = root_readonly()
    sb = read_secure_boot()
    # A dm-verity device may exist for another filesystem, hence do not infer root is protected.
    return {'product': 'Pulse P1 security audit', 'verified_boot_chain_proven': False,
            'secure_boot': sb, 'lockdown': lockdown or 'not measurable',
            'apparmor': 'available' if apparmor.lower() == 'y' else 'not confirmed',
            'root_readonly': ro, 'verity_devices_detected': verity,
            'root_dm_verity_proven': False,
            'system_tamper_resistance_certified': False,
            'note': 'Mount/EFI inspection alone cannot prove signed boot, root verity dependency, rollback prevention or complete sandbox coverage.'}
