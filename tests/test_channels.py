import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("render_channel",ROOT/"tools/render-channel.py")
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class ChannelTests(unittest.TestCase):
    def test_edge_contains_only_install_files_and_matching_versions(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/"edge"
            module.render(ROOT,target,"edge","0.1.2-dev.2.1")
            config=(target/"retrace/config.yaml").read_text()
            self.assertEqual(json.loads((target/"retrace/rootfs/app/retrace/channel.json").read_text())["channel"],"edge")
            self.assertIn("name: Retrace Edge",config)
            self.assertIn("version: 0.1.2-dev.2.1",config)
            self.assertIn("stage: experimental",config)
            self.assertIn("backup: cold",config)
            manifest=json.loads((target/"custom_components/retrace/manifest.json").read_text())
            self.assertEqual(manifest["version"],"0.1.2-dev.2.1")
            self.assertFalse((target/"tools").exists())
            self.assertFalse((target/".git").exists())
            self.assertFalse((target/"data").exists())
            self.assertTrue((target/"LICENSE").exists())
            self.assertFalse(list(target.rglob("__pycache__")))
    def test_channel_versions_cannot_be_confused(self):
        with tempfile.TemporaryDirectory() as tmp:
            for channel,version in [("edge","0.1.2"),("stable","0.1.2-dev.1.1"),("edge","../secret")]:
                with self.assertRaises(ValueError):
                    module.render(ROOT,Path(tmp)/"output",channel,version)
    def test_stable_keeps_experimental_marker_until_live_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/"stable"
            module.render(ROOT,target,"stable","0.1.2")
            self.assertIn("stage: experimental",(target/"retrace/config.yaml").read_text())
            self.assertEqual(json.loads((target/"CHANNEL.json").read_text())["channel"],"stable")

    def test_authorized_stable_is_fresh_mac_source_build_without_private_evaluation(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'stable'
            module.render(ROOT,target,'stable','0.2.0',runtime='shared')
            config=(target/'retrace/config.yaml').read_text()
            self.assertIn('stage: stable',config)
            self.assertIn('  runtime_mode: shared',config)
            self.assertIn('  apple_music_provider: false',config)
            self.assertIn('  macos_provider: true',config)
            self.assertIn('  private_evaluation: false',config)
            self.assertIn('  create_new_identity: true',config)
            self.assertIn('boot: auto',config)
            self.assertEqual(json.loads((target/'retrace/rootfs/app/retrace/channel.json').read_text())['channel'],'stable')
            policy=json.loads((target/'RELEASE_POLICY.json').read_text())
            self.assertEqual(policy['apple_native_permission'],'unresolved-disclosed')
            self.assertFalse(policy['history_migration'])
            self.assertFalse(list(target.rglob('*.bin')))
            self.assertFalse(list(target.rglob('*.enc')))

    def test_shared_edge_renderer_selects_shared_dockerfile_and_explicit_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/"shared-edge"
            module.render(ROOT,target,"edge","0.1.12-dev.1.1",runtime="shared")
            self.assertIn("  runtime_mode: shared",(target/"retrace/config.yaml").read_text())
            config=(target/"retrace/config.yaml").read_text()
            self.assertIn("slug: retrace\n",config)
            self.assertIn("discovery:\n  - retrace\n",config)
            self.assertEqual(json.loads((target/"custom_components/retrace/manifest.json").read_text())["domain"],"retrace")
            self.assertEqual((target/"retrace/Dockerfile").read_bytes(),(ROOT/"retrace/Dockerfile.shared").read_bytes())
            self.assertEqual(json.loads((target/"CHANNEL.json").read_text())["runtime"],"shared")
            self.assertIn("same authenticated account",(target/"retrace/DOCS.md").read_text())
            self.assertEqual((target/"retrace/apparmor.txt").read_bytes(),(ROOT/"retrace/apparmor.shared.txt").read_bytes())
            with self.assertRaises(ValueError):module.render(ROOT,Path(tmp)/"stable","stable","0.1.12",runtime="shared")

    def test_channel_render_excludes_private_component_and_session_files(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/"source";source.mkdir()
            for folder in ('retrace','custom_components','docs'):
                shutil.copytree(ROOT/folder,source/folder,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
            for name in ('README.md','repository.yaml','hacs.json','LICENSE'):shutil.copyfile(ROOT/name,source/name)
            private=source/'retrace/rootfs/app/private-fixture';private.mkdir()
            for name in ('owned-libs.bin','source.apk','session.key','session.enc','account.json','owned-signing.json'):(private/name).write_text('SYNTHETIC_PRIVATE')
            target=Path(tmp)/'rendered'
            module.render(source,target,'edge','0.1.12-dev.1.1',runtime='shared')
            self.assertEqual(list((target/'retrace/rootfs/app/private-fixture').iterdir()),[])

    def test_shared_packages_preserve_exact_upstream_license_and_attribution(self):
        import hashlib
        spec=importlib.util.spec_from_file_location("render_evaluation",ROOT/"tools/render-evaluation.py")
        evaluation=importlib.util.module_from_spec(spec);spec.loader.exec_module(evaluation)
        expected=ROOT/"retrace/rootfs/app/licenses/FindMy.py-MIT.txt"
        self.assertEqual(hashlib.sha256(expected.read_bytes()).hexdigest(),
                         "51396fd82204e1d844bbff2019054d8c3712e53c3ed8485c9f19dd73990eb46e")
        with tempfile.TemporaryDirectory() as tmp:
            normal=Path(tmp)/"edge"
            module.render(ROOT,normal,"edge","0.1.13-dev.1.6",runtime="shared")
            separate=Path(tmp)/"evaluation"
            evaluation.render(ROOT,separate,"0.1.13-dev.1.6")
            for app in (normal/"retrace",separate/"retrace_shared"):
                self.assertEqual((app/"rootfs/app/licenses/FindMy.py-MIT.txt").read_bytes(),expected.read_bytes())
                self.assertIn("Copyright (c) 2023 FindMy.py Contributors",
                              (app/"rootfs/app/licenses/NOTICE.md").read_text())
                docker=(app/"Dockerfile").read_text()
                self.assertIn("COPY rootfs/app /app",docker)
                self.assertIn("findmy LICENSE.md",docker)
            self.assertIn(expected.read_text(),(normal/"docs/THIRD_PARTY_NOTICES.md").read_text())
