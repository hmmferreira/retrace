import asyncio
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock,patch
from aiohttp.test_utils import TestClient,TestServer
from findmy import FindMyAccessory,LoginState
from retrace.storage import Store,read_json,atomic_json
from retrace.worker import AppleWorker
from retrace.shared_ui import SharedDiscoveryUI,compose_shared_ui
from retrace.shared_inventory import PrivateInventorySink
from retrace.server import make_app

class SharedUI(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name))
        self.account=SimpleNamespace(login_state=LoginState.LOGGED_IN,_password="synthetic-password",close=AsyncMock(),login=AsyncMock(return_value=LoginState.LOGGED_IN))
        self.client=SimpleNamespace(recovery_options=AsyncMock(return_value=SimpleNamespace(recoverable=[SimpleNamespace(device_name="Synthetic phone",device_model="iPhone")])),unlock=AsyncMock(),accessories=AsyncMock(return_value=[]),close=AsyncMock())
        self.writer=AsyncMock();self.worker=AppleWorker(self.store,account_factory=AsyncMock(return_value=self.account),session_writer=self.writer)
        self.saved=[]
        async def commit(items):self.saved.extend(items)
        self.ui=SharedDiscoveryUI(commit,factory=AsyncMock(return_value=self.client));self.ui.bind(self.worker)
    async def asyncTearDown(self):await self.ui.close();self.tmp.cleanup()
    async def test_background_login_hands_same_account_to_discovery_and_closes_on_cancel(self):
        gate=asyncio.Event()
        async def login(*args):await gate.wait();return LoginState.LOGGED_IN
        self.account.login.side_effect=login
        state=await self.ui.authenticate("owner",lambda:self.worker.login("owner","fixture@example.invalid","synthetic-password"))
        self.assertEqual(state,{"phase":"working"});await asyncio.sleep(0)
        self.assertFalse(self.ui.auth_task.done());gate.set();await self.ui.auth_task
        await self.ui.flow.task
        self.writer.assert_awaited_once_with(self.account)
        self.ui.flow.factory.assert_awaited_once_with(self.account)
        self.account.close.assert_not_awaited()
        self.assertIsNone(self.worker.pending);self.assertIsNone(self.account._password)
        self.assertEqual(self.ui.visible("stranger"),{"phase":"busy"})
        await self.ui.action("owner",{"action":"cancel"})
        self.account.close.assert_awaited_once();self.client.close.assert_awaited_once()
    async def test_unlock_uses_opaque_choice_no_duplicate_credentials(self):
        await self.ui.authenticated("owner",self.account);await self.ui.flow.task
        choice=self.ui.visible("owner")["choices"][0]["value"]
        result=await self.ui.action("owner",{"action":"answer","choice":choice,"passcode":"synthetic-passcode"})
        self.assertEqual(result["phase"],"working");await self.ui.flow.task;await self.ui.watcher
        self.assertEqual(self.ui.visible("owner"),{"phase":"complete","item_count":0})
        self.assertNotIn("synthetic-passcode",json.dumps(self.ui.visible("owner")))
        self.account.close.assert_awaited_once()
    async def test_default_account_factory_cannot_be_ui_enabled(self):
        with self.assertRaisesRegex(ValueError,"reviewed_account_lifecycle_required"):
            SharedDiscoveryUI(AsyncMock()).bind(AppleWorker(self.store))
    async def test_ingress_routes_return_accepted_and_require_consent(self):
        client=TestClient(TestServer(make_app(self.store,management=True,trusted_peer="127.0.0.1",worker=self.worker,shared_ui=self.ui)))
        await client.start_server()
        headers={"X-Remote-User-Id":"owner","X-Remote-User-Groups":"system-admin"}
        try:
            state=await (await client.get('/v1/snapshot',headers=headers)).json()
            self.assertTrue(state["setup"]["shared_auth"])
            headers["X-CSRF-Token"]=state["csrf"]
            body={"email":"fixture@example.invalid","password":"synthetic-password"}
            self.assertEqual((await client.post('/ui/login',headers=headers,json=body)).status,400)
            gate=asyncio.Event()
            async def login(*args):await gate.wait();return LoginState.LOGGED_IN
            self.account.login.side_effect=login
            response=await client.post('/ui/login',headers=headers,json={**body,"discovery_consent":True})
            self.assertEqual(response.status,202);self.assertEqual((await response.json())["phase"],"working")
            response=await client.get('/v1/snapshot',headers=headers)
            self.assertEqual((await response.json())["auth"],{"phase":"working"})
            gate.set();await self.ui.auth_task
        finally:await client.close()

    async def test_unavailable_or_unknown_provider_never_starts_authentication(self):
        client=TestClient(TestServer(make_app(self.store,management=True,trusted_peer="127.0.0.1",worker=self.worker,shared_ui=self.ui)))
        await client.start_server()
        headers={"X-Remote-User-Id":"owner","X-Remote-User-Groups":"system-admin"}
        try:
            state=await (await client.get('/v1/snapshot',headers=headers)).json()
            self.assertEqual(state['setup']['authentication_provider'],'apple_music')
            self.assertFalse(state['setup']['authentication_providers'][1]['available'])
            headers['X-CSRF-Token']=state['csrf']
            for provider,status in [('macos',409),('unknown',400),({},400)]:
                response=await client.post('/ui/login',headers=headers,json={
                    'email':'fixture@example.invalid','password':'synthetic-password',
                    'discovery_consent':True,'provider':provider})
                self.assertEqual(response.status,status)
            self.worker.account_factory.assert_not_awaited()
            self.writer.assert_not_awaited()
            self.assertIsNone(self.ui.auth_task)
        finally:await client.close()

    async def test_enabled_mac_selection_reaches_only_mac_factory(self):
        self.ui.macos_available=True
        client=TestClient(TestServer(make_app(self.store,management=True,trusted_peer="127.0.0.1",worker=self.worker,shared_ui=self.ui)))
        await client.start_server()
        headers={"X-Remote-User-Id":"owner","X-Remote-User-Groups":"system-admin"}
        try:
            state=await (await client.get('/v1/snapshot',headers=headers)).json()
            self.assertTrue(state['setup']['authentication_providers'][1]['available'])
            headers['X-CSRF-Token']=state['csrf']
            response=await client.post('/ui/login',headers=headers,json={
                'email':'fixture@example.invalid','password':'synthetic-password',
                'discovery_consent':True,'provider':'macos'})
            self.assertEqual(response.status,202)
            await self.ui.auth_task
            self.worker.account_factory.assert_awaited_once_with('macos')
        finally:await client.close()

    async def test_native_consent_is_enforced_server_side_before_credentials_reach_factory(self):
        self.ui.macos_available=True;self.ui.default_provider='macos'
        self.ui.apple_music_available=False;self.ui.native_consent_required=lambda:True
        client=TestClient(TestServer(make_app(self.store,management=True,trusted_peer="127.0.0.1",worker=self.worker,shared_ui=self.ui)))
        await client.start_server()
        headers={"X-Remote-User-Id":"owner","X-Remote-User-Groups":"system-admin"}
        try:
            state=await (await client.get('/v1/snapshot',headers=headers)).json()
            self.assertTrue(state['setup']['native_component_consent_required'])
            headers['X-CSRF-Token']=state['csrf']
            body={'email':'fixture@example.invalid','password':'synthetic-password','discovery_consent':True}
            response=await client.post('/ui/login',headers=headers,json=body)
            self.assertEqual(response.status,409)
            self.assertEqual((await response.json())['error'],'native_consent_required')
            self.worker.account_factory.assert_not_awaited()
            response=await client.post('/ui/login',headers=headers,json={**body,'native_component_consent':True})
            self.assertEqual(response.status,202)
            await self.ui.auth_task
            self.worker.account_factory.assert_awaited_once_with('macos',native_consent=True)
        finally:await client.close()

    async def test_expired_verification_is_explicit_and_does_not_reuse_credentials(self):
        self.ui.auth_owner="owner"
        self.ui.auth_state={"phase":"verification_code","method":0}
        self.assertIsNone(self.worker.pending)
        self.assertEqual(self.ui.auth_visible("owner"),{"phase":"failed","error":"sign_in_expired"})
        self.assertEqual(self.ui.auth_visible("stranger"),{"phase":"busy"})
        self.account.login.assert_not_awaited()

    async def test_session_save_failure_closes_account_before_discovery(self):
        from retrace.owned_session import SessionBlocked
        self.writer.side_effect=SessionBlocked("session_snapshot_failed")
        await self.ui.authenticate("owner",lambda:self.worker.login("owner","fixture@example.invalid","synthetic-password"))
        await self.ui.auth_task
        self.assertEqual(self.ui.auth_visible("owner"),{"phase":"failed","error":"session_save_failed"})
        self.ui.flow.factory.assert_not_awaited()
        self.assertIsNone(self.worker.pending);self.assertIsNone(self.account._password)
        self.account.close.assert_awaited_once()

    async def test_cancel_signin_clears_transient_password_and_reaps_task(self):
        entered=asyncio.Event()
        async def login(*args):entered.set();await asyncio.Event().wait()
        self.account.login.side_effect=login
        await self.ui.authenticate("owner",lambda:self.worker.login("owner","fixture@example.invalid","synthetic-password"))
        await entered.wait();await self.ui.cancel_auth("owner")
        self.assertTrue(self.ui.auth_task.done());self.assertIsNone(self.worker.pending)
        self.assertIsNone(self.account._password);self.account.close.assert_awaited_once()

    async def test_explicit_composition_rejects_unprotected_account_factory(self):
        worker,bridge=compose_shared_ui(self.store,account_factory=AsyncMock(return_value=self.account),
            session_writer=self.writer,session_available=lambda:False)
        try:
            await bridge.authenticate("owner",lambda:worker.login("owner","fixture@example.invalid","synthetic-password"))
            await bridge.auth_task
            self.account.login.assert_not_awaited();self.account.close.assert_awaited_once()
            self.assertEqual(bridge.auth_visible("owner")["phase"],"failed")
        finally:await bridge.close()

    async def test_session_availability_callback_drives_manual_readiness(self):
        worker=AppleWorker(self.store,session_available=lambda:True)
        self.store.items={"fixture":{"enabled":True}}
        worker._manual_refresh=AsyncMock()
        self.assertFalse((self.store.root/"account.json").exists())
        self.assertEqual(worker.request_refresh("fixture")["status"],"queued")
        await asyncio.sleep(0);await worker.close()

