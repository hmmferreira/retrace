import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from retrace.macos_store import MachineStore
from retrace.macos_identity import new_machine
from retrace.owned_session import SessionBlocked
from retrace.private_session_store import active_provider
from retrace.storage import atomic_json

class MacStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.store=MachineStore(self.root/'providers'/'macos')
        self.machine=new_machine();self.machine['saved']={'adi-000001F5.pb':base64.b64encode(b'synthetic-native-state').decode()}
    def test_encrypted_independent_roundtrip_and_permissions(self):
        old=self.root/'owned-signing.json';old.write_bytes(b'old fixture unchanged')
        self.store.save(self.machine)
        self.assertEqual(self.store.load(),self.machine)
        self.assertEqual(old.read_bytes(),b'old fixture unchanged')
        for path in self.store.root.iterdir():
            self.assertEqual(path.stat().st_mode&0o777,0o600)
            self.assertNotIn(b'synthetic-native-state',path.read_bytes())
        self.assertEqual(active_provider(self.root),'apple_music')
    def test_retention_is_bounded_and_unrelated_provider_files_are_preserved(self):
        self.store.save(self.machine)
        other=self.store.root/'session-fixture.enc';other.write_bytes(b'unrelated session fixture')
        for routing in range(10):self.store.save(dict(self.machine,routing=routing))
        self.assertEqual(len(list(self.store.root.glob('machine-*.enc'))),3)
        self.assertEqual(len(list(self.store.root.glob('machine-*.key'))),3)
        self.assertEqual(self.store.load()['routing'],9)
        self.assertEqual(other.read_bytes(),b'unrelated session fixture')

    def test_concurrent_reads_survive_generation_cleanup(self):
        from concurrent.futures import ThreadPoolExecutor
        self.store.save(self.machine)
        def write():
            for routing in range(25):self.store.save(dict(self.machine,routing=routing))
        def read():
            for _ in range(100):self.assertIsInstance(self.store.load()['routing'],int)
        with ThreadPoolExecutor(max_workers=2) as pool:
            writer=pool.submit(write);reader=pool.submit(read)
            writer.result(timeout=10);reader.result(timeout=10)
        self.assertEqual(self.store.load()['routing'],24)
        self.assertEqual(len(list(self.store.root.glob('machine-*.enc'))),3)

    def test_failed_publish_preserves_old_generation(self):
        self.store.save(self.machine)
        changed=dict(self.machine,routing=77)
        with patch('retrace.macos_store.atomic_json',side_effect=OSError('synthetic disk failure')):
            with self.assertRaises(OSError):self.store.save(changed)
        self.assertEqual(self.store.load(),self.machine)
    def test_corrupt_machine_never_replaced_implicitly(self):
        self.store.save(self.machine)
        (self.store.root/'machine.json').write_text('{}')
        with self.assertRaises(SessionBlocked):self.store.load()
    def test_provider_pointer_is_strict(self):
        for value in ({'version':True,'provider':'macos'},{'version':1,'provider':'../outside'},{'version':1,'provider':'macos','extra':1}):
            atomic_json(self.root/'active-provider.json',value)
            with self.assertRaises(SessionBlocked):active_provider(self.root)
        atomic_json(self.root/'active-provider.json',{'version':1,'provider':'macos'})
        self.assertEqual(active_provider(self.root),'macos')
