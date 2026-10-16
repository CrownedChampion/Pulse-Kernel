"""Pulse product identity, Linux compatibility remains intact."""
import platform
from .common import read

def status():
    return {'product': 'Pulse', 'release': '1.0.0',
            'lineage': 'Linux-derived', 'host_sysname': platform.system(),
            'host_release': platform.release(), 'kernel_module': read('/proc/pulse/status'),
            'linux_app_compatibility': 'uname Linux',
            'pace_exception': 'explicit opt-in LD_PRELOAD wrapper, libc uname only',
            'electron_process_platform': 'linux',
            'full_pulse_kernel_included': False}
