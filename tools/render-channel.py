"""Render an installable channel from source; never read runtime directories."""
import argparse
import json
from pathlib import Path
import re
import shutil


def render(source, target, channel, version, *, runtime="legacy"):
    if channel not in ("edge", "stable"):
        raise ValueError("Unknown channel")
    if runtime not in ("legacy","shared"):raise ValueError("Unknown runtime")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-dev\.[0-9]+\.[0-9]+)?", version):
        raise ValueError("Invalid version")
    if (channel == "edge") != ("-dev." in version):
        raise ValueError("Edge must use a development version")
    if channel=='stable' and runtime=='shared':
        record=Path(source)/'release'/(version+'.json')
        try:approval=json.loads(record.read_text())
        except Exception:raise ValueError('No version-specific maintainer release authorization') from None
        if (approval.get('version')!=version or approval.get('channel')!='stable' or
                approval.get('maintainer_release_authorized') is not True or
                approval.get('distribution')!='source-build-only' or
                approval.get('apple_binaries_in_package') is not False or
                approval.get('local_native_consent_required') is not True or
                approval.get('history_migration') is not False):
            raise ValueError('Invalid release authorization')
    target.mkdir(parents=True, exist_ok=False)
    for name in ("retrace", "custom_components", "docs"):
        shutil.copytree(source/name, target/name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.apk", "*.bin", "*.enc", "*.key", "*.plist", "runtime-options.json", "account.json", "owned-session.json", "owned-signing.json", "identity.json", "machine.json", "active-provider.json", "signer.lock", "store.lock", "native-consent.json", "*.dmg", "*.x86_64"))
    for name in ("README.md", "repository.yaml", "hacs.json", "LICENSE"):
        shutil.copyfile(source/name, target/name)
    (target/"retrace/rootfs/app/retrace/channel.json").write_text(
        json.dumps({"channel":channel,"version":version})+"\n")
    config=target/"retrace/config.yaml"
    text=config.read_text()
    text=re.sub(r"(?m)^version:.*$", "version: "+version, text)
    title="Retrace Edge" if channel=="edge" else "Retrace"
    text=re.sub(r"(?m)^name:.*$", "name: "+title, text)
    text=re.sub(r"(?m)^panel_title:.*$", "panel_title: "+title, text)
    if runtime=="shared":
        shutil.copyfile(target/"retrace/Dockerfile.shared",target/"retrace/Dockerfile")
        shutil.copyfile(target/"retrace/apparmor.shared.txt",target/"retrace/apparmor.txt")
        shutil.copyfile(target/"retrace"/("DOCS.stable.md" if channel=="stable" else "DOCS.shared.md"),target/"retrace/DOCS.md")
        text=text.replace("  runtime_mode: legacy","  runtime_mode: shared",1)
    if channel=='stable' and runtime=='shared':
        text=text.replace('  apple_music_provider: true','  apple_music_provider: false',1)
        text=text.replace('  macos_provider: false','  macos_provider: true',1)
        text=text.replace('  create_new_identity: false','  create_new_identity: true',1)
        text=text.replace('boot: manual','boot: auto',1)
        text=text.replace('stage: experimental','stage: stable',1)
        shutil.copyfile(Path(source)/'release'/(version+'.json'),target/'RELEASE_POLICY.json')
    config.write_text(text)
    # Channel name alone never removes experimental status: live validation is required.
    repo=target/"repository.yaml"
    repo.write_text(repo.read_text().replace("Retrace — development", "Retrace — "+channel))
    manifest=target/"custom_components/retrace/manifest.json"
    data=json.loads(manifest.read_text())
    data["version"]=version
    manifest.write_text(json.dumps(data,indent=2)+"\n")
    (target/"CHANNEL.json").write_text(json.dumps({"channel":channel,"version":version,"runtime":runtime},indent=2)+"\n")

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("channel",choices=["edge","stable"])
    parser.add_argument("version")
    parser.add_argument("output",type=Path)
    parser.add_argument("--runtime",choices=["legacy","shared"],default="legacy")
    args=parser.parse_args()
    render(Path(__file__).resolve().parents[1],args.output,args.channel,args.version,runtime=args.runtime)
