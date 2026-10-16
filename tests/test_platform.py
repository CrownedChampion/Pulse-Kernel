import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../platform')))
from pulse import motion, guard, fs, identity, memory, wake, link, frame

class PulseUnitTests(unittest.TestCase):
    def test_all_statuses(self):
        for cls in [motion.status, guard.status, fs.catalog, identity.status,
                    memory.status, wake.status, link.status, frame.status]:
            self.assertIsInstance(cls(), dict)

    def test_motion_classes(self):
        self.assertTrue(set(('balanced','interactive','gaming','creation','background','battery')) <= set(motion.PROFILES))
        for profile in motion.PROFILES.values():
            self.assertGreaterEqual(profile['CPUWeight'], 1)
            self.assertLessEqual(profile['CPUWeight'], 10000)
        with self.assertRaises(ValueError):
            motion.scope_command('bad-profile', ['/bin/true'])
        with self.assertRaises(ValueError):
            motion.scope_command('gaming', [])

    def test_scope_command_does_not_use_shell(self):
        with mock.patch.object(motion, 'is_cgroup_v2', return_value=True), mock.patch.object(motion.shutil, 'which', return_value='/bin/systemd-run'):
            cmd = motion.scope_command('gaming', ['/bin/echo', 'a;echo pwned'])
        self.assertEqual(cmd[-2:], ['/bin/echo', 'a;echo pwned'])
        self.assertIn('CPUWeight=300', cmd)

    def test_guard_fails_closed(self):
        with mock.patch.object(guard.shutil, 'which', return_value=None):
            with self.assertRaises(RuntimeError):
                guard.command(['/bin/true'])
        with self.assertRaises(ValueError):
            guard.command([])

    def test_fs_catalog_is_readonly(self):
        result = fs.catalog()
        self.assertEqual(len(result['home_items']), 6)
        self.assertEqual(result['logical_sections'][0], 'Home')
        for item in result['home_items']:
            self.assertNotIn('filesystem_path', item)

    def test_native_identity_does_not_lie(self):
        s = identity.status()
        self.assertEqual(s['lineage'], 'Linux-derived')
        self.assertFalse(s['full_pulse_kernel_included'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
