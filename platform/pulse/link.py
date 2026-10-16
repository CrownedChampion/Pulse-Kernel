"""Pulse Link: deterministic, read-only driver/firmware/network/audio fault path."""
from pathlib import Path
import re
from .common import read, command


def _driver(path):
    link = path / 'device/driver'
    try: return link.resolve(strict=True).name
    except OSError: return None


def _devices(base, pattern):
    return sorted(Path(base).glob(pattern)) if Path(base).exists() else []


def _get_rfkill():
    kills = []
    for dev in _devices('/sys/class/rfkill','rfkill*'):
        kills.append({'id': dev.name, 'type': (read(dev/'type') or '').strip(),
                      'software_block': (read(dev/'soft') or '').strip() == '1',
                      'hardware_block': (read(dev/'hard') or '').strip() == '1'})
    return kills


def status():
    interfaces = []
    for nic in _devices('/sys/class/net','*'):
        interfaces.append({'device': nic.name, 'operstate': (read(nic/'operstate') or '').strip(),
                           'driver': _driver(nic), 'wireless': (nic/'wireless').exists() or (nic/'phy80211').exists(),
                           'carrier': (read(nic/'carrier') or '').strip()})
    rfkill = _get_rfkill()
    wireless = [nic for nic in interfaces if nic['wireless']]
    return {'network': {'interfaces': interfaces, 'wireless_present': bool(wireless),
                        'hardware_radio_blocked': any(k['hardware_block'] for k in rfkill),
                        'software_radio_blocked': any(k['software_block'] for k in rfkill),
                        'rfkill': rfkill,
                        'network_manager': command(['nmcli', '-t', '-f', 'DEVICE,STATE', 'device', 'status']),
                        'dns_service': command(['resolvectl', 'status'], timeout=4)},
            'bluetooth': {'controllers': [p.name for p in _devices('/sys/class/bluetooth', 'hci*')],
                          'rfkill': [k for k in rfkill if k['type']=='bluetooth']},
            'audio': {'alsa_cards': [p.name for p in _devices('/sys/class/sound','card[0-9]*')],
                      'pipewire': command(['wpctl','status'], timeout=4)},
            'qca6174_checks': 'check PCI subsystem + firmware + ath10k_pci + rfkill + NM scan + DHCP + DNS; not auto-repaired',
            'principle': 'enumeration is not proof of device functionality; no false scan or audio success claims'}


def wifi_diagnosis():
    s = status()['network']
    stages = []
    if not s['wireless_present']:
        stages.append({'stage': 'interface enumeration', 'status': 'failed',
                       'next': 'inspect lspci -nnk, driver binding and firmware/board files'})
    elif s['hardware_radio_blocked']:
        stages.append({'stage': 'rfkill', 'status': 'blocked by hardware',
                       'next': 'use physical airplane-mode switch or BIOS setting; do not bypass'})
    elif s['software_radio_blocked']:
        stages.append({'stage': 'rfkill', 'status': 'software blocked',
                       'next': 'request authorized unblock through system UI'})
    else:
        stages.append({'stage': 'interface/rfkill', 'status': 'eligible for scan',
                       'next': 'validate actual scan, association, DHCP and DNS; not assumed working'})
    return {'steps': stages, 'driver_info': command(['lspci','-nnk'], timeout=8),
            'firmware_warnings': command(['journalctl','-k','-b','-p','warning','--no-pager','-n','30']),
            'no_fixes_applied': True}
