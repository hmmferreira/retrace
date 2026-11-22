"""Public-code-only shared image probe. Never load a native artifact or session."""
import asyncio
import os
from retrace.shared_runtime import require_shared_backend,configure_runtime
from retrace.artifact_policy import reviewed_artifact,ArtifactBlocked
from retrace.native_worker import _NativeChannel

from pathlib import Path
for notice in ('PYTHON_NOTICES.txt','unicorn-2.1.4/COPYING','unicorn-2.1.4/COPYING.LGPL2','unicorn-2.1.4/COPYING_GLIB','unicorn-2.1.4/PROVENANCE.json'):
    assert (Path('/app/licenses')/notice).is_file()
assert os.getuid()==1000
require_shared_backend()
assert configure_runtime({'runtime_mode':'shared'})=='shared'
try:reviewed_artifact('applemusic-arm64-v8a')
except ArtifactBlocked as error:assert error.code=='artifact_review_required'
else:raise AssertionError('Update smoke expectations after deliberate artifact approval')

async def probe():
    channel=_NativeChannel()
    try:
        async with asyncio.timeout(10):await channel._start()
    finally:await channel.close()
    assert channel._process.returncode is not None

asyncio.run(probe())
print('Shared smoke passed: pinned candidate, non-root, real native-worker boundary, default artifact refusal; no native artifact loaded.')

# Exercise the exact isolated reporting entrypoint without any item/account data.
# A normal JSON failure for the missing synthetic item proves startup reached the
# child main after checked runtime/SDK selection; a lost SDK path fails earlier.
import json
from pathlib import Path
import subprocess
import tempfile
from retrace.reporting_runtime import report_launch
from retrace.storage import atomic_json
with tempfile.TemporaryDirectory() as directory:
    root=Path(directory)
    options={'runtime_mode':'shared','private_evaluation':True}
    atomic_json(root/'runtime-options.json',options)
    configure_runtime(options)
    command,environment=report_launch(root)
    assert environment['RETRACE_RUNTIME_MODE']=='shared'
    assert environment['RETRACE_PRIVATE_EVALUATION']=='1'
    assert 'PYTHONPATH' not in environment and 'SUPERVISOR_TOKEN' not in environment
    child=subprocess.run(command,input=b'{"id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}',
        capture_output=True,env=environment,timeout=15,check=False)
    assert child.returncode==0 and json.loads(child.stdout)=={'ok':False,'error':'poll_failed'}
print('Shared report child smoke passed: fixed SDK paths, checked runtime context and no credential environment.')
