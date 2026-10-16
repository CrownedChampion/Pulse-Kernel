"""Restricted, read-only machine inspection and explicit command execution."""
import json
import os
import pathlib
import shutil
import subprocess


def read(path, limit=131072):
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read(limit)
    except (OSError, ValueError):
        return None


def lines(path):
    value = read(path)
    return value.splitlines() if value is not None else []


def command(argv, timeout=6):
    if not shutil.which(argv[0]):
        return {'ok': False, 'error': f'{argv[0]} is not installed'}
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                           check=False, env={**os.environ, 'LC_ALL': 'C'})
        return {'ok': r.returncode == 0, 'exit_code': r.returncode,
                'stdout': r.stdout[:8192], 'stderr': r.stderr[:2048]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'ok': False, 'error': str(exc)}


def human_bytes(n):
    for unit in ['B', 'KiB', 'MiB', 'GiB', 'TiB']:
        if n < 1024 or unit == 'TiB':
            return f'{n:.1f} {unit}'
        n /= 1024


def write_json(obj):
    print(json.dumps(obj, indent=2, sort_keys=True))


def is_cgroup_v2():
    return pathlib.Path('/sys/fs/cgroup/cgroup.controllers').exists()
