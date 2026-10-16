"""Pulse P1 negative-path security tests; generate disposable keys; never ship them."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'platform'))
from pulse import security, guard
ROOT = Path(__file__).resolve().parents[1]

class SignedBundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='pulse-tests-')
        self.addCleanup(self.tmp.cleanup)
        self.p = Path(self.tmp.name)
        self.b = self.p / 'bundle'
        self.b.mkdir()
        self.secret = self.p / 'ephemeral-private.pem'
        self.public = self.p / 'ephemeral-public.pem'
        subprocess.run(['openssl', 'genpkey', '-algorithm', 'ED25519', '-out', str(self.secret)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['openssl','pkey','-in',str(self.secret), '-pubout', '-out',str(self.public)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for f in ('root.squashfs', 'root.verity', 'vmlinuz-pulse', 'initrd-pulse'):
            (self.b / f).write_bytes(b'PULSE TEST FIXTURE NOT BOOTABLE: '+f.encode())
        (self.b / 'root-hash.txt').write_text('a'*64+'\n')
        subprocess.run(['bash',str(ROOT/'security/create-signed-bundle.sh'),str(self.b),'1.0.0',
                        str(self.secret),'root.squashfs','root.verity','root-hash.txt','vmlinuz-pulse','initrd-pulse'],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def test_signature_verify_and_offline_stage(self):
        result = security.verify_manifest(self.b, self.public)
        self.assertEqual(result['version'], '1.0.0')
        stage = self.p/'staged'
        self.assertFalse(stage.exists())
        security.stage_bundle(self.b, self.public, stage)
        self.assertTrue(stage.is_dir())
        self.assertEqual(security.verify_manifest(stage, self.public)['roles'], result['roles'])
        with self.assertRaises(ValueError):
            security.stage_bundle(self.b, self.public, stage)

    def test_reject_tamper(self):
        with open(self.b/'root.squashfs','ab') as f: f.write(b'ATTACK')
        with self.assertRaisesRegex(ValueError,'integrity|size'):
            security.verify_manifest(self.b, self.public)

    def test_reject_forged_manifest(self):
        with open(self.b/'manifest.json','ab') as f: f.write(b'\n')
        with self.assertRaisesRegex(ValueError,'signature'):
            security.verify_manifest(self.b, self.public)

    def test_reject_wrong_signing_key(self):
        other = self.p/'wrong-private.pem'
        other_public = self.p/'wrong-public.pem'
        subprocess.run(['openssl','genpkey','-algorithm','ED25519','-out',str(other)], check=True, stdout=subprocess.DEVNULL)
        subprocess.run(['openssl','pkey','-in',str(other),'-pubout','-out',str(other_public)], check=True, stdout=subprocess.DEVNULL)
        with self.assertRaisesRegex(ValueError,'signature'):
            security.verify_manifest(self.b, other_public)

    def test_reject_symlink_artifact(self):
        (self.b/'root.squashfs').unlink()
        (self.b/'root.squashfs').symlink_to('/etc/hosts')
        with self.assertRaises(ValueError):
            security.verify_manifest(self.b, self.public)

    def test_reject_missing_signature(self):
        (self.b/'manifest.sig').unlink()
        with self.assertRaisesRegex(ValueError,'manifest'):
            security.verify_manifest(self.b, self.public)

    def test_missing_sandbox_denies(self):
        with patch.object(guard.shutil, 'which', return_value=None):
            with self.assertRaises(RuntimeError):
                guard.command(['/usr/bin/true'])
        with self.assertRaises(ValueError):
            guard.command([])

    def test_invalid_trusted_key_denies(self):
        with self.assertRaises(ValueError):
            security.verify_manifest(self.b, self.p/'nonexistent-key')

    def test_root_readonly_parsing(self):
        self.assertTrue(security.root_readonly('41 31 8:1 / / ro,nosuid - ext4 /dev/sda1 ro'))
        self.assertFalse(security.root_readonly('41 31 8:1 / / rw - ext4 /dev/sda1 rw'))
        self.assertFalse(security.root_readonly('41 31 0:30 / / ro - overlay overlay rw'))

if __name__ == '__main__': unittest.main(verbosity=2)
