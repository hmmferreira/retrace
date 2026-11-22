import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock,patch
from retrace.native_consent import accepted,record,RECORD
from retrace.macos_runtime import MacRuntime
from retrace.owned_session import SessionBlocked

class NativeConsentTests(unittest.IsolatedAsyncioTestCase):
    async def test_fresh_stable_boot_never_acquires_or_provisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime=MacRuntime(Path(tmp),{'create_new_identity':True,'private_evaluation':False})
            with patch('retrace.macos_runtime.ensure',new_callable=AsyncMock) as ensure,patch('retrace.macos_runtime.provision',new_callable=AsyncMock) as provision:
                await runtime.prepare()
                self.assertTrue(runtime.consent_required())
                self.assertFalse(runtime.library.exists())
                with self.assertRaises(Exception) as caught:await runtime.account()
                self.assertEqual(caught.exception.code,'native_consent_required')
                ensure.assert_not_awaited();provision.assert_not_awaited()
    async def test_explicit_consent_records_terms_before_local_acquisition(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime=MacRuntime(Path(tmp),{'create_new_identity':True,'private_evaluation':False})
            with patch('retrace.macos_runtime.ensure',new_callable=AsyncMock) as ensure:
                await runtime.prepare(native_consent=True)
                self.assertTrue(accepted(runtime.root))
                ensure.assert_awaited_once_with(runtime.library,private_evaluation=False,local_consent=True)
                self.assertFalse(runtime.consent_required())
                value=json.loads((runtime.root/'native-consent.json').read_text())
                self.assertEqual(value,RECORD)
                self.assertNotIn('approved',value)
    async def test_corrupt_consent_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'native-consent.json'
            path.write_text('{}');path.chmod(0o600)
            with self.assertRaises(SessionBlocked):accepted(root)
            with self.assertRaises(SessionBlocked):record(root)
            self.assertEqual(path.read_text(),'{}')
