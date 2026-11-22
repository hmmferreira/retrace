import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('findmy_build_context',Path(__file__).resolve().parents[1]/'tools/build_context.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class BuildContextTests(unittest.TestCase):
    def test_private_runtime_artifacts_never_enter_build_context(self):
        for name in ('nested/account.json','providers/macos/machine.json','active-provider.json','signer.lock','providers/macos/store.lock','providers/macos/native-consent.json','CoreADI.x86_64','iTunes.dmg','nested/owned-session.json','nested/identity.json','owned-libs.bin','source.apk','session-a.key','session-a.enc','nested/export.plist','data/settings.json','.git/config','package/__pycache__/module.pyc'):
            with self.subTest(name=name):self.assertFalse(module.allowed_path(name))
    def test_reviewed_public_policy_code_and_ca_remain_available(self):
        for name in ('Dockerfile.shared','requirements-shared.lock','rootfs/app/retrace/trusted_artifacts.json','rootfs/app/retrace/trust/apple-root-ca.pem','tests/fixtures/native_worker_fixture.py'):
            with self.subTest(name=name):self.assertTrue(module.allowed_path(name))
