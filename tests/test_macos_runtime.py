import asyncio
import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock,patch
from retrace.macos_runtime import MacRuntime
from retrace.macos_identity import new_machine
from retrace.macos_worker import MacSigner
from retrace.macos_artifact import LIBRARY_SHA
from retrace.macos_store import MachineStore
from retrace.storage import atomic_json
from retrace.private_session_store import active_provider

class MacRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.runtime=MacRuntime(self.root,{'create_new_identity':True})
        self.machine=new_machine();self.machine['routing']=42
        self.machine['saved']={'adi-000001F5.pb':base64.b64encode(b'synthetic-state').decode()}
    async def test_failed_new_session_never_changes_active_provider(self):
        atomic_json(self.root/'active-provider.json',{'version':1,'provider':'apple_music'})
        self.runtime.sessions.save=AsyncMock(side_effect=OSError('synthetic disk failure'))
        with self.assertRaises(OSError):await self.runtime.save(object())
        self.assertEqual(active_provider(self.root),'apple_music')
    async def test_switch_publishes_only_after_session_save(self):
        async def save(account):self.assertEqual(active_provider(self.root),'apple_music')
        self.runtime.sessions.save=AsyncMock(side_effect=save)
        await self.runtime.save(object())
        self.assertEqual(active_provider(self.root),'macos')
    async def test_corrupt_mac_machine_cannot_trigger_reprovisioning(self):
        self.runtime.machine_store.save(self.machine)
        (self.runtime.root/'machine.json').write_text('{}')
        self.runtime.options['private_evaluation']=True
        with patch('retrace.macos_runtime.ensure',new_callable=AsyncMock),patch('retrace.macos_runtime.provision',new_callable=AsyncMock) as provision:
            with self.assertRaises(Exception):await self.runtime.account()
            provision.assert_not_awaited()
    async def test_signers_serialize_state_and_reap_children(self):
        self.runtime.machine_store.save(self.machine)
        live=0;maximum=0;closed=0
        saved=self.machine['saved']
        class Channel:
            async def exchange(self,command,**kwargs):
                nonlocal live,maximum
                if command=='mac_prepare':
                    live+=1;maximum=max(maximum,live)
                    return {'phase':'ready'}
                await asyncio.sleep(.02)
                return {'headers':{'X-Apple-I-MD':'b3Rw','X-Apple-I-MD-M':'bWlk','X-Apple-I-MD-RINFO':'42'},'saved':saved}
            async def close(self):
                nonlocal live,closed
                live-=1;closed+=1
        state=json.dumps(self.machine).encode()
        first=MacSigner(self.runtime.library,state,LIBRARY_SHA);second=MacSigner(self.runtime.library,state,LIBRARY_SHA)
        with patch('retrace.macos_worker._NativeChannel',Channel),patch.object(MacSigner,'_read_artifact',return_value=b'synthetic'):
            await first.initialize();await second.initialize()
            await asyncio.gather(first.headers(),second.headers())
            self.assertEqual(maximum,1);self.assertEqual(closed,2)
            await first.headers();self.assertEqual(closed,2)
        await first.close();await second.close()
