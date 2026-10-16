"""Fail-closed tests for Pulse P1's RELEASE decisions (not certificate issuance)."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from importlib.machinery import SourceFileLoader
CONFIG = SourceFileLoader('pulse_cfg', str(ROOT/'scripts/config-audit.py')).load_module()

class ReleasePolicyTests(unittest.TestCase):
    def test_unmodified_debian_config_not_yet_p1_hardened(self):
        base = CONFIG.read_config(ROOT/'config/debian-6.12.107-amd64-reference.config')
        hardening = json.loads((ROOT/'config/p1-security-policy.json').read_text())
        issues = CONFIG.audit(base, hardening)
        self.assertGreaterEqual(sum(level == 'mandatory' for level, *_ in issues), 1)
        self.assertIn('CONFIG_MODULE_SIG_FORCE', [name for _, name, *_ in issues])

    def test_proposed_hardened_config_has_no_mandatory_policy_failures(self):
        baseline = CONFIG.read_config(ROOT/'config/debian-6.12.107-amd64-reference.config')
        hardening = json.loads((ROOT/'config/p1-security-policy.json').read_text())
        for key, accepted in hardening['mandatory'].items():
            baseline[key] = accepted[0]
        self.assertFalse([a for a in CONFIG.audit(baseline, hardening) if a[0] == 'mandatory'])

    def test_release_readiness_remains_blocked_even_with_unverified_log(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            fake = d/'serial.txt'
            fake.write_text('PULSE_BOOT_OK release=6.12.999-pulse-p1.0.0\n')
            result = subprocess.run([sys.executable, str(ROOT/'scripts/p1-release-readiness.py'),
                                     '--boot-log', str(fake)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            data = json.loads(result.stdout)
            self.assertFalse(data['security_certified'])
            self.assertFalse(data['production_ready'])
            self.assertEqual(data['release_decision'], 'BLOCKED')
            self.assertFalse(data['gates']['qemu_boot']['pass'])
            self.assertEqual(len(data['gates']), 12)

    def test_release_verifier_expects_p1(self):
        text = (ROOT/'scripts/verify-release.sh').read_text()
        self.assertIn('pulse-p1', text)
        self.assertNotIn('pulse-p0', text)

    def test_no_mock_boot_marker_in_runtime_code(self):
        script = (ROOT/'scripts/boot-smoke.sh').read_text()
        self.assertIn('qemu-system-x86_64', script)
        self.assertIn('rdinit=/init', script)
        self.assertIn('PULSE_BOOT_OK', script)
        self.assertIn('timeout', script)
        self.assertIn('-nodefaults', script)

if __name__ == '__main__':
    unittest.main()
