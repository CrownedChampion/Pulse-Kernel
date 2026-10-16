"""Rift fail-closed and anti-footgun tests (no host encryption or mounts)."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'platform'))
from pulse import rift, fs

class VaultGuardTests(unittest.TestCase):
    def test_safe_names_only(self):
        for bad in ['../etc', '../../root', 'Foo', 'x y', '', 'a'*33, 'r!ft', '/tmp', '.hidden', 'a/../b']:
            with self.subTest(name=bad), self.assertRaises(ValueError):
                rift.name_check(bad)
        self.assertEqual(rift.name_check('my-private-vault'), 'my-private-vault')

    def test_path_fixed_and_no_traversal(self):
        self.assertEqual(rift._paths('private')[0], Path('/var/lib/secure-rift/vaults/private.luks'))
        self.assertEqual(rift._paths('private')[3], 'secure-rift-private')

    def test_normal_users_cannot_create_unlock_lock(self):
        with patch.object(rift.os,'geteuid',return_value=1000):
            with self.assertRaises(PermissionError): rift.create('private','user',1,True)
            with self.assertRaises(PermissionError): rift.unlock('private')
            with self.assertRaises(PermissionError): rift.lock('private')

    def test_creation_requires_explicit_confirmation(self):
        with patch.object(rift.os,'geteuid',return_value=0):
            with self.assertRaises(ValueError): rift.create('private','user',1,False)

    def test_size_bounds_reject_unsafe_values(self):
        with patch.object(rift.os,'geteuid',return_value=0):
            with self.assertRaises(ValueError): rift.create('private','user',0,True)
            with self.assertRaises(ValueError): rift.create('private','user',1025,True)
            with self.assertRaises(ValueError): rift.create('private','user',True,True)

    def test_directories_cannot_be_symlinks_or_world_writable(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            p = root/'rootdir'
            p.mkdir(mode=0o700)
            with patch.object(rift.os,'geteuid',return_value=0):
                # Even under root this must reject untrusted ownership.
                with patch.object(rift,'_path_check', wraps=rift._path_check):
                    with self.assertRaises(PermissionError):
                        p.chmod(0o777)
                        rift._path_check(p,0o700)
            link = root/'link'
            link.symlink_to(p)
            with self.assertRaises(PermissionError): rift._path_check(link,0o700)

    def test_no_direct_user_exposure(self):
        self.assertFalse(rift.status()['plaintext_exposed_to_user_apps_by_default'])
        cat = fs.catalog()
        self.assertFalse(cat['secure_rift']['physical_path_exposed'])
        self.assertTrue(cat['secure_rift']['locked_by_default'])

    def test_shell_not_used_anywhere_in_rift(self):
        import inspect
        src = inspect.getsource(rift)
        self.assertNotIn('shell=True',src)
        self.assertNotIn('passphrase=',src)
        self.assertNotIn('--key-file',src)

    def test_absent_cryptsetup_is_detected(self):
        with patch.object(rift.shutil,'which',return_value=None):
            self.assertFalse(rift.check()['supported_tools']['cryptsetup'])
            with self.assertRaises(RuntimeError): rift._tool('cryptsetup')

if __name__ == '__main__': unittest.main(verbosity=2)
