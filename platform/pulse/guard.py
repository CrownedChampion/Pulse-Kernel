"""Pulse Guard: strict opt-in offline sandbox and signed executable identity.

Sandbox does not replace host LSM policy. No unsandboxed fallback exists.
"""
import os
import shutil
import subprocess
from pathlib import Path
from .security import verify_manifest


def status():
    return {'bubblewrap': bool(shutil.which('bwrap')),
            'policy': 'unshare net/user/ipc/pid/uts + readonly executable runtime + private home',
            'signed_bundles': 'signed artifact verification available; app grant broker not production-ready',
            'no_unsandboxed_fallback': True}


def command(argv):
    if not argv:
        raise ValueError('command required')
    if not shutil.which('bwrap'):
        raise RuntimeError('bubblewrap unavailable: Guard refuses unsandboxed execution')
    if not Path(argv[0]).is_absolute():
        raise ValueError('launch executable must have an absolute path')
    # No writable host bind mounts. /tmp and /home are private tmpfs. /etc only narrow system files.
    cmd = ['bwrap', '--die-with-parent', '--new-session', '--unshare-user',
           '--unshare-ipc', '--unshare-pid', '--unshare-net', '--unshare-uts',
           '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp',
           '--tmpfs', '/home', '--tmpfs', '/run', '--tmpfs', '/var',
           '--dir', '/etc', '--chdir', '/tmp', '--clearenv',
           '--setenv', 'PATH', '/usr/bin:/bin', '--setenv', 'HOME', '/home/pulse-app',
           '--setenv', 'LANG', 'C.UTF-8']
    for path in ('/usr', '/bin', '/sbin', '/lib', '/lib64'):
        if os.path.exists(path):
            cmd.extend(['--ro-bind', path, path])
    for path in ('/etc/ld.so.cache', '/etc/nsswitch.conf', '/etc/localtime'):
        if os.path.isfile(path):
            cmd.extend(['--ro-bind', path, path])
    return cmd + ['--'] + argv


def run(argv):
    return subprocess.run(command(argv), check=False).returncode


def run_signed(bundle, public_key, executable_role='app'):
    result = verify_manifest(bundle, public_key)
    if executable_role not in result['roles']:
        raise ValueError('signed app executable missing')
    exe = Path(bundle) / result['roles'][executable_role]
    if not exe.is_file() or exe.is_symlink() or not (exe.stat().st_mode & 0o111):
        raise ValueError('signed executable is unavailable or not executable')
    # The currently implemented bubblewrap runner exposes only /usr. Signed app
    # execution from a bundle requires a separate read-only /app bind and sandbox
    # unit verification. Deliberately fail closed rather than run unsandboxed.
    raise RuntimeError('signed app bundle verified; production execution broker unavailable: denied')