class Inventory(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name));self.worker=AppleWorker(self.store)
        self.sink=PrivateInventorySink(self.store,self.worker)
    async def asyncTearDown(self):self.tmp.cleanup()
    def accessory(self,identifier="synthetic-item"):
        return FindMyAccessory(master_key=b"\x01"*28,skn=b"\x02"*32,sks=b"\x03"*32,paired_at=datetime(2024,1,1,tzinfo=timezone.utc),name="Synthetic item",identifier=identifier)
    async def test_atomic_manifest_preserves_selection_alignment_and_hides_keys(self):
        accessory=self.accessory();await self.sink([accessory])
        key=hashlib.sha256(b"synthetic-item").hexdigest()[:32]
        self.store.select([key]);self.store.items[key]["name"]="Custom name"
        oldpath=self.store.root/"keys"/self.store.items[key]["key_file"]
        raw=read_json(oldpath);raw["alignment_index"]=7;atomic_json(oldpath,raw)
        await self.sink([self.accessory(),self.accessory("second")])
        self.assertTrue(self.store.items[key]["enabled"]);self.assertEqual(self.store.items[key]["name"],"Custom name")
        self.assertEqual(read_json(self.store.root/"keys"/self.store.items[key]["key_file"])["alignment_index"],7)
        self.assertEqual(sum(i["enabled"] for i in self.store.items.values()),1)
        self.assertNotIn("master_key",json.dumps(self.store.public()))
        self.assertTrue(all(stat.S_IMODE(p.stat().st_mode)==0o600 for p in (self.store.root/"keys").iterdir()))
    async def test_invalid_inventory_never_changes_manifest(self):
        await self.sink([self.accessory()]);before=read_json(self.store.root/"items.json")
        with self.assertRaises(Exception):await self.sink([self.accessory("new"),object()])
        self.assertEqual(self.store.items,before);self.assertEqual(read_json(self.store.root/"items.json"),before)
    async def test_failed_manifest_write_keeps_old_keys_and_selection(self):
        await self.sink([self.accessory()]);before=dict(self.store.items)
        original=atomic_json
        def write(path,data):
            if path.name=="items.json":raise OSError("synthetic disk failure")
            original(path,data)
        with patch("retrace.shared_inventory.atomic_json",side_effect=write):
            with self.assertRaises(OSError):await self.sink([self.accessory("new")])
        self.assertEqual(self.store.items,before)
        self.assertEqual(read_json(self.store.root/"items.json"),before)
        self.assertFalse(self.worker.inventory_busy)
        self.assertEqual(self.worker.query_slots._value,self.worker.CONCURRENCY)

    async def test_inventory_waits_for_poll_children_and_blocks_new_manual_requests(self):
        await self.worker.query_slots.acquire()
        task=asyncio.create_task(self.sink([self.accessory()]))
        await asyncio.sleep(0)
        self.assertTrue(self.worker.inventory_busy)
        self.assertFalse(task.done())
        self.assertEqual(self.worker.request_refresh("unused")["status"],"discovery_busy")
        self.assertFalse((self.store.root/"items.json").exists())
        self.worker.query_slots.release()
        await asyncio.wait_for(task,2)
        self.assertEqual(len(self.store.items),1)
        self.assertFalse(self.worker.inventory_busy)
