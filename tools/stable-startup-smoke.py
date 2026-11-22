"""Fresh stable startup probe. Run in a disposable network-disabled container."""
import json
from pathlib import Path
import subprocess
import time
import urllib.request
import urllib.error

options={'runtime_mode':'shared','apple_music_provider':False,'macos_provider':True,
         'create_new_identity':True,'private_evaluation':False,
         'experimental_macos_signer':False,'install_reviewed_component':False,
         'shared_artifact_id':'applemusic-arm64-v8a'}
Path('/data/options.json').write_text(json.dumps(options));Path('/data/options.json').chmod(0o600)
process=subprocess.Popen(['python','/app/bootstrap.py'])
try:
    for _ in range(40):
        if process.poll() is not None:raise RuntimeError('Fresh stable startup exited')
        try:
            with urllib.request.urlopen('http://127.0.0.1:8099/health',timeout=1) as r:
                if json.load(r)=={'status':'ready'}:break
        except (OSError,ValueError):time.sleep(.25)
    else:raise RuntimeError('Fresh stable startup did not become ready')
    root=Path('/data/retrace')
    identity=json.loads((root/'identity.json').read_text())
    req=urllib.request.Request('http://127.0.0.1:8100/v1/snapshot',headers={'Authorization':'Bearer '+identity['read_token']})
    with urllib.request.urlopen(req,timeout=2) as r:snapshot=json.load(r)
    assert snapshot['channel']=='stable' and snapshot['items']==[]
    assert not list(root.rglob('*.bin'))
    assert not list(root.rglob('machine.json'))
    assert not list(root.rglob('native-consent.json'))
    assert not list(root.rglob('*.enc'))
    assert not Path('/usr/local/bin/findmy-export').exists()
    try:urllib.request.urlopen('http://127.0.0.1:8099/',timeout=2)
    except urllib.error.HTTPError as error:assert error.code==403
    else:raise AssertionError('Management accepted an untrusted peer')
    print('Fresh Stable smoke passed: ready without network/artifact/identity provisioning; empty stable state; management protected.')
finally:
    process.terminate()
    try:process.wait(timeout=15)
    except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
