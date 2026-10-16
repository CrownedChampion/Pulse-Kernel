"""Pulse Memory: PSI-aware diagnostics and explicit scoped resource controls."""
from .common import read
import re


def parse_psi(text):
    lines = {}
    for line in (text or '').splitlines():
        bits = line.split()
        if bits and bits[0] in ('some','full'):
            fields = {}
            for part in bits[1:]:
                if '=' in part:
                    k, v = part.split('=',1)
                    try: fields[k] = float(v)
                    except ValueError: pass
            lines[bits[0]] = fields
    return lines


def status():
    meminfo = {}
    for line in (read('/proc/meminfo') or '').splitlines():
        if ':' in line:
            k, v = line.split(':',1)
            if k in ('MemTotal','MemAvailable','SwapTotal','SwapFree','Zswap','Zswapped','Cached'):
                meminfo[k] = v.strip()
    psi = parse_psi(read('/proc/pressure/memory'))
    some = psi.get('some', {}).get('avg10', 0)
    return {'memory': meminfo, 'psi': psi,
            'pressure_interpretation': 'elevated' if some > 10 else 'low_or_unmeasurable',
            'pressure_warning_threshold_pct_avg10': 10,
            'zram': [p.name for p in __import__('pathlib').Path('/sys/block').glob('zram*')],
            'mitigation': 'background workloads should use opt-in cgroup v2 limits/weights; do not change global reclaim heuristics without profiling',
            'performance_gain_verified': False}
