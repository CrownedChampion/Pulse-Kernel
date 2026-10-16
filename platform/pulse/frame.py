"""Pulse Frame: GPU discovery and non-invasive game stack compatibility probe."""
from pathlib import Path
from .common import read, command


def status():
    cards = []
    for p in sorted(Path('/sys/class/drm').glob('card[0-9]*')):
        if not (p/'device').exists(): continue
        try: driver = (p/'device/driver').resolve(strict=True).name
        except OSError: driver = 'unknown'
        cards.append({'card':p.name,'driver':driver,
                      'vendor_id':(read(p/'device/vendor') or '').strip(),
                      'device_id':(read(p/'device/device') or '').strip()})
    return {'kernel_drm': cards,
            'vulkan_loader': command(['vulkaninfo','--summary'],timeout=8),
            'game_tools': {'steam':command(['which','steam']),
                           'gamescope':command(['which','gamescope']),
                           'wine':command(['which','wine'])},
            'launch_profile': 'pulse motion-run gaming -- /absolute/game',
            'compatibility_warning': 'DXVK/Proton, NVIDIA driver, anti-cheat and console Game Mode need real GPU/game tests',
            'performance_claim': 'no independently measured FPS/frame-time improvement'}
