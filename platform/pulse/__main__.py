"""Pulse CLI with read-only inspection and explicit opt-in operations."""
import argparse
import sys
from . import identity, motion, memory, fs, frame, link, wake, guard, security, rift
from .common import write_json

STATUS = {'identity': identity.status, 'motion': motion.status, 'guard': guard.status,
          'memory': memory.status, 'fs': fs.catalog, 'frame': frame.status,
          'link': link.status, 'wake': wake.status, 'security': security.status, 'rift': rift.status}

def main(argv=None):
    p = argparse.ArgumentParser(prog='pulse', description='Pulse P1 Linux-derived platform')
    sub = p.add_subparsers(dest='action', required=True)
    s = sub.add_parser('status', help='read-only subsystem inspection')
    s.add_argument('component', choices=['all', *STATUS], nargs='?', default='all')
    m = sub.add_parser('motion-run', help='run a program in a systemd workload scope')
    m.add_argument('profile', choices=motion.PROFILES.keys())
    m.add_argument('program', nargs=argparse.REMAINDER)
    g = sub.add_parser('guard-run', help='launch offline sandbox (fail closed)')
    g.add_argument('program', nargs=argparse.REMAINDER)
    d = sub.add_parser('wifi-diagnose', help='read-only Wi-Fi failure tracing')
    v = sub.add_parser('verify-bundle', help='verify signed Pulse bundle; no installation')
    v.add_argument('bundle'); v.add_argument('--trusted-key', required=True)
    st = sub.add_parser('stage-bundle', help='offline staging of signed artifacts; does not modify boot')
    st.add_argument('bundle'); st.add_argument('destination'); st.add_argument('--trusted-key', required=True)
    rf = sub.add_parser('rift', help='Secure Rift volume lifecycle; never exposes plaintext to untrusted applications')
    rf_sub = rf.add_subparsers(dest='rift_action', required=True)
    rf_sub.add_parser('check', help='read-only tool/kernel capability preflight')
    cr = rf_sub.add_parser('create', help='root only: allocate a fresh LUKS2 volume; interactive passphrase')
    cr.add_argument('name'); cr.add_argument('--owner', required=True)
    cr.add_argument('--size-gib', type=int, required=True)
    cr.add_argument('--confirm-creation', action='store_true')
    un = rf_sub.add_parser('unlock', help='root only: mount encrypted volume for root only')
    un.add_argument('name'); un.add_argument('--readonly', action='store_true')
    lk = rf_sub.add_parser('lock', help='root only: unmount safely and close mapper')
    lk.add_argument('name')
    args = p.parse_args(argv)
    try:
        if args.action == 'rift':
            if args.rift_action == 'check': result = rift.check()
            elif args.rift_action == 'create':
                result = rift.create(args.name, args.owner, args.size_gib, args.confirm_creation)
            elif args.rift_action == 'unlock': result = rift.unlock(args.name, args.readonly)
            else: result = rift.lock(args.name)
            write_json(result)
            return 0
        if args.action == 'status':
            write_json({key: fn() for key, fn in STATUS.items() if args.component in ('all', key)})
            return 0
        if args.action == 'wifi-diagnose':
            write_json(link.wifi_diagnosis())
            return 0
        if args.action == 'verify-bundle':
            write_json(security.verify_manifest(args.bundle, args.trusted_key))
            return 0
        if args.action == 'stage-bundle':
            write_json(security.stage_bundle(args.bundle, args.trusted_key, args.destination))
            return 0
        prog = args.program[1:] if args.program and args.program[0] == '--' else args.program
        if args.action == 'motion-run': return motion.run(args.profile, prog)
        if args.action == 'guard-run': return guard.run(prog)
    except (RuntimeError, ValueError, OSError, PermissionError, KeyError) as exc:
        print(f'Pulse: {exc}', file=sys.stderr)
        return 3
    return 2

if __name__ == '__main__':
    sys.exit(main())
