"""Real systemd-cgroup workload scheduling; explicit opt-in and default safety."""
import os
import shutil
import subprocess
from .common import is_cgroup_v2

# systemd controls established Linux policy knobs; no custom scheduler claim.
PROFILES = {
    'balanced': {'CPUWeight': 100, 'IOWeight': 100},
    'interactive': {'CPUWeight': 200, 'IOWeight': 150},
    'gaming': {'CPUWeight': 300, 'IOWeight': 250},
    'creation': {'CPUWeight': 175, 'IOWeight': 200},
    'background': {'CPUWeight': 25, 'IOWeight': 25},
    'battery': {'CPUWeight': 90, 'IOWeight': 80},
}


def status():
    return {
        'backend': 'systemd-run user transient scope, cgroup v2',
        'cgroup_v2': is_cgroup_v2(),
        'systemd_run_installed': bool(shutil.which('systemd-run')),
        'profile_properties': PROFILES,
        'limitation': 'Requires a functional systemd user manager; no real-time CPU scheduling or GPU overclocking',
    }


def scope_command(profile, argv):
    if profile not in PROFILES:
        raise ValueError('unknown profile')
    if not argv:
        raise ValueError('application command required')
    if not is_cgroup_v2() or not shutil.which('systemd-run'):
        raise RuntimeError('systemd-run and cgroup v2 are required; refusing to claim a profile')
    cmd = ['systemd-run', '--user', '--scope', '--collect', '--quiet']
    for key, val in PROFILES[profile].items():
        cmd.extend(['--property', f'{key}={val}'])
    return cmd + ['--'] + argv


def run(profile, argv):
    return subprocess.run(scope_command(profile, argv), check=False).returncode
